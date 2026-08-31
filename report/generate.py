"""
把一次 run 的結果轉成標準化 markdown report。

V0 先求「格式固定、資訊完整」，之後 Phase 3 Robustness Engine 接上後，
report 會再加上 parameter perturbation / cost stress 等區塊，
但這裡先把「單一 run 的 report 長什麼樣」定下來。
"""
from __future__ import annotations

from pathlib import Path

from quant_platform.backtest.simulator import RunResult


def render_run_report(run_id: str, result: RunResult, dataset_info: dict) -> str:
    m = result.metrics
    sharpe = m["sharpe"]
    lines = [
        f"# Research Report: {result.strategy_meta['name']} ({result.strategy_meta['version_label']})",
        "",
        f"- run_id: `{run_id}`",
        f"- timeframe: {result.timeframe}",
        f"- dataset: {dataset_info.get('symbol')} / {dataset_info.get('timeframe')} "
        f"(checksum={dataset_info.get('checksum')})",
        f"- params: `{result.strategy_meta['params']}`",
        "",
        "## Headline Metrics (with uncertainty)",
        "",
        f"- Sharpe: {sharpe['value']:.2f}  "
        f"(90% CI: [{sharpe['ci_low']:.2f}, {sharpe['ci_high']:.2f}])"
        if sharpe["ci_low"] is not None
        else f"- Sharpe: {sharpe['value']:.2f} (樣本太少，無法估計 CI)",
        f"- Sharpe one-sided p-value (H0: Sharpe <= 0): {m['sharpe_p_value']:.3f}",
        f"- CAGR: {m['cagr']*100:.1f}%",
        f"- Max Drawdown: {m['max_drawdown']*100:.1f}%",
        f"- Win rate (per bar with position change): {m['win_rate']*100:.1f}%",
        f"- N bars: {m['n_bars']}",
        "",
        "## Diagnostics",
        "",
        f"- Number of trades (position changes): {result.diagnostics['n_trades']}",
        f"- Avg absolute exposure: {result.diagnostics['avg_position_abs']:.2f}",
        f"- Time in market: {result.diagnostics['time_in_market_pct']:.1f}%",
        "",
        "## Interpretation Notes",
        "",
        "- 這是 V0 baseline report：只跑了單一參數組合，尚未經過 Phase 3 "
        "(parameter perturbation / cost stress / multiple testing) 檢驗。",
        "- Sharpe CI 是用 block bootstrap 估計，樣本內波動群聚已部分納入考量，"
        "但仍然是 in-sample 結果，不代表 out-of-sample 表現。",
        "- 在把這個策略當作『有效』之前，至少要先過 P2 (Statistical Evidence) "
        "與 P3 (Robustness) 兩關。",
        "",
    ]
    return "\n".join(lines)


def save_report(report_text: str, out_dir: Path, run_id: str) -> Path:
    out_path = out_dir / f"{run_id}.md"
    out_path.write_text(report_text, encoding="utf-8")
    return out_path


