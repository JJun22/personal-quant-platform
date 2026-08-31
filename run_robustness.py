"""
V0C 入口：跑完整的 Robustness / Falsification suite。

用法（在 quant_platform 的上一層目錄執行）：

    python -m quant_platform.run_robustness --timeframe 1h --fast 20 --slow 100

會依序執行：
1. 用 base 參數跑一次基準 backtest
2. Parameter perturbation（各參數 ±10%/±20%）
3. Cost stress（成本 1x/1.5x/2x/3x）
4. Execution delay sensitivity（額外延遲 0/1/2/3 根 bar）
5. Sample perturbation（leave-best-trade-out + rolling window）
6. 對 parameter candidate family 做 Benjamini-Hochberg multiple-testing 修正

Cost/delay 是穩健性診斷，不當成新的 alpha hypotheses 加入顯著性計數。

會產生比 run_experiment.py 多很多 run（每個 sweep 的每個 trial 都是一次
完整 backtest），這是刻意的：V0C 的重點就是「用大量 trial 換取穩健性判斷」，
如果 trial 數太少，穩定性/多重比較這些檢查本身就沒有意義。
"""
from __future__ import annotations

import argparse

from quant_platform import config
from quant_platform.data import synth
from quant_platform.data.loader import load_base_ohlcv, make_dataset_ref, resample_ohlcv
from quant_platform.registry import db as registry_db
from quant_platform.registry import repository as repo
from quant_platform.report.generate import render_robustness_report, save_report
from quant_platform.robustness.engine import run_full_robustness_suite
from quant_platform.strategy.examples.sma_cross import SmaCrossStrategy


def get_or_create_base_dataset():
    path = config.DATA_DIR / f"{config.DEFAULT_SYMBOL.replace('/', '')}_1m_synthetic.pkl"
    if not path.exists():
        print(f"[data] 找不到本地資料，產生合成 1m 資料集 -> {path}")
        synth.save_synthetic_dataset(path, seed=config.RANDOM_SEED)
    return path


def main():
    parser = argparse.ArgumentParser(description="跑完整的 V0C Robustness/Falsification suite")
    parser.add_argument("--timeframe", default="1h", choices=["1m", "5m", "15m", "1h", "4h", "1d"])
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=100)
    parser.add_argument("--experiment", default="v0c_robustness_test")
    args = parser.parse_args()

    registry_db.init_db(config.REGISTRY_DB_PATH)
    conn = registry_db.get_connection(config.REGISTRY_DB_PATH)

    base_path = get_or_create_base_dataset()
    df_1m = load_base_ohlcv(base_path)
    df = resample_ohlcv(df_1m, args.timeframe)
    dataset_ref = make_dataset_ref(config.DEFAULT_SYMBOL, args.timeframe, base_path)

    experiment_id = repo.ensure_experiment(
        conn, args.experiment, "V0C：Parameter perturbation / cost stress / execution delay / FDR"
    )

    base_params = {"fast": args.fast, "slow": args.slow}

    print(f"[robustness] 開始跑完整 suite（會產生較多 run，請稍候）...")
    report = run_full_robustness_suite(
        conn=conn,
        experiment_id=experiment_id,
        dataset_ref=dataset_ref,
        df=df,
        strategy_factory=lambda **kw: SmaCrossStrategy(**kw),
        base_params=base_params,
        timeframe=args.timeframe,
        base_commission_bps=config.DEFAULT_COMMISSION_BPS,
        base_slippage_bps=config.DEFAULT_SLIPPAGE_BPS,
    )

    report_text = render_robustness_report(report)
    report_path = save_report(report_text, config.REPORTS_DIR, f"robustness_{report.base_run_id}")

    print(report_text)
    print(f"\n[report] 已存到 {report_path}")

    conn.close()


if __name__ == "__main__":
    main()
