"""
Multiple Comparisons / False Discovery Rate 追蹤。

對應對話文件裡反覆強調的核心風險：AI agent 可以用一萬倍速度做 data mining，
但如果沒有 multiple-testing 修正，跑 100 個參數組合、隨機出現 5 個「p<0.05」
是純統計期望值，不代表發現了真正的 edge。

這裡實作標準的 Benjamini-Hochberg 程序：給一組 p-value，回傳修正後
哪些還站得住腳（q-value <= alpha）。用在 param_perturbation / cost_stress
這種「搜尋」型 sweep 上——每個 trial 都要算一個 p-value，跑完整批 sweep
後再統一做 BH 修正，而不是逐一挑「看起來最好」的那個。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BHResult:
    n_trials: int
    n_significant_raw: int       # 沒修正前，p < alpha 的數量
    n_significant_adjusted: int  # BH 修正後，仍然顯著的數量
    rejected: list[bool]         # 對應輸入順序，是否通過 BH 修正
    q_values: list[float]        # 每個 trial 的 BH-adjusted p-value


def benjamini_hochberg(p_values: list[float], alpha: float = 0.10) -> BHResult:
    """標準 BH 程序。alpha 預設 0.10（比常見的 0.05 寬鬆一點，
    因為 V0 sweep 的 trial 數還不大，用 0.05 幾乎篩不掉任何東西沒有教育意義；
    正式研究階段應該調回 0.05 甚至更嚴）。"""
    n = len(p_values)
    if n == 0:
        return BHResult(0, 0, 0, [], [])

    order = np.argsort(p_values)
    sorted_p = np.array(p_values)[order]

    # BH critical values: p_(i) <= (i/n) * alpha
    thresholds = (np.arange(1, n + 1) / n) * alpha
    passed = sorted_p <= thresholds

    if passed.any():
        max_i = np.max(np.where(passed)[0])  # 最大的通過的 index（0-indexed）
    else:
        max_i = -1

    rejected_sorted = np.zeros(n, dtype=bool)
    rejected_sorted[: max_i + 1] = True

    # q-value：從最大的 p 開始往回取 cumulative min，是標準 BH q-value 定義
    q_sorted = sorted_p * n / np.arange(1, n + 1)
    q_sorted = np.minimum.accumulate(q_sorted[::-1])[::-1]
    q_sorted = np.clip(q_sorted, 0, 1)

    # 還原成輸入順序
    rejected = np.empty(n, dtype=bool)
    q_values = np.empty(n, dtype=float)
    rejected[order] = rejected_sorted
    q_values[order] = q_sorted

    n_raw = int(np.sum(np.array(p_values) < alpha))
    n_adjusted = int(rejected.sum())

    return BHResult(
        n_trials=n,
        n_significant_raw=n_raw,
        n_significant_adjusted=n_adjusted,
        rejected=rejected.tolist(),
        q_values=q_values.tolist(),
    )
