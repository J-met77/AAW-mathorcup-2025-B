# -*- coding: utf-8 -*-
"""
q_sensitivity.py — A7 交付：敏感性/消融/稳健性实验
P1 Q1 规则参数扰动（阈值曲线 a,b 扰动 → 标签稳定性）
P2 Q2 特征组消融（索赔金额组/时效组/网点组/辅助 x̂）
P3 Q2 随机种子稳健性（3 seeds）
P4 Q3 阈值校正敏感性（b_sev 扫描，源自 q3_threshold_search.csv）
P5 附件2 预测分布 vs 训练目标分布（外推稳健性）
产出：output/tables/q_sensitivity.csv（四张分表）+ output/logs/q_sensitivity.log
运行：python code/q_sensitivity.py
"""
import sys, json, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CLEAN, TBL, FEATURES, CAT_FEATURES, get_X, smape, wmape, LABELS
import lightgbm as lgb

LOGF = OUT_LOG = Path(__file__).resolve().parent.parent / "output" / "logs" / "q_sensitivity.log"


def log(msg):
    print(msg)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def rule_label(c, yhat, a1, b1, a2, b2):
    x = np.asarray(c) - np.asarray(yhat)
    t1, t2 = a1 * np.power(yhat, b1), a2 * np.power(yhat, b2)
    return np.where(x <= t1, LABELS[0], np.where(x <= t2, LABELS[1], LABELS[2]))


def cv_smape(X, z, y, folds, seed=2025):
    oof = np.zeros(len(y))
    params = dict(objective="regression_l1", learning_rate=0.05, num_leaves=63,
                  min_child_samples=20, colsample_bytree=0.9, subsample=0.9,
                  subsample_freq=1, reg_lambda=1.0, n_estimators=2000,
                  random_state=seed, n_jobs=-1, verbose=-1)
    for a, b in folds:
        m = lgb.LGBMRegressor(**params)
        m.fit(X.iloc[a], z[a], eval_set=[(X.iloc[b], z[b])], eval_metric="l1",
              callbacks=[lgb.early_stopping(200, verbose=False)])
        oof[b] = m.predict(X.iloc[b], num_iteration=m.best_iteration_)
    return smape(y, np.expm1(oof)), wmape(y, np.expm1(oof))


