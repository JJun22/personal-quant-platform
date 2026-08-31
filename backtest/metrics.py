"""
績效指標。

對應對話文件第7節：系統不能只存 Sharpe = 1.73 這種 point estimate，
還要能給出 CI，避免用「Sharpe 1.8 一定比 1.5 好」這種過度簡化的方式選策略。

V0 先用最直接的 stationary bootstrap 做 Sharpe 的 CI；
更嚴謹的 block bootstrap / permutation test 留到 Phase 3 Robustness Engine 再擴充，
但這裡先把「回傳的是分布而不是單一數字」這個介面定下來，之後好接。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class MetricEstimate:
    """一個指標的 point estimate + confidence interval。"""

    name: str
    value: float
    ci_low: float | None = None
    ci_high: float | None = None
    confidence: float = 0.90

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "value": self.value,
            "ci_low": self.ci_low,
            "ci_high": self.ci_high,
            "confidence": self.confidence,
        }


def annualization_factor(bar_seconds: float) -> float:
    seconds_per_year = 365 * 24 * 60 * 60
    return seconds_per_year / bar_seconds


def sharpe_ratio(returns: pd.Series, bar_seconds: float, risk_free: float = 0.0) -> float:
    excess = returns - risk_free
    std = excess.std(ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(annualization_factor(bar_seconds)))


def max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1.0
    return float(drawdown.min())


def cagr(equity_curve: pd.Series, bar_seconds: float) -> float:
    if len(equity_curve) < 2 or equity_curve.iloc[0] <= 0:
        return 0.0
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
    n_bars = len(equity_curve)
    years = (n_bars * bar_seconds) / (365 * 24 * 60 * 60)
    if years <= 0:
        return 0.0
    return float(total_return ** (1 / years) - 1)


def win_rate(returns: pd.Series) -> float:
    nonzero = returns[returns != 0]
    if len(nonzero) == 0:
        return 0.0
    return float((nonzero > 0).mean())


def bootstrap_sharpe_ci(
    returns: pd.Series,
    bar_seconds: float,
    n_boot: int = 2000,
    confidence: float = 0.90,
    block_size: int = 20,
    seed: int = 42,
) -> MetricEstimate:
    """
    Stationary/block bootstrap 估計 Sharpe 的信賴區間。
    用 block bootstrap 而不是逐點 iid resample，是因為金融報酬率有自相關/波動群聚，
    iid resample 會低估不確定性。
    """
    rng = np.random.default_rng(seed)
    arr = returns.to_numpy()
    n = len(arr)
    if n < block_size * 2:
        point = sharpe_ratio(returns, bar_seconds)
        return MetricEstimate("sharpe", point, None, None, confidence)

    boot_sharpes = np.empty(n_boot)
    n_blocks = int(np.ceil(n / block_size))
    for b in range(n_boot):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block_size) for s in starts])[:n]
        sample = arr[idx]
        mean_ = sample.mean()
        std_ = sample.std(ddof=1)
        boot_sharpes[b] = 0.0 if std_ == 0 else mean_ / std_ * np.sqrt(annualization_factor(bar_seconds))

    alpha = 1 - confidence
    ci_low, ci_high = np.quantile(boot_sharpes, [alpha / 2, 1 - alpha / 2])
    point = sharpe_ratio(returns, bar_seconds)
    return MetricEstimate("sharpe", point, float(ci_low), float(ci_high), confidence)


def sharpe_p_value(returns: pd.Series, bar_seconds: float, n_boot: int = 2000, seed: int = 42) -> float:
    """單尾檢定 H0: Sharpe <= 0 的 bootstrap p-value。

    先將報酬置中來建立「平均報酬為 0」的 null distribution，再用
    moving-block bootstrap 保留區塊內的時序依賴。這是 frequentist p-value，不是
    posterior probability。
    """
    rng = np.random.default_rng(seed)
    arr = returns.to_numpy()
    n = len(arr)
    block_size = min(20, max(1, n // 10))
    observed = sharpe_ratio(returns, bar_seconds)
    if n < block_size * 2 or observed <= 0:
        return 1.0

    n_blocks = int(np.ceil(n / block_size))
    centered = arr - arr.mean()
    null_sharpes = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n - block_size, size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block_size) for s in starts])[:n]
        sample = centered[idx]
        mean_ = sample.mean()
        std_ = sample.std(ddof=1)
        null_sharpes[b] = 0.0 if std_ == 0 else mean_ / std_ * np.sqrt(annualization_factor(bar_seconds))
    # +1 correction 避免 Monte Carlo p-value 變成精確的 0。
    return float((np.count_nonzero(null_sharpes >= observed) + 1) / (n_boot + 1))


def prob_sharpe_positive(returns: pd.Series, bar_seconds: float, n_boot: int = 2000, seed: int = 42) -> float:
    """舊 API 相容層；返回 1-p，不應解釋為 Bayesian posterior probability。"""
    return 1.0 - sharpe_p_value(returns, bar_seconds, n_boot=n_boot, seed=seed)


def compute_all_metrics(returns: pd.Series, equity_curve: pd.Series, bar_seconds: float) -> dict:
    sharpe_est = bootstrap_sharpe_ci(returns, bar_seconds)
    return {
        "sharpe": sharpe_est.as_dict(),
        "sharpe_p_value": sharpe_p_value(returns, bar_seconds),
        # 保留舊欄位使現有 report/registry 可讀；新程式應優先使用 sharpe_p_value。
        "p_sharpe_positive": prob_sharpe_positive(returns, bar_seconds),
        "cagr": cagr(equity_curve, bar_seconds),
        "max_drawdown": max_drawdown(equity_curve),
        "win_rate": win_rate(returns),
        "n_bars": len(returns),
    }
