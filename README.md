<div align="center">

# 🚚 AAW · MathorCup 2025 赛道 B

**物流理赔风险识别及服务升级 —— 12-Agent 数模竞赛流水线**

![进度](https://img.shields.io/badge/总进度-12%25-2ea44f) ![当前阶段](https://img.shields.io/badge/当前阶段-A1-0969da) ![更新](https://img.shields.io/badge/更新-2026-10-04%2002%3A01-bf8700) ![流水线](https://img.shields.io/badge/流水线-12_Agents-8250df)

</div>

---

## 📌 项目简介

本项目用一套 **A0–A11 共 12 个角色化 Agent** 的流水线体系求解 **2025 年第 15 届 MathorCup 数学建模挑战赛·大数据竞赛赛道 B**：基于 11167 条历史运单建立理赔风险标注模型（合理诉求 / 诉求偏高 / 严重超额），预测 2792 条待预测运单的实际赔付金额与风险标注，并完成竞赛论文。本仓库每小时自动同步一次项目进展，全部快照见 [reports/](reports/)。

**三问概览**：Q1 风险标注模型 · Q2 实际赔付金额回归预测（SMAPE/MAE/RMSE/WMAPE）· Q3 风险标注分类预测（含不均衡处理与双路线对比论述）

## 🎯 当前状态

| 指标 | 值 |
|---|---|
| 当前阶段 | **A1 题意拆解** |
| 总进度 | **12%**（1 完成 / 1 进行中 / 11 待开始） |
| 最近更新 | 2026-10-04 02:01 |

```mermaid
pie showData
    title 任务阶段完成情况
    "已完成" : 1
    "进行中" : 1
    "待开始" : 11
```

## 📋 阶段进度总览

| 阶段 | 内容 | 状态 | 产物 |
|---|---|---|---|
| **G0** | 工作区/数据勘察、台账建立 | ✅ 完成 | STATE.md、00_admin/* |
| **A1** | 题意拆解 | 🔄 进行中 | paper/01_题意拆解.md |
| **A2** | 文献与假设 | ⬜ 待开始 | paper/01b_假设清单.md |
| **A3** | 清洗/EDA/特征工程 | ⬜ 待开始 | code/eda_clean.py、output/eda/*、output/data/* |
| **A4** | Q1 标注规则设计 | ⬜ 待开始 | paper/02_问题1标注模型.md |
| **A5** | Q2/Q3 算法规格 | ⬜ 待开始 | paper/03_算法规格.md |
| **A6** | 代码实现与结果产出 | ⬜ 待开始 | code/*.py、output/tables/*、output/Result_提交.xlsx |
| **A7** | 结果与敏感性分析 | ⬜ 待开始 | paper/04_结果分析.md |
| **A8** | 可视化 | ⬜ 待开始 | output/figures/* |
| **A9** | 论文撰写 | ⬜ 待开始 | paper/论文.md |
| **A10** | 摘要润色 | ⬜ 待开始 | paper/论文.md |
| **A11** | 终审质检 | ⬜ 待开始 | code/qa_check.py、output/logs/qa_report.md |
| **G6** | 提交包汇总 | ⬜ 待开始 | output/Result_提交.xlsx、paper/论文.docx |

## 🏆 成果展示

- *成果将于各阶段完成后在此展示*
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
