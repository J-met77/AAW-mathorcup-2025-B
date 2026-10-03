# -*- coding: utf-8 -*-
"""
q2_reg.py — A6 交付：问题2 实际赔付金额回归预测（最终方案）
主模型 = LightGBM 双参数化集成：
  模型M1: 目标 log1p(y)；模型M2: 目标 log(c/y)，还原 y_hat = c·exp(-t_hat)
  最终 ŷ = 0.5·expm1(t1) + 0.5·c·exp(-t2)（两个无偏尺度下的折中，实测 OOF 最优）
对比项：基线0（索赔十分位层中位数）、单目标 LGBM、XGBoost。
产出：
  output/tables/q2_metrics.csv、q2_model_compare.csv、q2_feature_importance.csv
  output/data/q2_附件1_OOF.csv（供 Q3 路线b）、q2_附件2_预测.csv、cv_folds.npy
运行：python code/q2_reg.py
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CLEAN, TBL, OUT, FEATURES, CAT_FEATURES, get_X, smape, wmape
import lightgbm as lgb
import xgboost as xgb
from sklearn.model_selection import KFold

SEED = 2025
NFOLD = 5
LOGF = OUT / "logs" / "q2_reg.log"
LOGF.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    print(msg)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def metrics(y, p):
    return {"SMAPE": round(smape(y, p), 4), "MAE": round(float(np.mean(np.abs(y - p))), 2),
            "RMSE": round(float(np.sqrt(np.mean((y - p) ** 2))), 2), "WMAPE": round(wmape(y, p), 4)}


LGB_PARAMS = dict(objective="regression_l1", learning_rate=0.03, num_leaves=63,
                  min_child_samples=20, colsample_bytree=0.9, subsample=0.9,
                  subsample_freq=1, reg_lambda=1.0, n_estimators=3000,
                  random_state=SEED, n_jobs=-1, verbose=-1)


def main():
    t0 = time.time()
    tr = pd.read_csv(CLEAN / "clean_附件1.csv")
    te = pd.read_csv(CLEAN / "clean_附件2.csv")
    y = tr["payment_real"].values.astype(float)
    c_tr = tr["claim_amount"].values.astype(float)
    c_te = te["claim_amount"].values.astype(float)

    Xtr, Xte = get_X(tr), get_X(te)
    for col in CAT_FEATURES:
        cats = sorted(set(tr[col].astype(str)) | set(te[col].astype(str)))
        dt = pd.CategoricalDtype(categories=cats)
        Xtr[col] = Xtr[col].astype(str).astype(dt)
        Xte[col] = Xte[col].astype(str).astype(dt)

    kf = KFold(n_splits=NFOLD, shuffle=True, random_state=SEED)
    folds = list(kf.split(Xtr))
    np.save(CLEAN / "cv_folds.npy", np.array(folds, dtype=object), allow_pickle=True)

    def cv_lgb(target, tag, X=None, X_test=None):
        X = Xtr if X is None else X
        Xt = Xte if X_test is None else X_test
        oof = np.zeros(len(tr)); imp = np.zeros(len(X.columns)); models = []; iters = []
        for i, (a, b) in enumerate(folds):
            m = lgb.LGBMRegressor(**LGB_PARAMS)
            m.fit(X.iloc[a], target[a], eval_set=[(X.iloc[b], target[b])], eval_metric="l1",
                  callbacks=[lgb.early_stopping(200, verbose=False)])
            oof[b] = m.predict(X.iloc[b], num_iteration=m.best_iteration_)
            imp += m.feature_importances_ / NFOLD
            iters.append(m.best_iteration_); models.append(m)
        log(f"  {tag}: best_iters={iters}")
        test_raw = np.mean([m.predict(Xt, num_iteration=m.best_iteration_) for m in models], axis=0)
        return oof, test_raw, imp

    # ---- 主模型：双参数化集成 ----
    log("训练 LGBM-M1 (log1p(y)) ...")
    o1, te1, imp1 = cv_lgb(np.log1p(y), "M1 log1p(y)")
    log("训练 LGBM-M2 (log(c/y)) ...")
    o2, te2, imp2 = cv_lgb(np.log(c_tr / y), "M2 log(c/y)")
    oof_ens = 0.5 * np.expm1(o1) + 0.5 * c_tr * np.exp(-o2)
    pred_ens = 0.5 * np.expm1(te1) + 0.5 * c_te * np.exp(-te2)

    # ---- 基线0：索赔十分位层中位数 ----
    bins = pd.qcut(c_tr, 10, labels=False, duplicates="drop")
    med_by_bin = pd.Series(y).groupby(np.asarray(bins)).median()
    te_bins = pd.cut(c_te, bins=pd.qcut(c_tr, 10, retbins=True, duplicates="drop")[1], labels=False)
    base_oof = pd.Series(np.asarray(bins)).map(med_by_bin).values.astype(float)
    base_test = (pd.Series(te_bins).map(med_by_bin).fillna(np.median(y)).values.astype(float))

    # ---- 对比：单目标与 XGBoost ----
    log("训练 XGBoost (log1p) ...")
    oof_xgb = np.zeros(len(tr))
    xgb_params = dict(n_estimators=3000, learning_rate=0.05, max_depth=8, subsample=0.8,
                      colsample_bytree=0.8, reg_lambda=5.0, min_child_weight=40,
                      random_state=SEED, n_jobs=-1, enable_categorical=True,
                      tree_method="hist", early_stopping_rounds=200)
    for i, (a, b) in enumerate(folds):
        m = xgb.XGBRegressor(**xgb_params)
        m.fit(Xtr.iloc[a], np.log1p(y)[a], eval_set=[(Xtr.iloc[b], np.log1p(y)[b])], verbose=False)
        oof_xgb[b] = m.predict(Xtr.iloc[b])

    rows = []
    for i, (a, b) in enumerate(folds):
        r = metrics(y[b], oof_ens[b]); r.update({"模型": "LGBM双目标集成", "折": i + 1}); rows.append(r)
    for name, oof in [("LGBM双目标集成", oof_ens), ("LGBM log1p(y)", np.expm1(o1)),
                      ("LGBM log(c/y)", c_tr * np.exp(-o2)), ("XGBoost log1p(y)", np.expm1(oof_xgb)),
                      ("基线0(索赔分层中位数)", base_oof)]:
        r = metrics(y, oof); r.update({"模型": name, "折": "OOF"}); rows.append(r)
    met = pd.DataFrame(rows)[["模型", "折", "SMAPE", "MAE", "RMSE", "WMAPE"]]
    met.to_csv(TBL / "q2_metrics.csv", index=False, encoding="utf-8-sig")
    log("\n" + met.to_string(index=False))

    cmp = (met[met["折"] == "OOF"][["模型", "SMAPE", "MAE", "RMSE", "WMAPE"]]
           .sort_values("SMAPE").reset_index(drop=True))
    cmp.to_csv(TBL / "q2_model_compare.csv", index=False, encoding="utf-8-sig")
    log("\n模型对比(OOF):\n" + cmp.to_string(index=False))

    imp_df = pd.DataFrame({"特征": list(Xtr.columns), "importance": (imp1 + imp2) / 2})
    imp_df = imp_df.sort_values("importance", ascending=False)
    imp_df.to_csv(TBL / "q2_feature_importance.csv", index=False, encoding="utf-8-sig")
    log("\n特征重要性 Top12:\n" + imp_df.head(12).to_string(index=False))

    if cmp.iloc[0]["模型"] != "LGBM双目标集成":
        log(f"警告：最优为 {cmp.iloc[0]['模型']}，仍按集成提交（差距见上表）")

    pd.DataFrame({"行序": np.arange(1, len(tr) + 1), "payment_real": y,
                  "oof_pred": oof_ens}).to_csv(CLEAN / "q2_附件1_OOF.csv", index=False, encoding="utf-8-sig")
    out_te = pd.DataFrame({"运单号": te["运单号"].values, "claim_amount": c_te,
                           "pred_payment": np.round(pred_ens, 2)})
    out_te.to_csv(CLEAN / "q2_附件2_预测.csv", index=False, encoding="utf-8-sig")
    log(f"\n附件2 预测: n={len(out_te)}, min={out_te.pred_payment.min():.2f}, "
        f"中位={out_te.pred_payment.median():.2f}, max={out_te.pred_payment.max():.2f}")
    log(f"耗时 {time.time()-t0:.1f}s\n== Q2 完成 ==")


if __name__ == "__main__":
    main()
