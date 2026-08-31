"""
Cost Stress Sweep。

對應對話文件 Phase 3：很多策略的「獲利」只存在於成本假設過於樂觀的世界裡
（比如假設 0 滑價、比實際交易所更低的手續費）。這裡把 commission/slippage
同時放大 1x/1.5x/2x/3x，看策略在多保守的成本假設下還撐不撐得住。
如果 Sharpe 在 1.5x 就轉負，代表這個策略的獲利本來就薄，經不起真實世界的摩擦成本。
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

DEFAULT_MULTIPLIERS = (1.0, 1.5, 2.0, 3.0)


@dataclass
class CostStressTrial:
    multiplier: float
    commission_bps: float
    slippage_bps: float
    run_id: str
    sharpe: float
    sharpe_p_value: float


def run_cost_stress(
    conn: sqlite3.Connection,
    experiment_id: str,
    dataset_ref: DatasetRef,
    df: pd.DataFrame,
    strategy: Strategy,
    timeframe: str,
    base_commission_bps: float,
    base_slippage_bps: float,
    multipliers=DEFAULT_MULTIPLIERS,
) -> tuple[str, list[CostStressTrial]]:
    sweep_id = repo.create_sweep(
        conn, experiment_id, kind="cost_stress",
        description=f"base_commission_bps={base_commission_bps}, base_slippage_bps={base_slippage_bps}",
    )

    trials: list[CostStressTrial] = []
    for mult in multipliers:
        commission_bps = base_commission_bps * mult
        slippage_bps = base_slippage_bps * mult
        broker = BacktestBroker(commission_bps=commission_bps, slippage_bps=slippage_bps)

        label = f"commission_x{mult:g}"
        run_id, result = execute_and_record(conn, experiment_id, dataset_ref, df, strategy, broker, timeframe)
        repo.link_sweep_run(conn, sweep_id, run_id, label)

        trials.append(
            CostStressTrial(
                multiplier=mult,
                commission_bps=commission_bps,
                slippage_bps=slippage_bps,
                run_id=run_id,
                sharpe=result.metrics["sharpe"]["value"],
                sharpe_p_value=result.metrics["sharpe_p_value"],
            )
        )
    return sweep_id, trials


def find_breakeven_multiplier(trials: list[CostStressTrial]) -> float | None:
    """找出 Sharpe 轉負的第一個 multiplier，作為『這個策略能撐到多少倍成本』的簡單指標。"""
    sorted_trials = sorted(trials, key=lambda t: t.multiplier)
    for t in sorted_trials:
        if t.sharpe <= 0:
            return t.multiplier
    return None  # 在測試範圍內都沒轉負
