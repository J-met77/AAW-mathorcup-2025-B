# -*- coding: utf-8 -*-
"""
fill_result.py — A6 交付：填写 Result.xlsx（问题2 实际赔付金额 + 问题3 风险标注）
硬校验（决策 D08）：
  1) 行数必须 2792；2) 运单号与原模板逐行一致（1..2792 顺序不变）；
  3) 风险标注 ∈ {合理诉求, 诉求偏高, 严重超额}；4) 实际赔付金额 ≥ 0 且无缺失。
写出：workspace data/Result.xlsx（覆盖副本）+ output/Result_提交.xlsx
注意：绝不改动用户桌面 C:\\Users\\21732\\Desktop\\Result.xlsx（决策 D02）。
运行：python code/fill_result.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import WORK, DATA, CLEAN, OUT, LABELS

LOGF = OUT / "logs" / "fill_result.log"


def log(msg):
    print(msg)
    with open(LOGF, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    tpl = pd.read_excel(DATA / "Result.xlsx")
    q2 = pd.read_csv(CLEAN / "q2_附件2_预测.csv")
    q3 = pd.read_csv(CLEAN / "q3_附件2_预测.csv")
    log(f"模板: {tpl.shape}, 列={list(tpl.columns)}")

    # ---- 前置校验：中间产物与模板对齐 ----
    assert len(tpl) == 2792 and len(q2) == 2792 and len(q3) == 2792, "行数必须 2792"
    assert (tpl["运单号"].values == q2["运单号"].values).all(), "q2 运单号与模板不一致"
    assert (tpl["运单号"].values == q3["运单号"].values).all(), "q3 运单号与模板不一致"
    assert (q3["pred_a"].values == q3["pred_b"].values).sum() >= 0

    out = tpl.copy()
    out["实际赔付金额"] = np.round(q2["pred_payment"].values.astype(float), 2)
    out["风险标注"] = q3["final_label"].values

    # ---- 硬校验 ----
    errs = []
    if len(out) != 2792:
        errs.append(f"行数 {len(out)} ≠ 2792")
    if not (out["运单号"].values == tpl["运单号"].values).all():
        errs.append("运单号顺序被改动")
    if not out["运单号"].astype(int).equals(pd.Series(range(1, 2793), name="运单号")):
        errs.append("运单号非 1..2792 顺序序列")
    bad_lab = set(out["风险标注"].unique()) - set(LABELS)
    if bad_lab:
        errs.append(f"非法标签: {bad_lab}")
    if out["实际赔付金额"].isna().any():
        errs.append("实际赔付金额存在缺失")
    if (out["实际赔付金额"] < 0).any():
        errs.append("实际赔付金额存在负值")
    if errs:
        raise RuntimeError("硬校验失败: " + "; ".join(errs))
    log("硬校验: 行数 2792 ✓ 运单号 1..2792 顺序不变 ✓ 标签三值合法 ✓ 金额非负无缺失 ✓")

    # ---- 写出（不动用户桌面原文件，决策 D02）----
    out.to_excel(DATA / "Result.xlsx", index=False)
    out.to_excel(OUT / "Result_提交.xlsx", index=False)
    log("已写出: data/Result.xlsx（工作区副本）与 output/Result_提交.xlsx")

    dist = out["风险标注"].value_counts(normalize=True).reindex(LABELS)
    log("\n提交分布:\n" + dist.round(4).to_string())
    log(f"实际赔付金额: min={out['实际赔付金额'].min():.2f} 中位={out['实际赔付金额'].median():.2f} "
        f"max={out['实际赔付金额'].max():.2f} 均值={out['实际赔付金额'].mean():.2f}")
    log("\n前 5 行预览:\n" + out.head(5).to_string(index=False))
    log("== fill_result 完成 ==")


if __name__ == "__main__":
    main()