def render_robustness_report(report) -> str:
    """把 RobustnessReport（robustness/engine.py）轉成 markdown。
    刻意用 duck typing 而不 import RobustnessReport type，避免 report 層反過來依賴 robustness 層。"""
    base = report.base_result
    lines = [
        f"# Robustness Report: {base.strategy_meta['name']} ({base.strategy_meta['version_label']})",
        "",
        f"- base_run_id: `{report.base_run_id}`",
        f"- base params: `{base.strategy_meta['params']}`",
        f"- base Sharpe: {base.metrics['sharpe']['value']:.2f}",
        "",
        "## 1. Parameter Perturbation",
        "",
        f"共測試 {len(report.param_trials)} 組參數（各參數獨立 ±10%/±20% 擾動）：",
        "",
        "| 擾動 | 參數 | Sharpe | p-value (H0: Sharpe<=0) |",
        "|---|---|---|---|",
    ]
    for t in report.param_trials:
        if t.skipped_reason:
            lines.append(f"| {t.label} | {t.params} | 跳過 | {t.skipped_reason} |")
        else:
            lines.append(f"| {t.label} | {t.params} | {t.sharpe:.2f} | {t.sharpe_p_value:.3f} |")

    stab = report.param_stability
    lines += [
        "",
        f"- 有效 trial: {stab.get('n_valid', 0)}（跳過 {stab.get('n_skipped', 0)} 組無效參數）",
        f"- Sharpe 範圍: [{stab.get('sharpe_min', float('nan')):.2f}, {stab.get('sharpe_max', float('nan')):.2f}]"
        f"，標準差: {stab.get('sharpe_std', float('nan')):.2f}",
        "- 判讀：標準差越小、範圍越窄，代表績效在參數鄰域內越平滑穩定；"
        "如果 baseline 附近的組合表現差異巨大，通常是曲線擬合的警訊。",
        "",
        "## 2. Cost Stress",
        "",
        "| 成本倍數 | Commission (bps) | Slippage (bps) | Sharpe |",
        "|---|---|---|---|",
    ]
    for t in report.cost_trials:
        lines.append(f"| {t.multiplier:g}x | {t.commission_bps:.2f} | {t.slippage_bps:.2f} | {t.sharpe:.2f} |")
    breakeven = report.cost_breakeven_multiplier
    lines += [
        "",
        f"- Breakeven 倍數: {f'{breakeven:g}x' if breakeven else '測試範圍內未轉負（>=3x 仍為正）'}",
        "- 判讀：這個策略能撐到成本放大幾倍還維持正 Sharpe。倍數越低代表獲利越薄，"
        "越可能在真實交易所的實際滑價下消失。",
        "",
        "## 3. Execution Delay Sensitivity",
        "",
        "| 額外延遲 (bars) | Sharpe |",
        "|---|---|",
    ]
    for t in report.delay_trials:
        lines.append(f"| +{t.extra_delay_bars} | {t.sharpe:.2f} |")
    lines += [
        "",
        "- 判讀：如果 Sharpe 隨延遲增加而快速崩壞，代表策略高度依賴精確的進出場時機，"
        "實盤環境（網路延遲、排程間隔）很難重現這種精度。",
        "",
        "## 4. Sample Perturbation",
        "",
        "**Leave-best-trade-out：**",
        f"- 原始 Sharpe: {report.leave_best_trade_out.original_sharpe:.2f}",
        f"- 拿掉最佳單根 bar 後 Sharpe: {report.leave_best_trade_out.sharpe_excl_best:.2f}"
        f"（下降 {report.leave_best_trade_out.sharpe_drop_pct*100:.0f}%）",
        f"- 最佳 bar 發生於: {report.leave_best_trade_out.best_bar_timestamp}",
        "",
        "**Rolling-window Sharpe（切成不重疊區塊分別計算）：**",
        "",
        "| 區間 | Sharpe |",
        "|---|---|",
    ]
    for label, s in zip(report.rolling_window.window_labels, report.rolling_window.window_sharpes):
        lines.append(f"| {label} | {s:.2f} |")
    lines += [
        "",
        f"- 區塊間 Sharpe 標準差: {report.rolling_window.sharpe_std_across_windows:.2f}",
        f"- 負報酬區塊數: {report.rolling_window.n_negative_windows}/{report.rolling_window.n_windows}",
        "- 判讀：如果績效集中在少數區塊、其餘區塊都是負的，代表這不是穩定存在的 edge，"
        "而是某段特殊市場狀況下的偶然結果。",
        "",
        "## 5. Parameter-Family Multiple-Testing Correction (Benjamini-Hochberg, α=0.10)",
        "",
        f"- 本次 parameter candidate family 共有 {report.bh_result.n_trials} 個 trial",
        f"- 未修正前 p<0.10 的 trial 數: {report.bh_result.n_significant_raw}",
        f"- **BH 修正後仍顯著的 trial 數: {report.bh_result.n_significant_adjusted}**",
        "- Cost stress 和 execution delay 是 robustness diagnostics，不算成新的 alpha hypotheses。",
        "",
        "- 判讀：如果 BH 修正後顯著的 trial 數是 0，代表這一整批搜尋沒有找到"
        "能通過統計把關的結果——在接近隨機遊走的資料上，這是**正確且預期**的結論，"
        "說明整套 falsification 機制正在如實運作，而不是隨便放行任何看起來好看的數字。",
        "",
    ]
    return "\n".join(lines)
