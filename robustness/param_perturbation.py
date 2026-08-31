"""
Parameter Perturbation Sweep。

對應對話文件 Phase 3：一個策略如果只在 fast=20/slow=100 這個精確組合上
表現好，鄰近的 fast=18/slow=95 或 fast=22/slow=105 表現就崩掉，
這通常代表在做曲線擬合（curve-fitting），不是找到真的 edge。

做法：對 base_params 裡每個數值型參數，各自獨立做 ±10%/±20% 擾動
（其他參數固定在 base 值），跑一次完整 backtest，收集 Sharpe 分佈。
理想的穩健策略，績效應該在這個鄰域內平滑變化，而不是只有一個孤島最佳點。
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from quant_platform.backtest.broker import Broker
from quant_platform.data.loader import DatasetRef
from quant_platform.registry import repository as repo
from quant_platform.runner import execute_and_record
from quant_platform.strategy.base import Strategy

DEFAULT_PCT_STEPS = (-0.20, -0.10, 0.0, 0.10, 0.20)


@dataclass
class PerturbationTrial:
    label: str
    params: dict
    run_id: str | None
    sharpe: float | None
    sharpe_p_value: float | None
    skipped_reason: str | None = None


def run_param_perturbation(
    conn: sqlite3.Connection,
    experiment_id: str,
    dataset_ref: DatasetRef,
    df: pd.DataFrame,
    strategy_factory: Callable[..., Strategy],
    base_params: dict,
    broker: Broker,
    timeframe: str,
    pct_steps=DEFAULT_PCT_STEPS,
) -> tuple[str, list[PerturbationTrial]]:
    """對 base_params 裡每個參數各自做 pct_steps 擾動，回傳 (sweep_id, trial 結果列表)。"""
    sweep_id = repo.create_sweep(
        conn, experiment_id, kind="param_perturbation",
        description=f"base_params={base_params}, pct_steps={pct_steps}",
    )

    trials: list[PerturbationTrial] = []
    seen_param_tuples: set[tuple] = set()

    for key, base_value in base_params.items():
        for pct in pct_steps:
            perturbed = dict(base_params)
            if isinstance(base_value, int):
                new_value = max(1, round(base_value * (1 + pct)))
            else:
                new_value = base_value * (1 + pct)
            perturbed[key] = new_value

            param_tuple = tuple(sorted(perturbed.items()))
            if param_tuple in seen_param_tuples:
                continue  # pct=0 對每個 key 都會重複到 base_params，只跑一次
            seen_param_tuples.add(param_tuple)

            label = f"{key}={pct:+.0%}" if pct != 0 else "baseline"

            try:
                strategy = strategy_factory(**perturbed)
            except (ValueError, TypeError) as e:
                trials.append(PerturbationTrial(label, perturbed, None, None, None, skipped_reason=str(e)))
                continue

            run_id, result = execute_and_record(conn, experiment_id, dataset_ref, df, strategy, broker, timeframe)
            repo.link_sweep_run(conn, sweep_id, run_id, label)

            sharpe = result.metrics["sharpe"]["value"]
            p_value = result.metrics["sharpe_p_value"]
            trials.append(PerturbationTrial(label, perturbed, run_id, sharpe, p_value))

    return sweep_id, trials


def summarize_stability(trials: list[PerturbationTrial]) -> dict:
    """簡單摘要：有效 trial 的 Sharpe 平均/標準差/範圍，標準差越小代表越穩定。"""
    valid = [t for t in trials if t.sharpe is not None]
    if not valid:
        return {"n_valid": 0}
    sharpes = [t.sharpe for t in valid]
    return {
        "n_valid": len(valid),
        "n_skipped": len(trials) - len(valid),
        "sharpe_mean": sum(sharpes) / len(sharpes),
        "sharpe_std": pd.Series(sharpes).std(ddof=1) if len(sharpes) > 1 else 0.0,
        "sharpe_min": min(sharpes),
        "sharpe_max": max(sharpes),
    }
