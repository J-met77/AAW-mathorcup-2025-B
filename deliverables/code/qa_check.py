# -*- coding: utf-8 -*-
"""
qa_check.py — A11 终审质检（只读核查，不修改任何交付物）
检查项：
  C1  Result_提交.xlsx 结构/运单号/标签/金额合法性；与 data/Result.xlsx 一致
  C2  用户桌面 Result.xlsx 未被改动（仍为空模板）
  C3  代码可复跑性：全部脚本 py_compile 通过 + eda_clean 重跑结果一致
  C4  关键数字一致性：标注分布/OOF 指标/混淆矩阵行列守恒
  C5  论文数字与表格一致（抽查锚点数字）
  C6  论文图表引用完整（链接文件存在）
  C7  必答论述存在（不均衡处理 / 两路线优劣势）
  C8  提交分布软约束（合理≥85%，严重<3%）
产出：output/logs/qa_report.md；全部通过时退出码 0
运行：python code/qa_check.py
"""
import sys, py_compile, re, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import WORK, DATA, CLEAN, TBL, OUT, LABELS, smape

CODE = WORK / "code"
PAPER = WORK / "paper" / "论文.md"
DESKTOP = Path(r"C:/Users/21732/Desktop/Result.xlsx")
REPORT = OUT / "logs" / "qa_report.md"

issues, passes = [], []


def check(cid, name, ok, detail=""):
    (passes if ok else issues).append(f"[{cid}] {name} — {'PASS' if ok else 'FAIL'} {detail}".rstrip())


