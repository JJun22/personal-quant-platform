"""
把「跑一次 backtest + 完整記錄到 Registry」的邏輯抽成共用函式。

run_experiment.py（單次執行）跟 robustness/engine.py（大量 sweep 執行）
都透過這個函式跑，確保兩邊的 lineage 紀錄邏輯永遠一致——
不會有「手動跑的 run 有記錄，sweep 跑的 run 忘記記錄」這種落差。
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from quant_platform.backtest.broker import Broker
from quant_platform.backtest.simulator import RunResult, run_backtest
from quant_platform.data.loader import DatasetRef
from quant_platform.registry import repository as repo
from quant_platform.strategy.base import Strategy


def execute_and_record(
    conn: sqlite3.Connection,
    experiment_id: str,
    dataset_ref: DatasetRef,
    df: pd.DataFrame,
    strategy: Strategy,
    broker: Broker,
    timeframe: str,
) -> tuple[str, RunResult]:
    """跑一次 backtest，並把完整身分（dataset/strategy version/cost model）跟結果寫進 Registry。
    回傳 (run_id, RunResult)。"""
    dataset_id = repo.ensure_dataset(conn, dataset_ref)
    strategy_id = repo.ensure_strategy(conn, strategy.meta.name, strategy.meta.description)
    version_id = repo.ensure_strategy_version(conn, strategy_id, strategy)

    cost_model = {
        "commission_bps": getattr(broker, "commission_bps", None),
        "slippage_bps": getattr(broker, "slippage_bps", None),
        "extra_delay_bars": getattr(broker, "extra_delay_bars", 0),
    }
    run_id = repo.start_run(conn, experiment_id, version_id, dataset_id, timeframe, cost_model)

    try:
        result = run_backtest(strategy, df, broker, timeframe)
        repo.record_metrics(conn, run_id, result.metrics)
        repo.finish_run(conn, run_id, status="completed")
    except Exception:
        repo.finish_run(conn, run_id, status="failed")
        raise

    return run_id, result
