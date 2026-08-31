"""
Sample Perturbation。

對應對話文件 Phase 3 的兩個檢查，直接對已經跑完的 base run 的 return
序列做分析，不需要重新跑 backtest（也因此不算進 registry 的 trial 計數——
這是對「已選定配置」的穩健性診斷，不是搜尋，不會有 multiple-testing 問題）：

1. Leave-best-trade-out：拿掉單一報酬貢獻最大的那根 bar，看 Sharpe 掉多少。
   如果整個策略的正報酬幾乎全靠一兩筆極端交易撐著，這不是可靠的 edge。
2. Rolling-window Sharpe：把整段期間切成幾個不重疊的區塊，分別算 Sharpe，
   看績效是不是集中在某一小段時間，而不是在整個測試期間都穩定存在。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from quant_platform.backtest.metrics import sharpe_ratio


@dataclass
class LeaveBestTradeOutResult:
    original_sharpe: float
    sharpe_excl_best: float
    best_bar_return: float
    best_bar_timestamp: str
    sharpe_drop_pct: float  # (original - excl) / |original|，越大代表越依賴這根 bar


@dataclass
class RollingWindowResult:
    window_sharpes: list[float]
    window_labels: list[str]
    sharpe_std_across_windows: float
    n_negative_windows: int
    n_windows: int


def leave_best_trade_out(returns: pd.Series, bar_seconds: float) -> LeaveBestTradeOutResult:
    original_sharpe = sharpe_ratio(returns, bar_seconds)

    best_idx = returns.idxmax()
    best_value = returns.loc[best_idx]

    returns_excl = returns.copy()
    returns_excl.loc[best_idx] = 0.0
    sharpe_excl = sharpe_ratio(returns_excl, bar_seconds)

    drop_pct = (
        (original_sharpe - sharpe_excl) / abs(original_sharpe) if abs(original_sharpe) > 1e-9 else 0.0
    )

    return LeaveBestTradeOutResult(
        original_sharpe=original_sharpe,
        sharpe_excl_best=sharpe_excl,
        best_bar_return=float(best_value),
        best_bar_timestamp=str(best_idx),
        sharpe_drop_pct=float(drop_pct),
    )


def rolling_window_sharpe(returns: pd.Series, bar_seconds: float, n_windows: int = 4) -> RollingWindowResult:
    n = len(returns)
    if n < n_windows * 10:
        n_windows = max(1, n // 10)

    chunk_size = n // n_windows
    sharpes = []
    labels = []
    for i in range(n_windows):
        start = i * chunk_size
        end = n if i == n_windows - 1 else (i + 1) * chunk_size
        chunk = returns.iloc[start:end]
        s = sharpe_ratio(chunk, bar_seconds)
        sharpes.append(s)
        start_ts = str(chunk.index[0])[:10] if len(chunk) else "?"
        end_ts = str(chunk.index[-1])[:10] if len(chunk) else "?"
        labels.append(f"{start_ts}~{end_ts}")

    return RollingWindowResult(
        window_sharpes=sharpes,
        window_labels=labels,
        sharpe_std_across_windows=float(np.std(sharpes, ddof=1)) if len(sharpes) > 1 else 0.0,
        n_negative_windows=sum(1 for s in sharpes if s < 0),
        n_windows=len(sharpes),
    )
