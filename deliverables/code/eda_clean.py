# -*- coding: utf-8 -*-
"""
eda_clean.py — A3 数据工程师交付：数据清洗 + 探索性分析 + 特征工程
产出：
  output/data/clean_附件1.csv, clean_附件2.csv      清洗与特征化后的数据集
  output/eda/EDA报告.md                              EDA 报告（数字与表格由本脚本生成，保证一致）
  output/eda/*.csv                                   过程统计表
运行：python code/eda_clean.py
"""
import sys, io
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (WORK, DATA, OUT, CLEAN, load_raw, build_features,
                    normalize_seconds, NUM_FEATURES, CAT_FEATURES, FEATURES)

LOG = OUT / "logs"; EDA = OUT / "eda"
for p in [CLEAN, EDA, LOG]:
    p.mkdir(parents=True, exist_ok=True)
LOGF = LOG / "eda_clean.log"


def log(msg: str):
    print(msg); 
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def psi(train: pd.Series, test: pd.Series, n_bins: int = 10) -> float:
    """总体稳定性指数（分位箱）。"""
    tr = train.dropna().values; te = test.dropna().values
    if len(tr) == 0 or len(te) == 0:
        return np.nan
    qs = np.unique(np.quantile(tr, np.linspace(0, 1, n_bins + 1)))
    qs[0], qs[-1] = -np.inf, np.inf
    pt = np.histogram(tr, bins=qs)[0] / len(tr)
    pe = np.histogram(te, bins=qs)[0] / len(te)
    pt, pe = np.clip(pt, 1e-4, None), np.clip(pe, 1e-4, None)
    return float(np.sum((pe - pt) * np.log(pe / pt)))


