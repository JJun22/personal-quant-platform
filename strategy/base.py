"""
Strategy 抽象介面。

對應對話文件 4.2/4.3：不管策略是用 DSL 產生還是手寫 Python，
最終都要符合同一個介面（輸入 OHLCV -> 輸出 target position），
這樣 Simulator／Broker 才能對 backtest、paper、live 共用同一套邏輯。

V0 先只支援單一 instrument、單一 signal 的簡化版本；
多資產 portfolio 版本留到 Phase 6 再擴充介面。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class StrategyMeta:
    """策略的身分與版本資訊，寫入 Registry 時會用到（對應文件第9節）。"""

    name: str
    version_label: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""


class Strategy(ABC):
    """
    所有策略的基底類別。

    子類別只需要實作 generate_signals：
    輸入一段 OHLCV DataFrame（index=timestamp, columns=[open,high,low,close,volume]），
    輸出一個 target position Series，值域建議在 [-1, 1]（做多/做空的目標曝險比例）。

    重要：generate_signals 內不可以用到「未來」資料（例如 shift 方向錯誤、
    用同一根 bar 的 close 去產生同一根 bar 就進場的訊號）。
    這是 P1 Data & Causality Integrity 要防的第一件事，
    所以 Simulator 會強制把訊號往後 shift 一根 bar 才拿去下單，
    即使策略寫錯了也不會直接吃到未來函數。
    """

    def __init__(self, meta: StrategyMeta):
        self.meta = meta

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """回傳與 df 同 index 的 target position Series。"""
        raise NotImplementedError

    def validate_signals(self, signals: pd.Series, df: pd.DataFrame) -> None:
        if not signals.index.equals(df.index):
            raise ValueError("signals 的 index 必須跟輸入的 OHLCV 完全對齊")
        if signals.isna().any():
            raise ValueError("signals 出現 NaN，策略邏輯可能有未覆蓋的情況")
        if (signals.abs() > 1.0 + 1e-9).any():
            raise ValueError("signals 超出 [-1, 1] 範圍")
