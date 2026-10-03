# -*- coding: utf-8 -*-
"""
q3_clf.py — A6 交付：问题3 风险标注分类（两路线对比 + 不均衡处理）
路线a：LightGBM 多分类（class_weight=balanced）+ 先验/阈值（类偏置）校正
路线b：用 Q2 的 ŷ 代入 Q1 规则 rule(c, ŷ) 直接映射标签
选择：OOF macro-F1 差距 <0.02 时取与规则自洽的路线b（paper/03 §2.1）
产出：
  output/tables/q3_route_compare.csv、q3_confusion_{a,b}.csv、q3_class_report.csv
  output/tables/q3_threshold_search.csv
  output/data/q3_附件2_预测.csv（含 pred_a / pred_b / final_label）
运行：python code/q3_clf.py（需先运行 q1_label.py 与 q2_reg.py）
"""
import sys, json, time
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CLEAN, TBL, OUT, FEATURES, CAT_FEATURES, get_X, LABELS
import lightgbm as lgb
from sklearn.metrics import f1_score, accuracy_score, confusion_matrix, classification_report

SEED = 2025
LOGF = OUT / "logs" / "q3_clf.log"


def log(msg):
    print(msg)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def rule_label(c, yhat, prm):
    """Q1 规则的向量化实现：x=c−y 与幂律阈值比较。"""
    x = np.asarray(c) - np.asarray(yhat)
    t1 = prm["a1"] * np.power(yhat, prm["b1"])
    t2 = prm["a2"] * np.power(yhat, prm["b2"])
    return np.where(x <= t1, LABELS[0], np.where(x <= t2, LABELS[1], LABELS[2]))


def report(y_true, y_pred, tag):
    f1m = f1_score(y_true, y_pred, average="macro")
    acc = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1, 2])
    return f1m, acc, cm


def save_cm(cm, path):
    pd.DataFrame(cm, index=["真_" + l for l in LABELS], columns=["判_" + l for l in LABELS]
                 ).to_csv(path, encoding="utf-8-sig")