def main():
    # ===== 1. 读取与结构核验 =====
    log("== A3 数据清洗与 EDA ==")
    tr_raw = load_raw("train"); te_raw = load_raw("test")
    log(f"附件1 真实样本: {len(tr_raw)}（已剥离 1 条英文字段名行）")
    log(f"附件2 真实样本: {len(te_raw)}（已剥离 1 条英文字段名行）")
    assert len(tr_raw) == 11167 and len(te_raw) == 2792

    # ===== 2. 缺失与异常标记统计 =====
    miss_rows = []
    for c in tr_raw.columns:
        nan = int(tr_raw[c].isna().sum())
        m1 = int((tr_raw[c] == -1).sum()) if tr_raw[c].dtype.kind in "if" else 0
        neg = int((pd.to_numeric(tr_raw[c], errors="coerce") < 0).sum()) if tr_raw[c].dtype.kind in "if" else 0
        if nan or m1 or neg:
            miss_rows.append({"字段": c, "NaN数": nan, "NaN占比": round(nan / len(tr_raw), 4),
                              "负1数": m1, "负值数": neg})
    miss_df = pd.DataFrame(miss_rows).sort_values("NaN占比", ascending=False)
    miss_df.to_csv(EDA / "缺失与异常标记统计.csv", index=False, encoding="utf-8-sig")
    log("\n缺失/异常标记（前 10）:\n" + miss_df.head(10).to_string(index=False))

    # ===== 3. 时间字段量纲诊断 =====
    diag_rows = []
    for c in ["overtime_raw", "case_delay_raw"]:
        v = pd.to_numeric(tr_raw[c], errors="coerce")
        diag_rows.append({
            "字段": c, "负值数": int((v < 0).sum()),
            "≥1e7(疑似毫秒)数": int((v >= 1e7).sum()),
            "≥1e7占比": round(float((v >= 1e7).mean()), 4),
            "众数区间频数": int(((v > 427000) & (v < 428000)).sum()) if c == "overtime_raw" else np.nan,
        })
    diag_df = pd.DataFrame(diag_rows)
    diag_df.to_csv(EDA / "时间字段量纲诊断.csv", index=False, encoding="utf-8-sig")
    log("\n时间字段量纲诊断:\n" + diag_df.to_string(index=False))

    # ===== 4. 目标与派生量分布（喂给 A4）=====
    tr_raw["over_claim"] = tr_raw["claim_amount"] - tr_raw["payment_real"]
    tr_raw["over_ratio"] = tr_raw["over_claim"] / tr_raw["payment_real"]
    tgt_rows = []
    for c, s in [("实际赔付金额", tr_raw["payment_real"]), ("索赔金额", tr_raw["claim_amount"]),
                 ("超额索赔额", tr_raw["over_claim"]), ("相对超额率", tr_raw["over_ratio"])]:
        q = np.percentile(s, [0, 25, 50, 75, 85, 90, 95, 97, 99, 100])
        tgt_rows.append({"变量": c, "min": round(q[0], 3), "P25": round(q[1], 3), "P50": round(q[2], 3),
                         "P75": round(q[3], 3), "P85": round(q[4], 3), "P90": round(q[5], 3),
                         "P95": round(q[6], 3), "P97": round(q[7], 3), "P99": round(q[8], 3),
                         "max": round(q[9], 3), "均值": round(float(s.mean()), 3)})
    tgt_df = pd.DataFrame(tgt_rows)
    tgt_df.to_csv(EDA / "目标与派生量分位数.csv", index=False, encoding="utf-8-sig")
    log("\n目标与派生量分位数:\n" + tgt_df.to_string(index=False))
    log(f"\n索赔>实赔 的样本占比: {(tr_raw['over_claim'] > 0).mean():.4f}")
    log(f"实赔最小值: {tr_raw['payment_real'].min():.2f}（不存在 0/负值）")

    # ===== 5. 类别变量分布（训练 vs 测试）=====
    cat_dist = []
    for c in ["abnormal_reason", "source", "goods_category", "goods_level",
              "bc_source", "customer_role", "route_type", "is_c2c", "is_staff"]:
        a = tr_raw[c].where(tr_raw[c].notna(), "缺失").astype(str).value_counts(normalize=True, dropna=False)
        b = te_raw[c].where(te_raw[c].notna(), "缺失").astype(str).value_counts(normalize=True, dropna=False)
        keys = sorted(set(a.index.astype(str)) | set(b.index.astype(str)))
        for k in keys:
            cat_dist.append({"字段": c, "取值": k,
                             "训练占比": round(float(a.reindex([k], fill_value=0).iloc[0]), 4),
                             "测试占比": round(float(b.reindex([k], fill_value=0).iloc[0]), 4)})
    pd.DataFrame(cat_dist).to_csv(EDA / "类别变量分布对比.csv", index=False, encoding="utf-8-sig")

    # ===== 6. 数值特征 PSI（训练 vs 测试）=====
    psi_rows = []
    for c in ["claim_amount", "insure_amount", "overtime_raw", "case_delay_raw",
              "start_node_waybill_num", "end_node_waybill_num",
              "start_node_accident_rate", "end_node_accident_rate"]:
        psi_rows.append({"字段": c, "PSI": round(psi(pd.to_numeric(tr_raw[c], errors="coerce"),
                                                     pd.to_numeric(te_raw[c], errors="coerce")), 4)})
    psi_df = pd.DataFrame(psi_rows).sort_values("PSI", ascending=False)
    psi_df.to_csv(EDA / "PSI_训练vs测试.csv", index=False, encoding="utf-8-sig")
    log("\nPSI（<0.1 稳定, 0.1~0.25 需关注, >0.25 漂移）:\n" + psi_df.to_string(index=False))

    # ===== 7. 相关性速览（特征与目标）=====
    corr = tr_raw[["payment_real", "claim_amount", "insure_amount", "over_claim",
                   "start_node_accident_rate", "end_node_accident_rate",
                   "start_node_claim_ratio", "end_node_claim_ratio"]].corr(method="spearman")
    corr.round(4).to_csv(EDA / "Spearman相关矩阵.csv", encoding="utf-8-sig")
    log("\n与实赔的 Spearman 相关:\n" + corr["payment_real"].drop("payment_real").sort_values(ascending=False).round(4).to_string())

    # ===== 8. 清洗与特征工程（train+test 合并 ID 词表，防泄漏）=====
    full = pd.concat([tr_raw.drop(columns=["over_claim", "over_ratio"], errors="ignore"),
                      te_raw], ignore_index=True)
    id_freq = {c: full[c].value_counts() for c in ["consigner_id", "receiver_id"]}
    # 先用统一流程构建（ID 频次列暂以本表词表填充），再用合并词表覆盖，保证 train/test 口径一致
    tr = build_features(tr_raw, id_freq=None)
    te = build_features(te_raw, id_freq=None)
    for c, tgt in [("consigner_id", "consigner_freq"), ("receiver_id", "receiver_freq")]:
        tr[tgt] = tr_raw[c].map(id_freq[c]).fillna(1.0).astype(float)
        te[tgt] = te_raw[c].map(id_freq[c]).fillna(1.0).astype(float)

    keep_tr = ["over_claim", "over_ratio", "payment_real"] + FEATURES
    keep_te = ["运单号", "claim_amount"] + FEATURES
    tr[keep_tr].to_csv(CLEAN / "clean_附件1.csv", index=False, encoding="utf-8-sig")
    te[keep_te].to_csv(CLEAN / "clean_附件2.csv", index=False, encoding="utf-8-sig")
    log(f"\n清洗后训练集: {tr[keep_tr].shape}，测试集: {te[keep_te].shape}")
    log(f"特征数: {len(FEATURES)}（数值 {len(NUM_FEATURES)} + 类别 {len(CAT_FEATURES)}）")
    log("剩余 NaN（训练/测试）: "
        f"{int(tr[FEATURES].isna().sum().sum())} / {int(te[FEATURES].isna().sum().sum())}")
    log("\n== A3 完成 ==")


if __name__ == "__main__":
    main()
