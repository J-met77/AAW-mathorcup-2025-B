# -*- coding: utf-8 -*-
"""
common.py — 共享工具模块（A3 建立，全部脚本共用）
职责：统一数据读取（剥离英文字段名行）、类型收敛、特征列清单、路径常量。
所有脚本使用绝对路径，工作目录任意可复跑。
"""
from pathlib import Path
import pandas as pd
import numpy as np

WORK = Path(r"C:/Users/21732/Desktop/2025b论文/agent_workspace")
DATA = WORK / "data"
OUT = WORK / "output"
TBL = OUT / "tables"
FIG = OUT / "figures"
LOG = OUT / "logs"
CLEAN = OUT / "data"

LABELS = ["合理诉求", "诉求偏高", "严重超额"]

# 数值特征（清洗后）
NUM_FEATURES = [
    "claim_amount", "insure_amount", "insure_to_claim", "log_claim", "log_insure",
    "overtime_log_h", "overtime_neg_flag", "overtime_spike_flag",
    "case_delay_log_h", "case_delay_neg_flag", "case_delay_ms_flag",
    "start_node_waybill_num_log", "start_node_accident_rate", "start_node_claim_ratio",
    "end_node_waybill_num_log", "end_node_accident_rate", "end_node_claim_ratio",
    "consigner_freq", "receiver_freq",
]
# 类别特征（清洗后）
CAT_FEATURES = [
    "route_type", "is_c2c", "fresh_on_time", "start_city_id", "end_city_id",
    "abnormal_reason", "source", "goods_category", "goods_level", "bc_source",
    "customer_role", "is_staff",
]
# 全部特征（q2/q3 共用）
FEATURES = NUM_FEATURES + CAT_FEATURES

RAW_NUM = {
    "保价金额": "insure_amount", "配送超时时长": "overtime_raw", "妥投到进线时长": "case_delay_raw",
    "索赔金额": "claim_amount", "始发网点发单量": "start_node_waybill_num",
    "始发网点万单理赔率": "start_node_accident_rate", "始发网点赔付比例": "start_node_claim_ratio",
    "目的网点发单量": "end_node_waybill_num", "目的网点万单理赔率": "end_node_accident_rate",
    "目的网点赔付比例": "end_node_claim_ratio", "实际赔付金额": "payment_real",
}
RAW_CAT = {
    "线路类型": "route_type", "是否c2c": "is_c2c", "是否生鲜妥投及时": "fresh_on_time",
    "始发城市": "start_city_id", "目的城市": "end_city_id", "异常原因": "abnormal_reason",
    "进线渠道": "source", "商品类型": "goods_category", "新旧程度": "goods_level",
    "寄件B/C": "bc_source", "进线人身份": "customer_role", "寄件是否内部": "is_staff",
    "寄件人id": "consigner_id", "收件人id": "receiver_id",
}


def _coerce_num(df: pd.DataFrame) -> pd.DataFrame:
    """数值列强制转 float（read 后首行英文名导致 object dtype）。"""
    for c in df.columns:
        if c in ("运单号",):
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
            continue
        conv = pd.to_numeric(df[c], errors="coerce")
        # 转换后非缺失比例不低于原非缺失比例-1e-9 才接受数值化（保价金额等列含 -1 仍可转）
        if conv.notna().sum() >= df[c].notna().sum() - 1:
            df[c] = conv
    return df


def load_raw(which: str) -> pd.DataFrame:
    """读取附件并剥离第 0 条数据行（英文字段名行），统一列名。"""
    assert which in ("train", "test")
    path = DATA / ("附件1.xlsx" if which == "train" else "附件2.xlsx")
    df = pd.read_excel(path)
    df = df.iloc[1:].reset_index(drop=True)          # 剥离英文字段名行
    df = _coerce_num(df)
    df = df.rename(columns={**RAW_NUM, **RAW_CAT})
    return df


def normalize_seconds(v: pd.Series, ms_threshold: float = 1e7) -> pd.Series:
    """秒/毫秒混用归一：>=ms_threshold 视为毫秒，/1000 还原为秒。"""
    out = pd.to_numeric(v, errors="coerce").astype(float)
    ms = out >= ms_threshold
    out[ms] = out[ms] / 1000.0
    return out


