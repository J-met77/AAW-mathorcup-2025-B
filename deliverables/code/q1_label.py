# -*- coding: utf-8 -*-
"""
q1_label.py — A4/A6 交付：问题1 风险标注模型
方法：实赔分位分层 → 层内超额索赔额 x 的密度谷值切分 → 幂律阈值曲线 T_k(y)=a_k·y^{b_k} → 软约束校验
产出：
  output/tables/q1_thresholds.csv          阈值曲线参数与约束校验
  output/tables/q1_stratum_cuts.csv        分层切点表
  output/tables/q1_label_distribution.csv  附件1 标注分布
  output/tables/q1_label_crosstab.csv      标注×业务字段交叉分析
  output/tables/q1_method_compare.csv      四种候选方案对比
  output/tables/q1_rule_params.json        规则参数（q3 复用）
  output/data/q1_附件1_标注.csv            附件1 标注结果
运行：python code/q1_label.py
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CLEAN, OUT, TBL

TBL.mkdir(parents=True, exist_ok=True)
LOGF = OUT / "logs" / "q1_label.log"
LOGF.parent.mkdir(parents=True, exist_ok=True)


def log(msg: str):
    print(msg)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


K = 10  # 实赔等频分层层数


def valley_depth(logx: np.ndarray, cut: float, half: int = 8, bins: int = 60) -> float:
    """切点处谷深：切点箱平滑密度 / 两侧邻域峰值密度。∈(0,1]，越小谷越深。"""
    if not np.isfinite(cut) or len(logx) < 30:
        return np.nan
    lo, hi = np.log(np.clip(logx, 1e-6, None).min()), np.log(logx.max())
    if hi <= lo:
        return np.nan
    lcut = np.log(cut)
    h, edges = np.histogram(np.log(logx), bins=bins, range=(lo, hi))
    k = np.convolve(h, np.array([1, 2, 1]) / 4.0, mode="same")
    b = int(np.clip(np.searchsorted(edges, lcut) - 1, 0, bins - 1))
    lp = k[max(0, b - half):b].max() if b > 0 else 0.0
    rp = k[b + 1:min(bins, b + 1 + half)].max() if b < bins - 1 else 0.0
    denom = max(lp, rp, 1.0)
    return float(min(1.0, k[b] / denom))


def fit_power(y_med: np.ndarray, cuts: np.ndarray):
    """log-log OLS：T(y)=a·y^b。"""
    m = np.isfinite(cuts) & (cuts > 0) & (y_med > 0)
    if m.sum() < 3:
        return np.nan, np.nan, np.nan
    A = np.vstack([np.log(y_med[m]), np.ones(m.sum())]).T
    coef, res, *_ = np.linalg.lstsq(A, np.log(cuts[m]), rcond=None)
    b, loga = coef
    pred = A @ coef
    ss_res = float(np.sum((np.log(cuts[m]) - pred) ** 2))
    ss_tot = float(np.sum((np.log(cuts[m]) - np.log(cuts[m]).mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return float(np.exp(loga)), float(b), r2


def label_by_curve(y: np.ndarray, x: np.ndarray, a1, b1, a2, b2):
    t1, t2 = a1 * np.power(y, b1), a2 * np.power(y, b2)
    return np.where(x <= t1, "合理诉求", np.where(x <= t2, "诉求偏高", "严重超额"))


def main():
    df = pd.read_csv(CLEAN / "clean_附件1.csv")
    y = df["payment_real"].values.astype(float)
    x = df["over_claim"].values.astype(float)
    r = df["over_ratio"].values.astype(float)
    n = len(df)
    log(f"载入 clean_附件1: {n} 条; y∈[{y.min():.2f},{y.max():.2f}], x∈[{x.min():.2f},{x.max():.2f}]")

    strata = pd.qcut(y, K, labels=False, duplicates="drop")
    K_eff = int(strata.max()) + 1
    log(f"实赔等频分层 K={K_eff}")
    y_med_k = np.array([np.median(y[strata == k]) for k in range(K_eff)])

    # ---- 网格搜索 (q1,q2)：软约束可行域内最大化平均谷深 ----
    grid_q1 = np.round(np.arange(0.845, 0.906, 0.005), 4)
    grid_q2 = np.round(np.arange(0.960, 0.986, 0.0025), 4)
    results, detail = [], {}
    for q1 in grid_q1:
        for q2 in grid_q2:
            c1 = np.array([np.quantile(x[strata == k], q1) for k in range(K_eff)])
            c2 = np.array([np.quantile(x[strata == k], q2) for k in range(K_eff)])
            a1, b1, r21 = fit_power(y_med_k, c1)
            a2, b2, r22 = fit_power(y_med_k, c2)
            if not all(np.isfinite([a1, b1, a2, b2])) or a2 <= a1 * 0.2:
                continue
            lab = label_by_curve(y, x, a1, b1, a2, b2)
            p_ok = float((lab == "合理诉求").mean())
            p_bad = float((lab == "严重超额").mean())
            if p_ok < 0.85 or p_bad >= 0.03:      # 软约束（题面）
                continue
            d1 = np.array([valley_depth(x[strata == k], c1[k]) for k in range(K_eff)])
            d2 = np.array([valley_depth(x[strata == k], c2[k]) for k in range(K_eff)])
            depth = float(np.nanmean(np.r_[d1, d2]))
            results.append({"q1": q1, "q2": q2, "a1": a1, "b1": b1, "a2": a2, "b2": b2,
                            "p_ok": p_ok, "p_mid": float((lab == "诉求偏高").mean()),
                            "p_bad": p_bad, "depth": depth, "r2_1": r21, "r2_2": r22})
            detail[(q1, q2)] = (c1, c2, d1, d2)
    if not results:
        raise RuntimeError("无可行 (q1,q2)，需放宽网格")
    res = pd.DataFrame(results).sort_values("depth")
    best = res.iloc[0]
    log(f"\n可行组合 {len(res)} 个；选择谷深最小（谷最深）: q1={best.q1}, q2={best.q2}, "
        f"depth={best.depth:.3f}, 占比 合理={best.p_ok:.4f} 偏高={best.p_mid:.4f} 严重={best.p_bad:.4f}")
    log(f"阈值曲线: T1(y)={best.a1:.3f}·y^{best.b1:.4f} (R²={best.r2_1:.4f}); "
        f"T2(y)={best.a2:.3f}·y^{best.b2:.4f} (R²={best.r2_2:.4f})")
    log(f"谷深 Top5 候选:\n{res.head(5).to_string(index=False)}")

    a1, b1, a2, b2 = float(best.a1), float(best.b1), float(best.a2), float(best.b2)
    label = label_by_curve(y, x, a1, b1, a2, b2)

    # ---- 阈值参数与校验 ----
    pd.DataFrame([{
        "q1": best.q1, "q2": best.q2,
        "T1_a": a1, "T1_b": b1, "T1_R2": best.r2_1,
        "T2_a": a2, "T2_b": b2, "T2_R2": best.r2_2,
        "平均谷深": best.depth,
        "占比_合理诉求": best.p_ok, "占比_诉求偏高": best.p_mid, "占比_严重超额": best.p_bad,
        "约束_合理≥85%": "通过" if best.p_ok >= 0.85 else "不通过",
        "约束_严重<3%": "通过" if best.p_bad < 0.03 else "不通过",
        "阈值随y递增": "通过" if (b1 > 0 and b2 > 0 and (a2 * y.max() ** b2) > (a1 * y.max() ** b1)) else "不通过",
    }]).to_csv(TBL / "q1_thresholds.csv", index=False, encoding="utf-8-sig")
    with open(TBL / "q1_rule_params.json", "w", encoding="utf-8") as f:
        json.dump({"a1": a1, "b1": b1, "a2": a2, "b2": b2,
                   "q1": float(best.q1), "q2": float(best.q2),
                   "rule": "x<=T1(y):合理诉求; T1(y)<x<=T2(y):诉求偏高; x>T2(y):严重超额; T_k(y)=a_k*y^b_k"},
                  f, ensure_ascii=False, indent=2)

    # ---- 分层切点表 ----
    c1, c2, d1, d2 = detail[(best.q1, best.q2)]
    rows = []
    for k in range(K_eff):
        m = strata == k
        lab_k = label[m]
        rows.append({
            "层": k + 1, "y区间": f"[{y[m].min():.2f}, {y[m].max():.2f}]", "y中位": round(y_med_k[k], 2),
            "n": int(m.sum()), "层内x_中位": round(float(np.median(x[m])), 1),
            "切点1(分位)": round(c1[k], 1), "拟合T1(y)": round(a1 * y_med_k[k] ** b1, 1),
            "谷深1": round(d1[k], 3),
            "切点2(分位)": round(c2[k], 1), "拟合T2(y)": round(a2 * y_med_k[k] ** b2, 1),
            "谷深2": round(d2[k], 3),
            "合理占比": round(float((lab_k == "合理诉求").mean()), 4),
            "严重占比": round(float((lab_k == "严重超额").mean()), 4),
        })
    cuts_df = pd.DataFrame(rows)
    cuts_df.to_csv(TBL / "q1_stratum_cuts.csv", index=False, encoding="utf-8-sig")
    log("\n分层切点表:\n" + cuts_df.to_string(index=False))

    # ---- 附件1 标注结果 ----
    out = pd.DataFrame({
        "行序": np.arange(1, n + 1), "实际赔付金额": y, "索赔金额": df["claim_amount"].values,
        "超额索赔额x": x, "相对超额率r": r, "实赔分层": strata + 1,
        "风险标注": label,
    })
    out.to_csv(CLEAN / "q1_附件1_标注.csv", index=False, encoding="utf-8-sig")

    dist = pd.Series(label).value_counts().reindex(["合理诉求", "诉求偏高", "严重超额"])
    dist_df = pd.DataFrame({"风险标注": dist.index, "运单数": dist.values,
                            "占比": (dist.values / n).round(4)})
    dist_df.to_csv(TBL / "q1_label_distribution.csv", index=False, encoding="utf-8-sig")
    log("\n附件1 标注分布:\n" + dist_df.to_string(index=False))

    # ---- 业务交叉分析 ----
    ana = df[["abnormal_reason", "goods_category", "bc_source", "over_ratio"]].copy()
    ana["label"] = label; ana["x"] = x; ana["y"] = y
    ct = ana.groupby("label").agg(n=("x", "size"), x中位=("x", "median"), r中位=("over_ratio", "median"))
    # 更直观：按异常原因/商品类型给严重超额浓度
    for col in ["abnormal_reason", "goods_category"]:
        g = ana.groupby(col)["label"].apply(lambda s: (s == "严重超额").mean()).sort_values(ascending=False)
        log(f"\n各[{col}]的严重超额浓度(Top5):\n{g.head(5).round(4).to_string()}")
    crosstab = pd.crosstab(ana["abnormal_reason"], ana["label"], normalize="index").round(4)
    crosstab.to_csv(TBL / "q1_label_crosstab.csv", encoding="utf-8-sig")
    log("\n异常原因×标注(行归一):\n" + crosstab.to_string())

    # ---- 四种候选方案对比 ----
    def stats(lab, name, cuts_pair=None):
        """cuts_pair=(cuts1_arr, cuts2_arr) 为各层切点（曲线法用拟合值），用于计算层内谷深均值。"""
        per_ok = pd.Series(lab).groupby(strata).apply(lambda s: (s == "合理诉求").mean())
        if cuts_pair is not None:
            dd = []
            for k in range(K_eff):
                m = strata == k
                dd += [valley_depth(x[m], cuts_pair[0][k]), valley_depth(x[m], cuts_pair[1][k])]
            depth = float(np.nanmean(dd))
        else:
            depth = np.nan
        return {"方案": name,
                "合理占比": round(float((lab == "合理诉求").mean()), 4),
                "诉求偏高占比": round(float((lab == "诉求偏高").mean()), 4),
                "严重超额占比": round(float((lab == "严重超额").mean()), 4),
                "约束满足": "是" if ((lab == "合理诉求").mean() >= .85 and (lab == "严重超额").mean() < .03) else "否",
                "平均谷深↓": round(depth, 3) if np.isfinite(depth) else None,
                "层间合理占比极差↓": round(float(per_ok.max() - per_ok.min()), 4),
                "与方案D一致率": round(float((lab == label).mean()), 4)}

    t1_all, t2_all = a1 * np.power(y, b1), a2 * np.power(y, b2)
    cmp_rows = []
    lab_gx = np.where(x <= np.quantile(x, best.q1), "合理诉求",
                      np.where(x <= np.quantile(x, best.q2), "诉求偏高", "严重超额"))
    g1, g2 = np.quantile(x, best.q1), np.quantile(x, best.q2)
    cmp_rows.append(stats(lab_gx, "A: 全局x分位阈值(忽略实赔差异)",
                          cuts_pair=(np.full(K_eff, g1), np.full(K_eff, g2))))
    # 常数 r 阈值 → 等价于 x = θ·y，层内切点用 y 中位近似
    th1, th2 = np.quantile(r, best.q1), np.quantile(r, best.q2)
    lab_gr = np.where(r <= th1, "合理诉求", np.where(r <= th2, "诉求偏高", "严重超额"))
    cmp_rows.append(stats(lab_gr, "B: 全局常数相对超额率阈值",
                          cuts_pair=(np.full(K_eff, th1 * y_med_k), np.full(K_eff, th2 * y_med_k))))
    lab_st = np.empty(n, dtype=object)
    for k in range(K_eff):
        m = strata == k
        lab_st[m] = np.where(x[m] <= c1[k], "合理诉求", np.where(x[m] <= c2[k], "诉求偏高", "严重超额"))
    cmp_rows.append(stats(lab_st, "C: 分层分位切分(无平滑曲线)", cuts_pair=(c1, c2)))
    cmp_rows.append(stats(label, "D: 本文 幂律阈值曲线+谷值选择",
                          cuts_pair=(np.array([a1 * y_med_k[k] ** b1 for k in range(K_eff)]),
                                     np.array([a2 * y_med_k[k] ** b2 for k in range(K_eff)]))))
    cmp_df = pd.DataFrame(cmp_rows)
    cmp_df.to_csv(TBL / "q1_method_compare.csv", index=False, encoding="utf-8-sig")
    log("\n方案对比(谷深越小切分越落在密度谷; 极差越小层间越均衡):\n" + cmp_df.to_string(index=False))

    log("\n== Q1 标注模型完成 ==")


if __name__ == "__main__":
    main()
