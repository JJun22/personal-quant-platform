"""
Simulator：把 Strategy 跟 Broker 串成一次完整的 backtest run。

這一層刻意保持「薄」——不做任何 registry 寫入或 report 產生，
單純負責 Signal -> Fill -> Metrics 這條計算鏈，方便未來被
Paper/Live 用同一組介面呼叫（只是 Broker 換成 PaperBroker/ExchangeBroker）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from quant_platform.backtest.broker import Broker, BacktestResult
from quant_platform.backtest.metrics import compute_all_metrics
from quant_platform.strategy.base import Strategy

TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}
_TIMEFRAME_SECONDS = TIMEFRAME_SECONDS  # 保留舊名稱相容


@dataclass
class RunResult:
    strategy_meta: dict
    timeframe: str
    backtest_result: BacktestResult
    metrics: dict
    signals: pd.Series
    diagnostics: dict = field(default_factory=dict)


def run_backtest(strategy: Strategy, df: pd.DataFrame, broker: Broker, timeframe: str) -> RunResult:
    if timeframe not in _TIMEFRAME_SECONDS:
        raise ValueError(f"未知 timeframe: {timeframe}，請在 simulator._TIMEFRAME_SECONDS 補上")
    bar_seconds = _TIMEFRAME_SECONDS[timeframe]

    signals = strategy.generate_signals(df)
    strategy.validate_signals(signals, df)

    result = broker.run(df, signals)
    metrics = compute_all_metrics(result.returns, result.equity_curve, bar_seconds)

    diagnostics = {
        "n_trades": len(result.fills),
        "avg_position_abs": float(result.position.abs().mean()),
        "time_in_market_pct": float((result.position.abs() > 1e-9).mean() * 100),
    }

    return RunResult(
        strategy_meta={
            "name": strategy.meta.name,
            "version_label": strategy.meta.version_label,
            "params": strategy.meta.params,
            "description": strategy.meta.description,
        },
        timeframe=timeframe,
        backtest_result=result,
        metrics=metrics,
        signals=signals,
        diagnostics=diagnostics,
    )
