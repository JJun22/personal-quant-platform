"""
Market Data Layer.

設計原則（對應對話文件 4.1）：
- 1m OHLCV 是 canonical base data，所有其他 timeframe 都由此 resample 而來，
  確保任何 timeframe 的資料都可以追溯回同一底層來源。
- Dataset 有版本概念（用檔案內容 hash 當 checksum），確保 experiment 可重現：
  同一個 dataset_id + checksum 保證你跑的是同一份資料。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

_RESAMPLE_RULE = {
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1D",
}

_AGG = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum",
}


@dataclass(frozen=True)
class DatasetRef:
    """一份 dataset 的可追溯身分：路徑 + 內容 checksum。"""

    symbol: str
    timeframe: str
    path: Path
    checksum: str


def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def load_base_ohlcv(path: Path) -> pd.DataFrame:
    """讀取 canonical 1m OHLCV。
    V0 用 pickle（此環境無網路裝不了 pyarrow）；換成 parquet 只需要改這一行 + synth.py 的寫入。"""
    df = pd.read_pickle(path)
    _validate_ohlcv_schema(df)
    return df


def resample_ohlcv(df_1m: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """把 1m base data aggregate 成指定 timeframe。"""
    if timeframe == "1m":
        return df_1m.copy()
    if timeframe not in _RESAMPLE_RULE:
        raise ValueError(f"不支援的 timeframe: {timeframe}")
    rule = _RESAMPLE_RULE[timeframe]
    out = df_1m.resample(rule).agg(_AGG)
    out = out.dropna(subset=["open", "high", "low", "close"])
    return out


def make_dataset_ref(symbol: str, timeframe: str, path: Path) -> DatasetRef:
    return DatasetRef(
        symbol=symbol,
        timeframe=timeframe,
        path=path,
        checksum=file_checksum(path),
    )


def _validate_ohlcv_schema(df: pd.DataFrame) -> None:
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV 資料缺少欄位: {missing}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("OHLCV index 必須是 DatetimeIndex")
    if df.index.tz is None:
        raise ValueError("OHLCV index 必須帶時區（UTC），避免對齊錯誤")
    # P1 Data & Causality Integrity 的第一道防線：時間必須嚴格遞增、不可重複
    if not df.index.is_monotonic_increasing:
        raise ValueError("OHLCV index 不是嚴格遞增，可能有資料錯亂")
    if df.index.has_duplicates:
        raise ValueError("OHLCV index 有重複時間戳")
