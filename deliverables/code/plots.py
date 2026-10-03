# -*- coding: utf-8 -*-
"""
plots.py — A8 交付：论文级图表（中文 Microsoft YaHei，300dpi PNG）
产出：output/figures/fig1~fig11.png
运行：python code/plots.py
"""
import sys, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CLEAN, TBL, OUT, LABELS

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
C3 = ["#2e7d32", "#f9a825", "#c62828"]  # 合理/偏高/严重


def log(msg):
    print(msg)


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    log(f"  生成 {name}")


def main():
    lab = pd.read_csv(CLEAN / "q1_附件1_标注.csv")
    prm = json.load(open(TBL / "q1_rule_params.json", encoding="utf-8"))
    y = lab["实际赔付金额"].values
    c = lab["索赔金额"].values
    x = lab["超额索赔额x"].values
    lb = lab["风险标注"].values
    colors = np.array([C3[list(LABELS).index(l)] for l in lb])

    # ---- fig1 目标与派生量分布 ----
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    axes[0].hist(np.log10(y), bins=60, color="#1f77b4", alpha=0.85)
    axes[0].set_title("实际赔付金额分布(log10尺度)")
    axes[0].set_xlabel("log10(实际赔付金额/元)"); axes[0].set_ylabel("运单数")
    axes[1].hist(np.log10(c), bins=60, color="#ff7f0e", alpha=0.85)
    axes[1].set_title("索赔金额分布(log10尺度)")
    axes[1].set_xlabel("log10(索赔金额/元)")
    r = lab["相对超额率r"].values
    axes[2].hist(np.log10(r), bins=80, color="#d62728", alpha=0.85)
    axes[2].set_title("相对超额率 r=(索赔−实赔)/实赔")
    axes[2].set_xlabel("log10(r)")
    save(fig, "fig1_目标与派生量分布.png")

    # ---- fig2 时间字段量纲 ----
    raw = pd.read_excel(OUT.parent / "data" / "附件1.xlsx").iloc[1:]
    v = pd.to_numeric(raw["妥投到进线时长"], errors="coerce").values
    v = v[np.isfinite(v) & (v > 0)]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    axes[0].hist(np.log10(v), bins=80, color="#9467bd", alpha=0.85)
    axes[0].axvline(7, color="r", ls="--", lw=1.5, label="1e7 归一化分界")
    axes[0].set_title("清洗前：妥投到进线时长(原始值,log10)")
    axes[0].set_xlabel("log10(秒, 疑似毫秒/秒混用)"); axes[0].legend()
    from common import normalize_seconds
    vn = normalize_seconds(pd.Series(v)).values
    axes[1].hist(vn / 3600, bins=80, color="#2ca02c", alpha=0.85, range=(0, 240))
    axes[1].set_title("清洗后：归一为秒→小时")
    axes[1].set_xlabel("小时"); axes[1].set_ylabel("运单数")
    save(fig, "fig2_时间字段量纲归一.png")

    # ---- fig3 Q1 规则图（核心图）----
    fig, ax = plt.subplots(figsize=(8.4, 6))
    for i in [2, 1, 0]:
        m = lb == LABELS[i]
        ax.scatter(y[m], x[m], s=5, c=C3[i], alpha=0.45, label=LABELS[i], rasterized=True)
    yy = np.linspace(y.min(), y.max(), 400)
    ax.plot(yy, prm["a1"] * yy ** prm["b1"], "k--", lw=1.8, label="T1(y)=53.96·y^0.560")
    ax.plot(yy, prm["a2"] * yy ** prm["b2"], "k-.", lw=1.8, label="T2(y)=129.65·y^0.495")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("实际赔付金额 y（元, log）"); ax.set_ylabel("超额索赔额 x = 索赔−实赔（元, log）")
    ax.set_title("问题1 风险标注规则：幂律阈值曲线切分")
    ax.legend(markerscale=2.5, loc="upper left", framealpha=0.9)
    save(fig, "fig3_标注规则阈值曲线.png")

    # ---- fig4 分层切点 ----
    cuts = pd.read_csv(TBL / "q1_stratum_cuts.csv")
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    k = cuts["层"].values
    ax.plot(k, cuts["切点1(分位)"], "o--", color="#1f77b4", label="层内分位切点 c1")
    ax.plot(k, cuts["拟合T1(y)"], "o-", color="#1f77b4", alpha=0.55, label="拟合 T1(y)")
    ax.plot(k, cuts["切点2(分位)"], "s--", color="#c62828", label="层内分位切点 c2")
    ax.plot(k, cuts["拟合T2(y)"], "s-", color="#c62828", alpha=0.55, label="拟合 T2(y)")
    ax.set_xlabel("实赔十分位层（1=最低, 10=最高）")
    ax.set_ylabel("超额索赔额切点（元）")
    ax.set_title("层内切点与幂律拟合曲线（阈值随实赔递增）")
    ax.legend(ncol=2); ax.set_yscale("log")
    save(fig, "fig4_分层切点与拟合.png")

    # ---- fig5 标注分布 ----
    dist = pd.read_csv(TBL / "q1_label_distribution.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    axes[0].bar(dist["风险标注"], dist["占比"] * 100, color=C3)
    for i, v_ in enumerate(dist["占比"] * 100):
        axes[0].text(i, v_ + 1, f"{v_:.2f}%", ha="center")
    axes[0].set_ylabel("占比 %"); axes[0].set_ylim(0, 100)
    axes[0].set_title("附件1 标注分布（合理89.34%≥85%，严重1.34%<3%）")
    grp = lab.groupby("实赔分层")["风险标注"].value_counts(normalize=True).unstack().reindex(
        columns=LABELS) * 100
    bottom = np.zeros(len(grp))
    for i, l in enumerate(LABELS):
        axes[1].bar(grp.index, grp[l], bottom=bottom, color=C3[i], label=l)
        bottom += grp[l].values
    axes[1].set_xlabel("实赔十分位层"); axes[1].set_ylabel("占比 %")
    axes[1].set_title("各实赔层的标注构成（层间稳健）"); axes[1].legend(ncol=3, loc="lower center")
    save(fig, "fig5_标注分布.png")

    # ---- fig6 Q2 OOF 预测 vs 真值 ----
    oof = pd.read_csv(CLEAN / "q2_附件1_OOF.csv")
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    axes[0].hexbin(oof["payment_real"], oof["oof_pred"], gridsize=60, cmap="Blues",
                   extent=(0, 1500, 0, 1500), mincnt=1)
    axes[0].plot([0, 1500], [0, 1500], "r--", lw=1.2)
    axes[0].set_xlabel("真实实赔 y（元）"); axes[0].set_ylabel("OOF 预测 ŷ（元）")
    axes[0].set_title("问题2 OOF 预测 vs 真值（SMAPE=0.4324）")
    res = oof["oof_pred"] - oof["payment_real"]
    axes[1].hist(res, bins=80, color="#1f77b4", alpha=0.85)
    axes[1].axvline(0, color="r", ls="--")
    axes[1].set_xlabel("残差 ŷ−y（元）"); axes[1].set_ylabel("频数")
    axes[1].set_title(f"残差分布（MAE={np.abs(res).mean():.1f} 元）")
    save(fig, "fig6_预测与残差.png")

    # ---- fig7 模型对比 + 特征重要性 ----
    cmp = pd.read_csv(TBL / "q2_model_compare.csv")
    imp = pd.read_csv(TBL / "q2_feature_importance.csv").head(15).iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.8))
    axes[0].barh(cmp["模型"], cmp["SMAPE"],
                 color=["#c62828" if i == 0 else "#90a4ae" for i in range(len(cmp))])
    for i, v_ in enumerate(cmp["SMAPE"]):
        axes[0].text(v_ + 0.003, i, f"{v_:.4f}", va="center")
    axes[0].set_xlabel("OOF SMAPE（越小越好）"); axes[0].set_title("问题2 模型对比")
    axes[1].barh(imp["特征"], imp["importance"], color="#1565c0")
    axes[1].set_xlabel("LightGBM 切分重要性（均值）"); axes[1].set_title("特征重要性 Top15")
    save(fig, "fig7_模型对比与特征重要性.png")

    # ---- fig8 Q3 混淆矩阵 ----
    cm = pd.read_csv(TBL / "q3_confusion_a.csv", index_col=0)
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    im = ax.imshow(cm.values, cmap="Reds")
    ax.set_xticks(range(3), [t[1:] for t in cm.columns])
    ax.set_yticks(range(3), [t[1:] for t in cm.index])
    for i in range(3):
        for j in range(3):
            ax.text(j, i, int(cm.values[i, j]), ha="center", va="center",
                    color="white" if cm.values[i, j] > cm.values.max() / 2 else "black")
    ax.set_title("问题3 路线a OOF 混淆矩阵")
    fig.colorbar(im, ax=ax, shrink=0.85)
    save(fig, "fig8_混淆矩阵.png")

    # ---- fig9 阈值校正敏感性 ----
    ts = pd.read_csv(TBL / "q3_threshold_search.csv")
    bmid = float(ts.iloc[0]["b_mid"])
    curve = ts[(np.abs(ts["b_mid"] - bmid) < 0.05)].sort_values("b_sev")
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    ax.plot(curve["b_sev"], curve["macro_f1"], "o-", ms=3)
    ax.axvline(-0.8, color="r", ls="--", lw=1, label="选定 b_sev=−0.8")
    ax.set_xlabel("严重超额类偏置 b_sev"); ax.set_ylabel("OOF macro-F1")
    ax.set_title("阈值校正敏感性（b_mid 固定为其最优值）"); ax.legend()
    save(fig, "fig9_阈值校正敏感性.png")

    # ---- fig10 两路线对比 ----
    rep = pd.read_csv(TBL / "q3_class_report.csv", index_col=0)
    f1a = [rep.loc[f"a_{l}", "f1-score"] for l in LABELS] + [rep.loc["a_macro avg", "f1-score"]]
    f1b = [rep.loc[f"b_{l}", "f1-score"] for l in LABELS] + [rep.loc["b_macro avg", "f1-score"]]
    names = LABELS + ["macro-F1"]
    xp = np.arange(4)
    fig, ax = plt.subplots(figsize=(8.6, 4.4))
    ax.bar(xp - 0.18, f1a, 0.36, label="路线a 直接分类(含$\\hat{x}$辅助特征)", color="#1565c0")
    ax.bar(xp + 0.18, f1b, 0.36, label="路线b 先回归后标注", color="#ef6c00")
    for i, (a_, b_) in enumerate(zip(f1a, f1b)):
        ax.text(i - 0.18, a_ + 0.01, f"{a_:.3f}", ha="center", fontsize=9)
        ax.text(i + 0.18, b_ + 0.01, f"{b_:.3f}", ha="center", fontsize=9)
    ax.set_xticks(xp, names); ax.set_ylabel("F1"); ax.set_ylim(0, 1.1)
    ax.set_title("问题3 两路线 OOF F1 对比"); ax.legend()
    save(fig, "fig10_两路线对比.png")

    # ---- fig11 外推稳健性 ----
    ex = pd.read_csv(TBL / "q2_extrapolation_check.csv")
    xp = np.arange(len(ex))
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.bar(xp - 0.18, ex["训练实赔"], 0.36, label="训练集实赔分位", color="#90a4ae")
    ax.bar(xp + 0.18, ex["附件2预测"], 0.36, label="附件2 预测分位", color="#2e7d32")
    ax.set_xticks(xp, ex["分位"]); ax.set_ylabel("金额（元）")
    ax.set_title("附件2 预测分布 vs 训练目标分布（外推检查）"); ax.legend()
    save(fig, "fig11_外推稳健性.png")

    log("== A8 图表完成 ==")


if __name__ == "__main__":
    main()