def main():
    # ===== C1 Result_提交.xlsx =====
    sub = pd.read_excel(OUT / "Result_提交.xlsx")
    tpl = pd.read_excel(DATA / "Result.xlsx")
    check("C1.1", "行数=2792", len(sub) == 2792, f"(实际 {len(sub)})")
    check("C1.2", "列名与顺序", list(sub.columns) == ["运单号", "实际赔付金额", "风险标注"], str(list(sub.columns)))
    check("C1.3", "运单号=1..2792 顺序不变",
          sub["运单号"].tolist() == list(range(1, 2793)) and sub["运单号"].tolist() == tpl["运单号"].tolist())
    check("C1.4", "风险标注三值合法", set(sub["风险标注"]) <= set(LABELS), str(set(sub["风险标注"])))
    pay = sub["实际赔付金额"]
    check("C1.5", "金额非负、无缺失、数值型",
          pay.notna().all() and (pay >= 0).all() and pd.api.types.is_numeric_dtype(pay),
          f"min={pay.min()}, max={pay.max()}")
    check("C1.6", "与工作区 data/Result.xlsx 一致",
          sub.equals(tpl.rename(columns={})) or
          (sub.values.tolist() == tpl.values.tolist()))

    # ===== C2 桌面原文件未动 =====
    if DESKTOP.exists():
        d = pd.read_excel(DESKTOP)
        untouched = (d["实际赔付金额"].isna().all() and d["风险标注"].isna().all()
                     and d["运单号"].tolist() == list(range(1, 2793)))
        check("C2", "桌面 Result.xlsx 仍为未填写模板（未被改动）", untouched)
    else:
        check("C2", "桌面 Result.xlsx 不存在（未创建、未改动）", True)

    # ===== C3 代码可复跑 =====
    scripts = ["common.py", "eda_clean.py", "q1_label.py", "q2_reg.py", "q3_clf.py",
               "fill_result.py", "q_sensitivity.py", "plots.py", "qa_check.py"]
    ok = True
    for s in scripts:
        try:
            py_compile.compile(str(CODE / s), doraise=True)
        except Exception as e:
            ok = False
            issues.append(f"[C3] 编译失败 {s}: {e}")
    check("C3.1", "全部脚本语法可编译", ok)
    # eda_clean 重跑一致性（重建文件后对比哈希）
    h_before = {f.name: hashlib.md5(f.read_bytes()).hexdigest()
                for f in [CLEAN / "clean_附件1.csv", CLEAN / "clean_附件2.csv"]}
    import subprocess
    subprocess.run([sys.executable, str(CODE / "eda_clean.py")], check=True,
                   capture_output=True, cwd=str(WORK))
    h_after = {f.name: hashlib.md5(f.read_bytes()).hexdigest()
               for f in [CLEAN / "clean_附件1.csv", CLEAN / "clean_附件2.csv"]}
    check("C3.2", "eda_clean.py 重跑输出逐字节一致", h_before == h_after, str(h_after))

    # ===== C4 关键数字一致性 =====
    lab = pd.read_csv(CLEAN / "q1_附件1_标注.csv")
    dist = lab["风险标注"].value_counts()
    dist_tbl = pd.read_csv(TBL / "q1_label_distribution.csv").set_index("风险标注")["运单数"]
    check("C4.1", "q1 标注分布表与标注数据一致",
          all(int(dist[l]) == int(dist_tbl[l]) for l in LABELS),
          f"{dict(dist)}")
    oof = pd.read_csv(CLEAN / "q2_附件1_OOF.csv")
    s = round(smape(oof["payment_real"], oof["oof_pred"]), 4)
    check("C4.2", "q2 OOF SMAPE 可复算=0.4324", abs(s - 0.4324) < 5e-4, f"复算值 {s}")
    cm = pd.read_csv(TBL / "q3_confusion_a.csv", index_col=0).values
    true_cnt = lab["风险标注"].value_counts().reindex(LABELS).values
    check("C4.3", "q3 混淆矩阵行和=真实类数", (cm.sum(axis=1) == true_cnt).all(),
          f"行和={cm.sum(axis=1).tolist()}, 真实={true_cnt.tolist()}")
    q3sub = pd.read_csv(CLEAN / "q3_附件2_预测.csv")
    check("C4.4", "q3 提交标签与 Result 一致",
          (q3sub["final_label"].values == sub["风险标注"].values).all())
    q2sub = pd.read_csv(CLEAN / "q2_附件2_预测.csv")
    check("C4.5", "q2 提交金额与 Result 一致",
          np.allclose(q2sub["pred_payment"].values, pay.values, atol=0.005))

    # ===== C5 论文数字抽查 =====
    paper = PAPER.read_text(encoding="utf-8")
    anchors = {"0.4324": True, "0.6398": True, "0.5806": True, "89.34": True,
               "1.34": True, "9977": True, "1040": True, "150": True,
               "53.958": True, "129.648": True, "0.5602": True, "0.4945": True,
               "96.04": True, "142.31": True, "0.3286": True}
    miss = [k for k in anchors if k not in paper]
    check("C5", "论文包含全部锚点数字", not miss, f"缺失: {miss}" if miss else "")

    # ===== C6 图表引用 =====
    figs = re.findall(r"\]\((\.\./output/figures/[^)]+)\)", paper)
    missing = [f for f in figs if not (WORK / "paper" / f).resolve().exists()]
    check("C6.1", f"论文引用 {len(figs)} 张图全部存在", not missing, f"缺失: {missing}" if missing else "")
    figfiles = list((OUT / "figures").glob("fig*.png"))
    check("C6.2", "figures 目录含 ≥10 张图", len(figfiles) >= 10, f"实际 {len(figfiles)}")

    # ===== C7 必答论述 =====
    check("C7.1", "含严重不均衡处理论述",
          all(k in paper for k in ["class weight", "SMOTE", "Focal Loss", "阈值校正"]))
    check("C7.2", "含两路线优劣势论述",
          all(k in paper for k in ["直接分类", "先回归后标注", "优势", "劣势"]))

    # ===== C8 提交分布软约束 =====
    d = sub["风险标注"].value_counts(normalize=True)
    p_ok, p_bad = float(d.get(LABELS[0], 0)), float(d.get(LABELS[2], 0))
    check("C8", f"软约束：合理诉求 {p_ok:.4f}≥0.85 且 严重超额 {p_bad:.4f}<0.03",
          p_ok >= 0.85 and p_bad < 0.03)

    # ===== 报告 =====
    verdict = "终审通过" if not issues else "存在 FAIL，需打回修复"
    lines = ["# QA 终审报告（A11，只读核查）", "",
             f"- 结论：**{verdict}**", f"- 通过 {len(passes)} 项 / 失败 {len(issues)} 项", ""]
    lines += ["## 通过项"] + [f"- {p}" for p in passes]
    if issues:
        lines += ["", "## 失败项"] + [f"- {i}" for i in issues]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    sys.exit(0 if not issues else 1)


if __name__ == "__main__":
    main()