def build_features(df: pd.DataFrame, id_freq: pd.Series | None = None) -> pd.DataFrame:
    """清洗 + 特征工程（train/test 一致处理）。

    步骤见 paper/03 算法规格与 output/eda/EDA报告.md。
    """
    df = df.copy()
    # ---- 缺失标记修复 ----
    df["insure_amount"] = df["insure_amount"].where(df["insure_amount"] >= 0, np.nan)   # -1→缺失(42)
    for c in ["start_node_waybill_num", "end_node_waybill_num"]:
        df[c] = df[c].where(df[c] >= 0, np.nan)
    for c in ["start_node_accident_rate", "end_node_accident_rate"]:                    # 负理赔率→缺失
        df[c] = df[c].where(df[c] >= 0, np.nan)

    # ---- 类别缺失归为独立水平 ----
    df["abnormal_reason"] = df["abnormal_reason"].fillna("无异常记录")
    df["source"] = df["source"].fillna("未知")
    for c in ["route_type", "is_c2c", "fresh_on_time", "goods_level", "is_staff",
              "start_city_id", "end_city_id", "goods_category", "bc_source", "customer_role"]:
        df[c] = df[c].astype(str)

    # ---- 时间字段 ----
    ov = normalize_seconds(df["overtime_raw"])
    df["overtime_log_h"] = np.sign(ov) * np.log1p(np.abs(ov) / 3600.0)
    df["overtime_neg_flag"] = (ov < 0).astype(int)
    df["overtime_spike_flag"] = ((ov - 427850).abs() < 60).astype(int)   # 哨兵值聚集区

    cd = normalize_seconds(df["case_delay_raw"])
    df["case_delay_ms_flag"] = (df["case_delay_raw"] >= 1e7).astype(int)
    df["case_delay_log_h"] = np.sign(cd) * np.log1p(np.abs(cd) / 3600.0)
    df["case_delay_neg_flag"] = (cd < 0).astype(int)

    # ---- 金额与派生 ----
    med_insure = df["insure_amount"].median()
    df["insure_amount"] = df["insure_amount"].fillna(med_insure)
    df["log_insure"] = np.log1p(df["insure_amount"])
    df["insure_to_claim"] = df["insure_amount"] / df["claim_amount"]
    df["log_claim"] = np.log1p(df["claim_amount"])

    # ---- 网点统计 ----
    for c in ["start_node_waybill_num", "end_node_waybill_num"]:
        df[c + "_log"] = np.log1p(df[c].fillna(df[c].median()))

    # ---- 高基数 ID：频次编码（train+test 合并词表，防泄漏见 D07）----
    for c, tgt in [("consigner_id", "consigner_freq"), ("receiver_id", "receiver_freq")]:
        if id_freq is None:
            freq = df[c].value_counts()
        else:
            freq = id_freq
        df[tgt] = df[c].map(freq).fillna(1.0).astype(float)

    # ---- Q1 派生量（训练表才有意义，test 上 payment_real 为 NaN）----
    if "payment_real" in df.columns:
        df["over_claim"] = df["claim_amount"] - df["payment_real"]          # 超额索赔额 x
        df["over_ratio"] = df["over_claim"] / df["payment_real"]            # 相对超额率 r
    return df


def get_X(df: pd.DataFrame) -> pd.DataFrame:
    return df[FEATURES].copy()


def as_category(X: pd.DataFrame) -> pd.DataFrame:
    """类别列转 pandas category（LightGBM 原生支持）。"""
    X = X.copy()
    for c in CAT_FEATURES:
        X[c] = X[c].astype("category")
    return X


def smape(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    den = (np.abs(y_true) + np.abs(y_pred)) / 2.0
    mask = den > 0
    return float(np.mean(np.abs(y_pred - y_true)[mask] / den[mask]))


def wmape(y_true, y_pred) -> float:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    return float(np.abs(y_pred - y_true).sum() / np.abs(y_true).sum())
