"""
合成 OHLCV 資料產生器。

用意：這台 sandbox 沒有對外網路，無法直接接 Binance/ccxt 拉真實資料。
這裡先用一個帶波動群聚（volatility clustering）與弱趨勢的隨機過程，
產生「看起來合理」的 1m OHLCV，讓 V0A/V0B 的管線可以先端到端跑通、
驗證 Strategy -> Backtest -> Registry -> Report 每一層邏輯正確。

之後接真實資料時，只需要新增一個 data/exchange_loader.py（例如用 ccxt），
產生同樣 schema 的 parquet 檔即可，其餘所有層完全不用動。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def generate_synthetic_ohlcv(
    start: str = "2024-01-01",
    periods: int = 60 * 24 * 90,  # 90 天的 1m bars
    freq: str = "1min",
    start_price: float = 42000.0,
    seed: int = 42,
) -> pd.DataFrame:
    """產生 canonical schema 的合成 1m OHLCV: index=UTC timestamp, columns=[open,high,low,close,volume]"""
    rng = np.random.default_rng(seed)

    n = periods
    # 用 GARCH-like 波動群聚：vol 本身是隨機遊走 + 均值回歸
    vol = np.zeros(n)
    vol[0] = 0.0006
    for i in range(1, n):
        vol[i] = max(1e-5, 0.95 * vol[i - 1] + 0.05 * 0.0006 + rng.normal(0, 0.00003))

    # 弱趨勢 + 噪音的 log return
    drift = rng.normal(0, 0.00002, n)
    noise = rng.normal(0, 1, n) * vol
    log_ret = drift + noise

    close = start_price * np.exp(np.cumsum(log_ret))

    # 用 close 反推合理的 open/high/low（bar 內雜訊）
    open_ = np.empty(n)
    open_[0] = start_price
    open_[1:] = close[:-1]

    intrabar_noise = rng.normal(0, 1, n) * vol * start_price
    high = np.maximum(open_, close) + np.abs(intrabar_noise)
    low = np.minimum(open_, close) - np.abs(intrabar_noise)

    # volume 跟波動度正相關 + 隨機雜訊，且非負
    base_volume = 5 + 4000 * (vol / vol.mean())
    volume = np.abs(base_volume + rng.normal(0, 5, n))

    idx = pd.date_range(start=start, periods=n, freq=freq, tz="UTC")
    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )
    df.index.name = "timestamp"
    return df


def save_synthetic_dataset(path, **kwargs) -> pd.DataFrame:
    df = generate_synthetic_ohlcv(**kwargs)
    # 用 pickle 而非 parquet：這個 sandbox 沒有網路裝不了 pyarrow。
    # 之後在有網路的環境，把這裡跟 loader.load_base_ohlcv 換成 to_parquet/read_parquet 即可，
    # 其餘所有層（strategy/backtest/registry）完全不受影響。
    df.to_pickle(path)
    return df
