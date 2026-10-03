# 任务看板 task_board.md（A0 维护）

## 看板
| 任务卡 | 负责 | 输入 | 输出 | 门禁 | 状态 |
|---|---|---|---|---|---|
| T-A1 题意拆解 | A1 | 赛题要点、数据勘察 | paper/01_题意拆解.md | G1: 三问拆解完整、口径定义清晰 | IN_PROGRESS |
| T-A2 假设清单 | A2 | 赛题+EDA 线索 | paper/01b_假设清单.md | 假设可检验、不超过 8 条 | PENDING |
| T-A3 数据工程 | A3 | data/附件1.xlsx、附件2.xlsx | code/eda_clean.py、output/eda/*、output/data/clean_*.csv | G2: 缺失/异常全说明、清洗后可复跑 | PENDING |
| T-A4 Q1 规则设计 | A4 | A3 产物 | paper/02_问题1标注模型.md、output/tables/q1_*.csv | G3: 满足软约束、规则可复现 | PENDING |
| T-A5 算法规格 | A5 | A3/A4 产物 | paper/03_算法规格.md | 指标/CV/不均衡方案完整 | PENDING |
| T-A6 代码实现 | A6 | A3–A5 产物 | code/*.py、output/tables/*、output/Result_提交.xlsx | G4: 运单号不变、类别取值合法、日志齐全 | PENDING |
| T-A7 结果分析 | A7 | A6 产物 | paper/04_结果分析.md | 含敏感性+两路线对比数据 | PENDING |
| T-A8 可视化 | A8 | A3/A4/A6 产物 | output/figures/fig*.png | 中文无乱码、300dpi | PENDING |
| T-A9 论文撰写 | A9 | 全部产物 | paper/论文.md | G5: 结构完整、含两处必答论述 | PENDING |
| T-A10 润色 | A10 | 论文.md | 摘要定稿版 | 格式统一 | PENDING |
| T-A11 终审质检 | A11 | 全部 | code/qa_check.py、output/logs/qa_report.md | G6: 0 ERROR 才终审通过 | PENDING |

## 任务卡索引
- 00_admin/task_cards/ 下按 T-A1 ... T-A11 存卡（卡内含输入/输出/验收标准）。

## 冲突与仲裁记录
- 暂无。
