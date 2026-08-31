"""
Execution Delay Sensitivity。

對應對話文件 Phase 3：真實下單不會是完美即時的，網路延遲、系統排程、
交易所處理時間都會讓實際成交比策略「以為」的時間晚個幾根 bar。
如果策略績效對這種延遲極度敏感（延遲 1-2 根 bar 就從賺錢變賠錢），
代表這個策略高度依賴精確的進出場時機，實盤環境很難重現這種精度。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pandas as pd

from quant_platform.backtest.broker import BacktestBroker
from quant_platform.data.loader import DatasetRef
from quant_platform.registry import repository as repo
from quant_platform.runner import execute_and_record
from quant_platform.strategy.base import Strategy

DEFAULT_EXTRA_DELAYS = (0, 1, 2, 3)


@dataclass
class DelayTrial:
    extra_delay_bars: int
    run_id: str
    sharpe: float
    sharpe_p_value: float


def run_execution_delay_sweep(
    conn: sqlite3.Connection,
    experiment_id: str,
    dataset_ref: DatasetRef,
    df: pd.DataFrame,
    strategy: Strategy,
    timeframe: str,
    commission_bps: float,
    slippage_bps: float,
    extra_delays=DEFAULT_EXTRA_DELAYS,
) -> tuple[str, list[DelayTrial]]:
    sweep_id = repo.create_sweep(
        conn, experiment_id, kind="execution_delay",
        description=f"extra_delays={extra_delays}",
    )

    trials: list[DelayTrial] = []
    for delay in extra_delays:
        broker = BacktestBroker(
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            extra_delay_bars=delay,
        )
        label = f"delay+{delay}"
        run_id, result = execute_and_record(conn, experiment_id, dataset_ref, df, strategy, broker, timeframe)
        repo.link_sweep_run(conn, sweep_id, run_id, label)

        trials.append(
            DelayTrial(
                extra_delay_bars=delay,
                run_id=run_id,
                sharpe=result.metrics["sharpe"]["value"],
                sharpe_p_value=result.metrics["sharpe_p_value"],
            )
        )
    return sweep_id, trials