def main():
    t0 = time.time()
    tr = pd.read_csv(CLEAN / "clean_附件1.csv")
    te = pd.read_csv(CLEAN / "clean_附件2.csv")
    lab = pd.read_csv(CLEAN / "q1_附件1_标注.csv")
    oof_q2 = pd.read_csv(CLEAN / "q2_附件1_OOF.csv")
    pred_q2 = pd.read_csv(CLEAN / "q2_附件2_预测.csv")
    with open(TBL / "q1_rule_params.json", encoding="utf-8") as f:
        prm = json.load(f)

    y_cls = lab["风险标注"].map({l: i for i, l in enumerate(LABELS)}).values
    c_tr = tr["claim_amount"].values.astype(float)
    c_te = te["claim_amount"].values.astype(float)
    folds = [(a.tolist(), b.tolist()) for a, b in np.load(CLEAN / "cv_folds.npy", allow_pickle=True)]

    Xtr, Xte = get_X(tr), get_X(te)
    for col in CAT_FEATURES:
        cats = sorted(set(tr[col].astype(str)) | set(te[col].astype(str)))
        dt = pd.CategoricalDtype(categories=cats)
        Xtr[col] = Xtr[col].astype(str).astype(dt)
        Xte[col] = Xte[col].astype(str).astype(dt)

    # ---- 回归辅助特征（混合路线）：x̂ = c − ŷ（OOF 防泄漏；测试端用全量预测）----
    xhat_tr = c_tr - oof_q2["oof_pred"].values
    xhat_te = c_te - pred_q2["pred_payment"].values
    Xtr["x_hat"] = xhat_tr
    Xte["x_hat"] = xhat_te
    log("已加入回归辅助特征 x_hat = c − ŷ（混合路线，A6 实验 D 组最优）")

    # ---- 类别权重（反频率）----
    cnt = np.bincount(y_cls, minlength=3)
    cw = {i: len(y_cls) / (3 * cnt[i]) for i in range(3)}
    log(f"类别数: {dict(zip(LABELS, cnt))}; class_weight={ {LABELS[i]: round(v,2) for i,v in cw.items()} }")

    # ===== 路线a：直接分类 =====
    params = dict(objective="multiclass", num_class=3, learning_rate=0.05,
                  num_leaves=63, min_child_samples=30, colsample_bytree=0.9,
                  subsample=0.9, subsample_freq=1, reg_lambda=1.0, n_estimators=2000,
                  class_weight=cw, random_state=SEED, n_jobs=-1, verbose=-1)
    probs_oof = np.zeros((len(tr), 3)); probs_te = np.zeros((len(te), 3))
    for i, (a, b) in enumerate(folds):
        m = lgb.LGBMClassifier(**params)
        m.fit(Xtr.iloc[a], y_cls[a], eval_set=[(Xtr.iloc[b], y_cls[b])], eval_metric="multi_logloss",
              callbacks=[lgb.early_stopping(200, verbose=False)])
        probs_oof[b] = m.predict_proba(Xtr.iloc[b], num_iteration=m.best_iteration_)
        probs_te += m.predict_proba(Xte, num_iteration=m.best_iteration_) / len(folds)
        log(f"  route-a fold{i+1}: best_iter={m.best_iteration_}")

    def apply_bias(P, bm, bs):
        adj = np.log(np.clip(P, 1e-9, 1)) + np.array([0.0, bm, bs])
        return np.argmax(adj, axis=1)

    # 先验/阈值校正搜索（macro-F1 最大；预测分布偏离先验 ≤2pp 为过滤条件，若无可行则放宽）
    prior = cnt / cnt.sum()
    rows = []
    for bm in np.arange(-2.0, 2.01, 0.1):
        for bs in np.arange(-3.0, 3.01, 0.1):
            yp = apply_bias(probs_oof, bm, bs)
            dist = np.bincount(yp, minlength=3) / len(yp)
            f1m = f1_score(y_cls, yp, average="macro")
            rows.append({"b_mid": round(bm, 2), "b_sev": round(bs, 2), "macro_f1": round(f1m, 4),
                         "dev_max_pp": round(float(np.max(np.abs(dist - prior)) * 100), 2)})
    ts = pd.DataFrame(rows)
    feasible = ts[ts["dev_max_pp"] <= 2.0]
    used = feasible if len(feasible) else ts
    best = used.sort_values("macro_f1", ascending=False).iloc[0]
    ts.sort_values("macro_f1", ascending=False).to_csv(
        TBL / "q3_threshold_search.csv", index=False, encoding="utf-8-sig")
    log(f"\n阈值校正: b_mid={best.b_mid}, b_sev={best.b_sev}, macro_f1={best.macro_f1} "
        f"(分布偏离 {best.dev_max_pp}pp；可行集 {len(feasible)}/{len(ts)})")
    pred_a_oof = apply_bias(probs_oof, best.b_mid, best.b_sev)
    pred_a_te = np.array(LABELS, dtype=object)[apply_bias(probs_te, best.b_mid, best.b_sev)]
    f1_a, acc_a, cm_a = report(y_cls, pred_a_oof, "a")

    # 未校正基线（用于展示校正增益）
    f1_raw = f1_score(y_cls, np.argmax(probs_oof, axis=1), average="macro")
    log(f"路线a: 未校正 macro-F1={f1_raw:.4f} → 校正后 {f1_a:.4f}")

    # ===== 路线b：先回归后标注 =====
    yhat_oof = oof_q2["oof_pred"].values
    pred_b_oof = rule_label(c_tr, yhat_oof, prm)
    pred_b_oof_idx = pd.Series(pred_b_oof).map({l: i for i, l in enumerate(LABELS)}).values
    f1_b, acc_b, cm_b = report(y_cls, pred_b_oof_idx, "b")
    consist = float(np.mean(pd.Series(pred_b_oof).map({l: i for i, l in enumerate(LABELS)}).values == y_cls))
    log(f"路线b: OOF 一致率={consist:.4f}, macro-F1={f1_b:.4f}")

    # ===== 路线对比 =====
    def cls_dist(idx):
        d = np.bincount(np.asarray(idx, int), minlength=3) / len(idx)
        return {LABELS[i]: round(float(d[i]), 4) for i in range(3)}

    cmp = pd.DataFrame([
        {"路线": "a: 直接分类+权重+阈值校正", "OOF_macro_F1": round(f1_a, 4), "OOF_accuracy": round(acc_a, 4),
         "与Q1规则一致率": round(float(np.mean(pred_a_oof == y_cls)), 4),
         "预测分布": str(cls_dist(pred_a_oof))},
        {"路线": "b: 先回归后标注", "OOF_macro_F1": round(f1_b, 4), "OOF_accuracy": round(acc_b, 4),
         "与Q1规则一致率": round(consist, 4),
         "预测分布": str(cls_dist(pred_b_oof_idx))},
    ])
    cmp.to_csv(TBL / "q3_route_compare.csv", index=False, encoding="utf-8-sig")
    log("\n路线对比:\n" + cmp.to_string(index=False))

    save_cm(cm_a, TBL / "q3_confusion_a.csv")
    save_cm(cm_b, TBL / "q3_confusion_b.csv")
    rep_a = classification_report(y_cls, pred_a_oof, target_names=LABELS, digits=4, output_dict=True)
    rep_b = classification_report(y_cls, pred_b_oof_idx, target_names=LABELS, digits=4, output_dict=True)
    rep = pd.DataFrame({**{f"a_{k}": v for k, v in rep_a.items() if isinstance(v, dict)},
                        **{f"b_{k}": v for k, v in rep_b.items() if isinstance(v, dict)}}).T
    rep.round(4).to_csv(TBL / "q3_class_report.csv", encoding="utf-8-sig")
    log("\n分类报告(路线a/b):\n" + rep.round(4).to_string())

    # ===== 测试端两路线 =====
    yhat_te = pred_q2["pred_payment"].values
    pred_b_te = rule_label(c_te, yhat_te, prm)

    # 提交策略（paper/03 §2.1）
    if f1_a - f1_b >= 0.02:
        final_te, final_name = pred_a_te, "a: 直接分类"
    else:
        final_te, final_name = pred_b_te, "b: 先回归后标注"
    log(f"\n提交路线: {final_name} (f1_a={f1_a:.4f}, f1_b={f1_b:.4f})")
    dist_te = pd.Series(final_te).value_counts(normalize=True).reindex(LABELS)
    log(f"附件2 预测分布:\n{dist_te.round(4).to_string()}")
    log("软约束校验: 合理≥85%%: %s; 严重<3%%: %s" % (
        "通过" if dist_te[LABELS[0]] >= 0.85 else "不通过",
        "通过" if dist_te[LABELS[2]] < 0.03 else "不通过"))

    pd.DataFrame({"运单号": te["运单号"].values, "pred_a": pred_a_te, "pred_b": pred_b_te,
                  "final_label": final_te}).to_csv(CLEAN / "q3_附件2_预测.csv", index=False,
                                                   encoding="utf-8-sig")
    log(f"耗时 {time.time()-t0:.1f}s\n== Q3 完成 ==")


if __name__ == "__main__":
    main()