def main():
    t0 = time.time()
    tr = pd.read_csv(CLEAN / "clean_附件1.csv")
    te = pd.read_csv(CLEAN / "clean_附件2.csv")
    lab = pd.read_csv(CLEAN / "q1_附件1_标注.csv")
    oof_q2 = pd.read_csv(CLEAN / "q2_附件1_OOF.csv")
    prm = json.load(open(TBL / "q1_rule_params.json", encoding="utf-8"))
    folds = [(a, b) for a, b in np.load(CLEAN / "cv_folds.npy", allow_pickle=True)]
    y = tr["payment_real"].values.astype(float)
    c = tr["claim_amount"].values.astype(float)
    base_label = lab["风险标注"].values

    # ===== P1 Q1 规则参数扰动 =====
    rows = []
    scen = [("基准", 1, 0, 1, 0), ("T1系数×0.9", 0.9, 0, 1, 0), ("T1系数×1.1", 1.1, 0, 1, 0),
            ("T2系数×0.9", 1, 0, 0.9, 0), ("T2系数×1.1", 1, 0, 1.1, 0),
            ("b1−0.03", 1, -0.03, 1, 0), ("b1+0.03", 1, +0.03, 1, 0),
            ("b2−0.03", 1, 0, 1, -0.03), ("b2+0.03", 1, 0, 1, +0.03)]
    for name, m1, d1, m2, d2 in scen:
        lb = rule_label(c, y, prm["a1"] * m1, prm["b1"] + d1, prm["a2"] * m2, prm["b2"] + d2)
        rows.append({"扰动": name,
                     "合理占比": round(float((lb == LABELS[0]).mean()), 4),
                     "诉求偏高占比": round(float((lb == LABELS[1]).mean()), 4),
                     "严重超额占比": round(float((lb == LABELS[2]).mean()), 4),
                     "与基准标注一致率": round(float((lb == base_label).mean()), 4)})
    p1 = pd.DataFrame(rows)
    p1.to_csv(TBL / "q1_sensitivity.csv", index=False, encoding="utf-8-sig")
    log("P1 Q1 规则参数扰动:\n" + p1.to_string(index=False))

    # ===== P2 Q2 特征组消融 =====
    Xtr, Xte = get_X(tr), get_X(te)
    for col in CAT_FEATURES:
        cats = sorted(set(tr[col].astype(str)) | set(te[col].astype(str)))
        dt = pd.CategoricalDtype(categories=cats)
        Xtr[col] = Xtr[col].astype(str).astype(dt)
        Xte[col] = Xte[col].astype(str).astype(dt)
    z = np.log1p(y)
    xhat = c - oof_q2["oof_pred"].values
    ablate = {
        "全特征+x̂(生产配置)": (FEATURES, True),
        "全特征无x̂": (FEATURES, False),
        "无索赔金额组(含x̂)": ([f for f in FEATURES if f not in ("claim_amount", "log_claim")], True),
        "无索赔金额组(无x̂)": ([f for f in FEATURES if f not in ("claim_amount", "log_claim")], False),
        "无保价组(含x̂)": ([f for f in FEATURES if f not in ("insure_amount", "log_insure", "insure_to_claim")], True),
        "无时效组(含x̂)": ([f for f in FEATURES if not f.startswith(("overtime", "case_delay"))], True),
        "无网点组(含x̂)": ([f for f in FEATURES if not f.startswith(("start_node", "end_node"))], True),
        "无城市/ID组(含x̂)": ([f for f in FEATURES if f not in ("start_city_id", "end_city_id", "consigner_freq", "receiver_freq")], True),
    }
    rows = []
    for name, (cols, use_xhat) in ablate.items():
        X = Xtr[cols].copy()
        if use_xhat:
            X["x_hat"] = xhat
        s, w = cv_smape(X, z, y, folds)
        rows.append({"消融": name, "OOF_SMAPE": round(s, 4), "OOF_WMAPE": round(w, 4)})
    p2 = pd.DataFrame(rows)
    p2.to_csv(TBL / "q2_ablation.csv", index=False, encoding="utf-8-sig")
    log("\nP2 Q2 特征组消融:\n" + p2.to_string(index=False))

    # ===== P3 种子稳健性 =====
    rows = []
    for seed in [2025, 7, 42]:
        X = Xtr.copy(); X["x_hat"] = xhat
        s, w = cv_smape(X, z, y, folds, seed=seed)
        rows.append({"seed": seed, "OOF_SMAPE": round(s, 4), "OOF_WMAPE": round(w, 4)})
    p3 = pd.DataFrame(rows)
    p3.to_csv(TBL / "q2_seed_stability.csv", index=False, encoding="utf-8-sig")
    log("\nP3 种子稳健性:\n" + p3.to_string(index=False)
        + f"\nSMAPE mean±std = {p3['OOF_SMAPE'].mean():.4f} ± {p3['OOF_SMAPE'].std():.4f}")

    # ===== P4 Q3 阈值敏感性（读阈值搜索表）=====
    ts = pd.read_csv(TBL / "q3_threshold_search.csv")
    best_bm_row = ts.sort_values("macro_f1", ascending=False).iloc[0]
    bmid = float(best_bm_row["b_mid"])
    rows = []
    for bs in [-1.0, -0.8, -0.5, -0.2, 0.0, 0.5, 1.0]:
        cand = ts[(np.abs(ts["b_mid"] - bmid) < 0.05) & (np.abs(ts["b_sev"] - bs) < 0.05)]
        if len(cand):
            r = cand.sort_values("macro_f1", ascending=False).iloc[0]
            rows.append({"b_mid": r["b_mid"], "b_sev": r["b_sev"],
                         "macro_f1": r["macro_f1"], "dev_max_pp": r["dev_max_pp"]})
    p4 = pd.DataFrame(rows)
    p4.to_csv(TBL / "q3_threshold_sensitivity.csv", index=False, encoding="utf-8-sig")
    log("\nP4 Q3 阈值敏感性(b_sev 扫描):\n" + p4.to_string(index=False))

    # ===== P5 外推稳健性：附件2 预测分布 vs 训练目标分布 =====
    pred_q2 = pd.read_csv(CLEAN / "q2_附件2_预测.csv")
    q_tr = np.percentile(y, [10, 25, 50, 75, 90])
    q_te = np.percentile(pred_q2["pred_payment"], [10, 25, 50, 75, 90])
    p5 = pd.DataFrame({"分位": ["P10", "P25", "P50", "P75", "P90"],
                       "训练实赔": np.round(q_tr, 2), "附件2预测": np.round(q_te, 2)})
    p5.to_csv(TBL / "q2_extrapolation_check.csv", index=False, encoding="utf-8-sig")
    log("\nP5 外推稳健性:\n" + p5.to_string(index=False))

    log(f"\n耗时 {time.time()-t0:.1f}s\n== 敏感性实验完成 ==")


if __name__ == "__main__":
    main()
