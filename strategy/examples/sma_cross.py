"""
範例策略：SMA crossover。

目的不是要「賺錢」，是 V0A 的驗收工具：用一個最簡單、行為完全可預期的策略，
驗證 Strategy -> Simulator -> Broker -> Metrics -> Registry -> Report 整條管線邏輯正確。
"""
from __future__ import annotations

import pandas as pd

from quant_platform.strategy.base import Strategy, StrategyMeta


class SmaCrossStrategy(Strategy):
    def __init__(self, fast: int = 20, slow: int = 100):
        if fast >= slow:
            raise ValueError("fast 週期必須小於 slow 週期")
        meta = StrategyMeta(
            name="sma_cross",
            version_label=f"fast{fast}_slow{slow}",
            params={"fast": fast, "slow": slow},
            description="快線上穿慢線做多，下穿做空的最簡單範例策略",
        )
        super().__init__(meta)
        self.fast = fast
        self.slow = slow

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        fast_ma = df["close"].rolling(self.fast).mean()
        slow_ma = df["close"].rolling(self.slow).mean()

        signal = pd.Series(0.0, index=df.index)
        signal[fast_ma > slow_ma] = 1.0
        signal[fast_ma < slow_ma] = -1.0
        # rolling window 還沒填滿前沒有訊號，保持空手，不可以是 NaN
        signal = signal.fillna(0.0)
        return signal
