"""
V0A + V0B 的入口：跑一次策略、記錄到 Registry、產生 report。

用法（在 /home/claude 底下執行，讓 quant_platform 是可 import 的 package）：

    python -m quant_platform.run_experiment --timeframe 1h

第一次執行時，如果找不到本地資料，會自動用合成資料產生一份 1m 資料集
（因為這個環境沒有對外網路，無法接真實交易所 API — 見 data/synth.py 說明）。
"""
from __future__ import annotations

import argparse

from quant_platform import config
from quant_platform.backtest.broker import BacktestBroker
from quant_platform.data import synth
from quant_platform.data.loader import load_base_ohlcv, make_dataset_ref, resample_ohlcv
from quant_platform.registry import db as registry_db
from quant_platform.registry import repository as repo
from quant_platform.report.generate import render_run_report, save_report
from quant_platform.runner import execute_and_record
from quant_platform.strategy.examples.sma_cross import SmaCrossStrategy


def get_or_create_base_dataset():
    path = config.DATA_DIR / f"{config.DEFAULT_SYMBOL.replace('/', '')}_1m_synthetic.pkl"
    if not path.exists():
        print(f"[data] 找不到本地資料，產生合成 1m 資料集 -> {path}")
        synth.save_synthetic_dataset(path, seed=config.RANDOM_SEED)
    return path


def main():
    parser = argparse.ArgumentParser(description="跑一次策略 backtest，並記錄到 Registry")
    parser.add_argument("--timeframe", default="1h", choices=["1m", "5m", "15m", "1h", "4h", "1d"])
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=100)
    parser.add_argument("--experiment", default="v0_smoke_test")
    args = parser.parse_args()

    registry_db.init_db(config.REGISTRY_DB_PATH)
    conn = registry_db.get_connection(config.REGISTRY_DB_PATH)

    base_path = get_or_create_base_dataset()
    df_1m = load_base_ohlcv(base_path)
    df = resample_ohlcv(df_1m, args.timeframe)
    dataset_ref = make_dataset_ref(config.DEFAULT_SYMBOL, args.timeframe, base_path)

    strategy = SmaCrossStrategy(fast=args.fast, slow=args.slow)
    broker = BacktestBroker(
        commission_bps=config.DEFAULT_COMMISSION_BPS,
        slippage_bps=config.DEFAULT_SLIPPAGE_BPS,
    )

    # ---- Registry: 先確立這次 run 的完整身分（V0B 核心）----
    experiment_id = repo.ensure_experiment(conn, args.experiment, "V0 smoke test：驗證管線端到端跑通")
    run_id, result = execute_and_record(conn, experiment_id, dataset_ref, df, strategy, broker, args.timeframe)

    report_text = render_run_report(
        run_id, result, {"symbol": dataset_ref.symbol, "timeframe": args.timeframe, "checksum": dataset_ref.checksum}
    )
    report_path = save_report(report_text, config.REPORTS_DIR, run_id)

    print(report_text)
    print(f"\n[registry] run_id={run_id} 已記錄到 {config.REGISTRY_DB_PATH}")
    print(f"[report] 已存到 {report_path}")

    conn.close()


if __name__ == "__main__":
    main()
