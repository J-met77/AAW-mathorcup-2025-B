#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_to_github.py — 每小时将数模项目进度同步到 GitHub 仓库
============================================================
数据源:  C:\\Users\\21732\\Desktop\\2025b论文\\agent_workspace  (STATE.md 为唯一进度权威)
目标库:  https://github.com/J-met77/AAW-mathorcup-2025-B  (本地 C:\\Users\\21732\\AAW-mathorcup-2025-B)

每次同步做五件事:
  1. 解析 STATE.md 阶段表 -> 生成 README.md 进度仪表盘 + PROGRESS.md 台账
  2. 镜像成果: code/*.py, paper/*.md|*.docx, output/figures, tables, logs, Result_提交.xlsx
     (竞赛原始数据 附件*.xlsx 不入仓库)
  3. 复制 00_admin/task_board.md, decisions.md 到 docs/
  4. 生成 reports/YYYY-MM/YYYY-MM-DD_HHMM.md 快照 + reports/LATEST.md
  5. git add -> commit -> push (无变更则跳过)
"""
import re
import shutil
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(r"C:\Users\21732\Desktop\2025b论文\agent_workspace")
REPO = Path(r"C:\Users\21732\AAW-mathorcup-2025-B")
STATE_MD = WORKSPACE / "STATE.md"

STATUS_EMOJI = {"DONE": "✅ 完成", "IN_PROGRESS": "🔄 进行中", "PENDING": "⬜ 待开始"}
STATUS_WEIGHT = {"DONE": 1.0, "IN_PROGRESS": 0.5, "PENDING": 0.0}
REPO_URL = "https://github.com/J-met77/AAW-mathorcup-2025-B"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def parse_stage_table(state_text: str):
    """解析 STATE.md §5 阶段状态表: | 阶段 | 内容 | 状态 | 产物 |"""
    rows = []
    for line in state_text.splitlines():
        m = re.match(r"^\|\s*([GA]\d+)\s*\|\s*(.+?)\s*\|\s*(DONE|IN_PROGRESS|PENDING)\s*\|\s*(.+?)\s*\|\s*$", line)
        if m:
            rows.append({"stage": m.group(1), "content": m.group(2),
                         "status": m.group(3), "artifacts": m.group(4)})
    return rows


def extract_section(state_text: str, header_pattern: str) -> str:
    """提取 STATE.md 中某个 '## n. 标题' 小节原文（到下一个 ## 为止）"""
    pat = re.compile(rf"(^{header_pattern}.*?)(?=^## |\Z)", re.M | re.S)
    m = pat.search(state_text)
    return m.group(1).strip() if m else ""


def progress_stats(rows):
    done = sum(1 for r in rows if r["status"] == "DONE")
    doing = sum(1 for r in rows if r["status"] == "IN_PROGRESS")
    pending = sum(1 for r in rows if r["status"] == "PENDING")
    pct = int(round(100 * sum(STATUS_WEIGHT[r["status"]] for r in rows) / max(len(rows), 1)))
    return done, doing, pending, pct


def current_stage(rows):
    for r in rows:
        if r["status"] == "IN_PROGRESS":
            return f"{r['stage']} {r['content']}"
    done = [r for r in rows if r["status"] == "DONE"]
    return f"{done[-1]['stage']} {done[-1]['content']}（全部阶段完成）" if done else "启动中"


def stage_table_md(rows):
    lines = ["| 阶段 | 内容 | 状态 | 产物 |", "|---|---|---|---|"]
    lines += [f"| **{r['stage']}** | {r['content']} | {STATUS_EMOJI[r['status']]} | {r['artifacts']} |" for r in rows]
    return "\n".join(lines)


def pie_chart(rows):
    done, doing, pending, _ = progress_stats(rows)
    return ("```mermaid\npie showData\n    title 任务阶段完成情况\n"
            f"    \"已完成\" : {done}\n    \"进行中\" : {doing}\n    \"待开始\" : {pending}\n```")


def mirror(src: Path, dst_dir: Path, patterns):
    if not src.is_dir():
        return []
    copied = []
    for pat in patterns:
        for f in sorted(src.glob(pat)):
            if f.is_file():
                dst_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst_dir / f.name)
                copied.append(f.name)
    return copied


def copy_deliverables() -> dict:
    d = REPO / "deliverables"
    copied = {
        "代码": mirror(WORKSPACE / "code", d / "code", ["*.py"]),
        "论文与阶段文档": mirror(WORKSPACE / "paper", d / "paper", ["*.md", "*.docx"]),
        "图表": mirror(WORKSPACE / "output" / "figures", d / "figures", ["*.png", "*.svg"]),
        "结果表格": mirror(WORKSPACE / "output" / "tables", d / "tables", ["*.csv"]),
        "日志与QA": mirror(WORKSPACE / "output" / "logs", d / "logs", ["*.md", "*.log", "*.txt"]),
        "提交结果": mirror(WORKSPACE / "output", d / "result", ["Result_提交.xlsx"]),
    }
    # Result 提交文件摘要（成果展示用，若已产出）
    result_file = WORKSPACE / "output" / "Result_提交.xlsx"
    if result_file.exists():
        try:
            import pandas as pd
            df = pd.read_excel(result_file)
            (d / "result").mkdir(parents=True, exist_ok=True)
            df.head(30).to_csv(d / "result" / "result_预览前30行.csv", index=False, encoding="utf-8-sig")
            lines = ["# Result_提交.xlsx 摘要\n",
                     f"- 总行数：**{len(df)}**\n",
                     f"- 列：{'、'.join(map(str, df.columns))}\n"]
            for col in ("风险标注",):
                if col in df.columns:
                    vc = df[col].value_counts()
                    lines.append(f"\n## {col} 分布\n\n| 取值 | 数量 | 占比 |\n|---|---|---|")
                    for k, v in vc.items():
                        lines.append(f"| {k} | {v} | {v/len(df):.2%} |")
                    lines.append("")
            for col in ("实际赔付金额",):
                if col in df.columns:
                    s = df[col]
                    lines.append(f"\n## 实际赔付金额（预测）\n\n| 统计量 | 值 |\n|---|---|\n"
                                 f"| 均值 | {s.mean():.2f} |\n| 中位数 | {s.median():.2f} |\n"
                                 f"| 最小值 | {s.min():.2f} |\n| 最大值 | {s.max():.2f} |\n")
            (d / "result" / "result_摘要.md").write_text("\n".join(lines), encoding="utf-8")
        except Exception as e:  # 摘要失败不影响同步
            print(f"[warn] Result 摘要生成失败: {e}")
    return copied


def timeline_entries(new_line: str) -> str:
    """在 PROGRESS.md 的时间线区追加（保留历史）"""
    prog = REPO / "PROGRESS.md"
    old = []
    if prog.exists():
        text = read(prog)
        m = re.search(r"<!-- TIMELINE-START -->(.*?)<!-- TIMELINE-END -->", text, re.S)
        if m:
            old = [l for l in m.group(1).strip().splitlines() if l.startswith("|")]
    return "\n".join(old + [new_line])


def gen_snapshot(rows, ts: str, copied: dict, state_text: str) -> str:
    done, doing, pending, pct = progress_stats(rows)
    mirror_md = "\n".join(f"- **{k}**：{len(v)} 个文件" for k, v in copied.items())
    return f"""# 📸 同步快照 · {ts}

> 由 `sync/sync_to_github.py` 自动生成 | 数据源：`agent_workspace/STATE.md`

## 本轮概要

| 指标 | 值 |
|---|---|
| 当前进度 | **{pct}%** |
| 已完成阶段 | {done} |
| 进行中阶段 | {doing} |
| 待开始阶段 | {pending} |
| 当前阶段 | {current_stage(rows)} |

### 本轮镜像的成果文件

{mirror_md}

## 阶段状态表

{stage_table_md(rows)}

{pie_chart(rows)}

---

## 附：STATE.md 台账原文

```markdown
{state_text}
```

## 附：任务看板原文

```markdown
{read(WORKSPACE / '00_admin' / 'task_board.md') if (WORKSPACE / '00_admin' / 'task_board.md').exists() else '（尚未建立）'}
```

## 附：决策记录原文

```markdown
{read(WORKSPACE / '00_admin' / 'decisions.md') if (WORKSPACE / '00_admin' / 'decisions.md').exists() else '（尚未建立）'}
```
"""


def gen_readme(rows, ts: str, copied: dict) -> str:
    done, doing, pending, pct = progress_stats(rows)
    stage_label = current_stage(rows)
    q = urllib.parse.quote
    b1 = q(f"{pct}%25-{pct*10//10}")
    badges = (f"![进度](https://img.shields.io/badge/总进度-{pct}%25-2ea44f)"
              f" ![当前阶段](https://img.shields.io/badge/当前阶段-{q(stage_label.split(' ')[0])}-0969da)"
              f" ![更新](https://img.shields.io/badge/更新-{q(ts)}-bf8700)"
              f" ![流水线](https://img.shields.io/badge/流水线-12_Agents-8250df)")
    deliverable_links = []
    if copied["论文与阶段文档"]:
        deliverable_links.append("[📄 论文与文档](deliverables/paper/)")
    if copied["图表"]:
        deliverable_links.append("[📈 图表](deliverables/figures/)")
    if copied["提交结果"]:
        deliverable_links.append("[📦 提交结果](deliverables/result/)")
    dl = " · ".join(deliverable_links) if deliverable_links else "*成果将于各阶段完成后在此展示*"
    return f"""<div align="center">

# 🚚 AAW · MathorCup 2025 赛道 B

**物流理赔风险识别及服务升级 —— 12-Agent 数模竞赛流水线**

{badges}

</div>

---

## 📌 项目简介

本项目用一套 **A0–A11 共 12 个角色化 Agent** 的流水线体系求解 **2025 年第 15 届 MathorCup 数学建模挑战赛·大数据竞赛赛道 B**：基于 11167 条历史运单建立理赔风险标注模型（合理诉求 / 诉求偏高 / 严重超额），预测 2792 条待预测运单的实际赔付金额与风险标注，并完成竞赛论文。本仓库每小时自动同步一次项目进展，全部快照见 [reports/](reports/)。

**三问概览**：Q1 风险标注模型 · Q2 实际赔付金额回归预测（SMAPE/MAE/RMSE/WMAPE）· Q3 风险标注分类预测（含不均衡处理与双路线对比论述）

## 🎯 当前状态

| 指标 | 值 |
|---|---|
| 当前阶段 | **{stage_label}** |
| 总进度 | **{pct}%**（{done} 完成 / {doing} 进行中 / {pending} 待开始） |
| 最近更新 | {ts} |

{pie_chart(rows)}

## 📋 阶段进度总览

{stage_table_md(rows)}

## 🏆 成果展示

- {dl}
- 结果摘要：[deliverables/result/result_摘要.md](deliverables/result/result_摘要.md)（A6 完成后可用）

## 🗂 目录导航

| 路径 | 内容 |
|---|---|
| [PROGRESS.md](PROGRESS.md) | 进度台账：阶段明细、关键结论、同步时间线 |
| [reports/](reports/) | 每小时同步快照（含台账/看板/决策原文存档），最新见 [LATEST.md](reports/LATEST.md) |
| [docs/pipeline.md](docs/pipeline.md) | 12-Agent 流水线架构与门禁体系 |
| [docs/data-notes.md](docs/data-notes.md) | 数据事实与已识别数据坑 |
| [docs/decisions.md](docs/decisions.md) | 决策记录（随阶段追加） |
| [docs/task-board.md](docs/task-board.md) | 任务看板（A0 维护） |
| [docs/environment.md](docs/environment.md) | 环境与工具链、目录约定 |
| [deliverables/](deliverables/) | 成果镜像：代码 / 论文 / 图表 / 表格 / 提交结果 |
| [sync/](sync/) | 自动同步脚本（可复现同步过程） |

---

<div align="center">
<sub>本仓库由 sync_to_github.py 每小时自动同步 · 数据源为工作区 STATE.md · 竞赛原始数据不入库</sub>
</div>
"""


def gen_progress(rows, ts: str, state_text: str, timeline: str) -> str:
    done, doing, pending, pct = progress_stats(rows)
    conds = extract_section(state_text, r"^## 2\. 数据事实")
    concl = extract_section(state_text, r"^## 4\. 关键模型结论")
    todo = extract_section(state_text, r"^## 6\. 当前状态")
    done_list = "\n".join(f"- ✅ **{r['stage']}** {r['content']} → `{r['artifacts']}`"
                          for r in rows if r["status"] == "DONE") or "- （暂无）"
    doing_list = "\n".join(f"- 🔄 **{r['stage']}** {r['content']} → 目标产物：`{r['artifacts']}`"
                           for r in rows if r["status"] == "IN_PROGRESS") or "- （暂无）"
    pend_list = "\n".join(f"- ⬜ **{r['stage']}** {r['content']}"
                          for r in rows if r["status"] == "PENDING") or "- （暂无）"
    return f"""# 📒 进度台账 · PROGRESS

> 自动生成于 {ts} | 数据源：`agent_workspace/STATE.md`（A0 chief-orchestrator 维护）

## 总览

- **总进度：{pct}%** —— 已完成 **{done}** 个阶段，进行中 **{doing}** 个，待开始 **{pending}** 个
- **当前阶段：{current_stage(rows)}**

## 阶段状态表

{stage_table_md(rows)}

## ✅ 已完成

{done_list}

## 🔄 进行中

{doing_list}

## ⬜ 待办

{pend_list}

## 🔑 关键模型结论（随阶段更新，仅记录已实测数字）

{concl}

## 🗃 数据事实（已核验）

{conds}

## 📝 当前状态与待办（台账原文）

{todo}

## 🕐 同步时间线

<!-- TIMELINE-START -->
{timeline}
<!-- TIMELINE-END -->
"""


def git(*args, timeout=120):
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r


def main():
    if not STATE_MD.exists():
        print(f"[error] 找不到台账文件: {STATE_MD}")
        sys.exit(1)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    month_dir = datetime.now().strftime("%Y-%m")

    state_text = read(STATE_MD)
    rows = parse_stage_table(state_text)
    if not rows:
        print("[error] 未能从 STATE.md 解析出阶段表")
        sys.exit(1)

    # 1) 成果镜像（竞赛原始数据不入库）
    copied = copy_deliverables()

    # 2) docs 复制
    for src, dst in (("task_board.md", "task-board.md"), ("decisions.md", "decisions.md"),
                     ("progress.md", "progress.md")):
        p = WORKSPACE / "00_admin" / src
        if p.exists():
            (REPO / "docs").mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, REPO / "docs" / dst)

    # 3) 快照
    snap = gen_snapshot(rows, ts, copied, state_text)
    rdir = REPO / "reports" / month_dir
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / f"{stamp}.md").write_text(snap, encoding="utf-8")
    (REPO / "reports" / "LATEST.md").write_text(snap, encoding="utf-8")

    # 4) README + PROGRESS（时间线保留历史）
    tl_line = f"| {ts} | 进度 {progress_stats(rows)[3]}% | {current_stage(rows)} |"
    (REPO / "README.md").write_text(gen_readme(rows, ts, copied), encoding="utf-8")
    (REPO / "PROGRESS.md").write_text(
        gen_progress(rows, ts, state_text, timeline_entries(tl_line)), encoding="utf-8")

    # 5) git 提交推送
    if git("add", "-A").returncode != 0:
        print("[error] git add 失败"); sys.exit(1)
    st = git("status", "--porcelain")
    if not st.stdout.strip():
        print(f"[skip] {ts} 无变更，跳过提交")
        return
    done, doing, pending, pct = progress_stats(rows)
    msg = (f"sync: {ts} 进度{pct}% — 完成{done} 进行中{doing} 待办{pending} · {current_stage(rows)}")
    c = git("commit", "-m", msg)
    if c.returncode != 0:
        print(f"[error] git commit 失败: {c.stderr}"); sys.exit(1)
    # 确保分支名为 main 并带 upstream 推送
    git("branch", "-M", "main")
    p = git("push", "-u", "origin", "main", timeout=180)
    if p.returncode != 0:
        print(f"[error] git push 失败:\n{p.stderr}"); sys.exit(1)
    print(f"[ok] {ts} 已同步并推送: {msg}")


if __name__ == "__main__":
    main()
