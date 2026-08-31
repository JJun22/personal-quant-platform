"""
Broker 抽象層。

對應對話文件 4.3：Simulator 不該只算 equity curve，要保留完整的
Signal -> Target Position -> Order -> Fill -> Position -> PnL 事件鏈，
這樣同一個 Strategy 介面才能無縫接到 PaperBroker / ExchangeBroker，
不用因為換了執行環境就重寫策略邏輯。

V0 先實作 BacktestBroker：假設每根 bar 的 close 價格可以完全成交
（沒有 partial fill、沒有滑價曲面），符合 P1 Data & Causality Integrity
所說的「不能有 impossible fill」的最基本版本 —— 用下一根 bar 的 open 成交，
避免用同一根 bar 的 close 訊號、同一根 bar 的 close 成交這種 lookahead。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Fill:
    timestamp: pd.Timestamp
    price: float
    qty_delta: float  # position 變化量，正=買入，負=賣出
    commission: float
    slippage_cost: float


class Broker(ABC):
    @abstractmethod
    def run(self, df: pd.DataFrame, target_position: pd.Series) -> "BacktestResult":
        raise NotImplementedError


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    position: pd.Series
    fills: list[Fill]
    returns: pd.Series


class BacktestBroker(Broker):
    """
    最簡化的單一 instrument backtest broker。

    執行規則（刻意寫死、簡單、可解釋，避免一開始就用複雜撮合模型騙自己）：
    - target_position 在 t 時刻決定，但用 t+1 的 open 價格成交（避免 lookahead）。
    - 每次 position 變化都收 commission + slippage（用 bps 表示）。
    - 沒有槓桿限制、沒有保證金模型（V0 範圍外，Phase 6 risk 才會加）。
    """

    def __init__(
        self,
        commission_bps: float,
        slippage_bps: float,
        initial_capital: float = 100_000.0,
        extra_delay_bars: int = 0,
    ):
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.initial_capital = initial_capital
        # V0C execution delay 敏感度測試用：baseline 已經有 1 根 bar 的必要延遲
        # （t 時刻決定、t+1 才成交），extra_delay_bars 是在這之上「再多」延遲幾根，
        # 模擬 signal 產生到真的送出訂單之間的額外延遲（網路延遲、排程間隔等）。
        if extra_delay_bars < 0:
            raise ValueError("extra_delay_bars 不能是負數")
        self.extra_delay_bars = extra_delay_bars

    def run(self, df: pd.DataFrame, target_position: pd.Series) -> BacktestResult:
        total_delay = 1 + self.extra_delay_bars
        # position 在索引 t 開始生效（=從這根 bar 起適用新部位），
        # 所以這根 bar 的 open 就是自然的成交價，不需要再額外位移。
        # extra_delay_bars 是透過下面 target_position 的 shift 量體現，而不是這裡。
        exec_price = df["open"]
        # 訊號本身要 lag total_delay 根，代表「這根 bar 收盤後，經過額外延遲才真的調整部位」
        lagged_target = target_position.shift(total_delay).fillna(0.0)

        position = lagged_target.copy()
        position_change = position.diff().fillna(position.iloc[0])

        cost_bps = (self.commission_bps + self.slippage_bps) / 10_000.0
        trade_cost = position_change.abs() * cost_bps  # 以「曝險比例變化」計算成本比例

        # 成交與 PnL 必須用同一條時間線：
        # - 前一根 close 到本根 open 的 overnight return，由「舊部位」承擔。
        # - 訊號在本根 open 成交後，open 到 close 由「新部位」承擔。
        # 不能讓在 open 才成交的新部位吃到事先已發生的 close-to-open 跳空。
        previous_close = df["close"].shift(1)
        overnight_return = (df["open"] / previous_close - 1.0).fillna(0.0)
        intraday_return = (df["close"] / df["open"] - 1.0).fillna(0.0)
        previous_position = position.shift(1).fillna(0.0)

        overnight_factor = 1.0 + previous_position * overnight_return
        cost_factor = 1.0 - trade_cost
        intraday_factor = 1.0 + position * intraday_return
        strategy_return = overnight_factor * cost_factor * intraday_factor - 1.0

        equity_curve = self.initial_capital * (1 + strategy_return).cumprod()

        fills: list[Fill] = []
        commission_rate = self.commission_bps / 10_000.0
        slippage_rate = self.slippage_bps / 10_000.0
        nonzero_changes = position_change[position_change.abs() > 1e-12]
        for ts, delta in nonzero_changes.items():
            price = exec_price.get(ts, np.nan)
            if np.isnan(price):
                continue
            notional = abs(delta) * self.initial_capital
            fills.append(
                Fill(
                    timestamp=ts,
                    price=float(price),
                    qty_delta=float(delta),
                    commission=notional * commission_rate,
                    slippage_cost=notional * slippage_rate,
                )
            )

        return BacktestResult(
            equity_curve=equity_curve,
            position=position,
            fills=fills,
            returns=strategy_return,
        )
