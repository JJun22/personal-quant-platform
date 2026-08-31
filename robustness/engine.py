"""
Robustness / Falsification Engine（V0C）。

把四種穩健性檢查串成一次完整的 suite。Parameter trials 被視為
同一個 evidence family，共同做 Benjamini-Hochberg 修正。Cost stress 和
execution delay 是已選定策略的診斷情境，不是額外的 alpha discoveries，
因此不混入同一個 multiple-testing family。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from quant_platform.backtest.broker import BacktestBroker
from quant_platform.backtest.simulator import RunResult, TIMEFRAME_SECONDS
from quant_platform.data.loader import DatasetRef
from quant_platform.robustness import cost_stress, execution_delay, param_perturbation, sample_perturbation
from quant_platform.robustness.trials import BHResult, benjamini_hochberg
from quant_platform.strategy.base import Strategy


@dataclass
class RobustnessReport:
    base_run_id: str
    base_result: RunResult
    param_sweep_id: str
    param_trials: list
    param_stability: dict
    cost_sweep_id: str
    cost_trials: list
    cost_breakeven_multiplier: float | None
    delay_sweep_id: str
    delay_trials: list
    leave_best_trade_out: sample_perturbation.LeaveBestTradeOutResult
    rolling_window: sample_perturbation.RollingWindowResult
    bh_result: BHResult
    n_total_trials_in_experiment: int


def run_full_robustness_suite(
    conn: sqlite3.Connection,
    experiment_id: str,
    dataset_ref: DatasetRef,
    df: pd.DataFrame,
    strategy_factory: Callable[..., Strategy],
    base_params: dict,
    timeframe: str,
    base_commission_bps: float,
    base_slippage_bps: float,
) -> RobustnessReport:
    from quant_platform.registry import repository as repo
    from quant_platform.runner import execute_and_record

    bar_seconds = TIMEFRAME_SECONDS[timeframe]

    base_strategy = strategy_factory(**base_params)
    base_broker = BacktestBroker(commission_bps=base_commission_bps, slippage_bps=base_slippage_bps)
    base_run_id, base_result = execute_and_record(
        conn, experiment_id, dataset_ref, df, base_strategy, base_broker, timeframe
    )

    # ---- 1. Parameter perturbation ----
    param_sweep_id, param_trials = param_perturbation.run_param_perturbation(
        conn, experiment_id, dataset_ref, df, strategy_factory, base_params, base_broker, timeframe
    )
    param_stability = param_perturbation.summarize_stability(param_trials)

    # ---- 2. Cost stress ----
    cost_sweep_id, cost_trials = cost_stress.run_cost_stress(
        conn, experiment_id, dataset_ref, df, base_strategy, timeframe,
        base_commission_bps, base_slippage_bps,
    )
    breakeven = cost_stress.find_breakeven_multiplier(cost_trials)

    # ---- 3. Execution delay ----
    delay_sweep_id, delay_trials = execution_delay.run_execution_delay_sweep(
        conn, experiment_id, dataset_ref, df, base_strategy, timeframe,
        base_commission_bps, base_slippage_bps,
    )

    # ---- 4. Sample perturbation（診斷 base run，不算進 trial 計數）----
    lbto = sample_perturbation.leave_best_trade_out(base_result.backtest_result.returns, bar_seconds)
    rolling = sample_perturbation.rolling_window_sharpe(base_result.backtest_result.returns, bar_seconds)

    # ---- 5. Multiple-testing 修正：只對參數候選 family 作檢定 ----
    p_values = []
    for t in param_trials:
        if t.sharpe_p_value is not None:
            p_values.append(t.sharpe_p_value)
    bh_result = benjamini_hochberg(p_values, alpha=0.10)

    n_total_trials = len(p_values)

    return RobustnessReport(
        base_run_id=base_run_id,
        base_result=base_result,
        param_sweep_id=param_sweep_id,
        param_trials=param_trials,
        param_stability=param_stability,
        cost_sweep_id=cost_sweep_id,
        cost_trials=cost_trials,
        cost_breakeven_multiplier=breakeven,
        delay_sweep_id=delay_sweep_id,
        delay_trials=delay_trials,
        leave_best_trade_out=lbto,
        rolling_window=rolling,
        bh_result=bh_result,
        n_total_trials_in_experiment=n_total_trials,
    )
