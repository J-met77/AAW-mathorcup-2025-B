# 环境与工具链

| 项 | 版本 / 说明 |
|---|---|
| 操作系统 | Windows 10.0.26200 x64 |
| Python | 3.13.14 |
| pandas | 3.0.5 |
| scikit-learn | 1.9.1 |
| LightGBM | 4.7.0 |
| XGBoost | 3.4.1 |
| matplotlib | 3.11.2 |
| python-docx | 1.2.0（pandoc 不可用，改用 python-docx 导出 docx） |

## 目录约定（工作区）

```
agent_workspace/
├── 00_admin/        # task_board.md、progress.md、decisions.md、task_cards/
├── code/            # eda_clean.py、q1_label.py、q2_reg.py、q3_clf.py、
│                    # fill_result.py、plots.py、qa_check.py、common.py
├── data/            # 附件1.xlsx、附件2.xlsx、Result.xlsx（竞赛原始数据，不入仓库）
├── output/
│   ├── data/        # 清洗后数据集
│   ├── eda/         # EDA 图表与统计
│   ├── figures/     # 论文级图表（300dpi PNG）
│   ├── logs/        # 运行日志、QA 报告
│   ├── tables/      # 结果表格 CSV
│   └── Result_提交.xlsx
├── paper/           # 01_题意拆解.md … 论文.md、论文.docx
└── STATE.md         # 进度台账（唯一权威进度来源）
```

## 重跑顺序

```
eda_clean.py → q1_label.py → q2_reg.py → q3_clf.py → fill_result.py → plots.py → qa_check.py
```

（内部使用绝对路径，工作目录任意。）
