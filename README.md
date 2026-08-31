# Personal Quant Research & Trading Platform

一套以 **evidence-driven research、falsification、reproducibility** 為核心的個人量化研究與交易平台。

這個專案的長期目標不是只做一個「可以回測、可以送單」的 trading bot，而是建立完整的策略生命週期：

```text
Ideas / Hypotheses
        ↓
Research & Falsification (Phase 0–5)
        ↓
Validated Strategy Registry
        ↓
Portfolio Selection & Allocation (Phase 6)
        ↓
Paper → Shadow → Limited Live → Live (Phase 7)
        ↓
Monitoring, Governance & Feedback (Phase 8)
        ↓
Keep / Resize / Suspend / Return to Research / Retire
```

目前 repository 是這個願景的 **V0 research foundation**：已經能讓單一 Python 策略通過標準回測、experiment lineage、基礎統計估計與 robustness suite，但尚未完成 OOS、portfolio allocation、paper/live execution 與 production monitoring。

> [!IMPORTANT]
> 本專案目前只適合研究與架構開發，不應直接用於真實資金交易。現有範例使用合成資料，尚未建立完整的交易所連線、帳戶對帳、風控與 kill switch。

---

## 1. Project Philosophy

### 1.1 Research 和 Trading 必須分離

Research system 問的是：

> 這個策略是否有足夠證據支持它可能存在可重複的 edge？

Trading system 問的是：

> 即使策略有 edge，在現有 portfolio、成本、資本、風險與市場狀態下，是否值得配置真實 risk budget？

因此：

```text
VALIDATED ≠ TRADABLE ≠ SHOULD BE ALLOCATED
```

Research 通過的策略只會取得進入 portfolio-selection 的資格，不會自動進入實盤。

### 1.2 目標不是證明策略有效，而是嘗試摧毀它

每一個 hypothesis 都應接受相同的 falsification protocol：

```text
Baseline
  ↓
Data / causality checks
  ↓
Statistical uncertainty
  ↓
Parameter / cost / delay / sample stress
  ↓
Regime explanation
  ↓
Out-of-sample / walk-forward
```

大多數策略被淘汰是健康的結果。系統的價值不在於產生大量漂亮 backtest，而在於讓少數經得起攻擊的策略留下。

### 1.3 每一個結果都必須可追溯

任何研究結果最終都應能回答：

- 使用哪一份 dataset？
- data／resample 規則是哪一版？
- strategy code 與 parameters 是哪一版？
- commission、slippage、delay 假設是什麼？
- 屬於哪個 experiment 和 testing family？
- 通過／失敗在哪個 phase？原因是什麼？
- 產生了哪些 signals、positions、orders、fills、returns 與 reports？

目前 Registry 已完成其中的最小 lineage 子集，完整 evidence package 仍在 roadmap 中。

---

## 2. Target Architecture

```text
                          IDEA SOURCES
                 Human / DSL / ML / AI Agent
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    RESEARCH SYSTEM                          │
│  P0 Hypothesis                                              │
│       ↓                                                     │
│  P1 Data & Causality Integrity                              │
│       ↓                                                     │
│  P2 Statistical Evidence                                    │
│       ↓                                                     │
│  P3 Robustness & Falsification                              │
│       ↓                                                     │
│  P4 Regime & Economic Explanation                           │
│       ↓                                                     │
│  P5 OOS / Walk-Forward                                      │
└───────────────────────────────┬─────────────────────────────┘
                                ▼
                    VALIDATED STRATEGY REGISTRY
                    Evidence + Artifacts + Failures
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    TRADING SYSTEM                           │
│  P6 Portfolio Contribution & Allocation                     │
│       ↓                                                     │
│  P7 Replay / Paper / Shadow / Live Execution                │
│       ↓                                                     │
│  P8 Monitoring / Governance / Feedback                      │
└───────────────────────────────┬─────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
            KEEP              RESIZE            SUSPEND
                                                    │
                                      ┌─────────────┴──────────┐
                                      ▼                        ▼
                              RETURN TO RESEARCH              RETIRE
```

長期的三個 strategy pools：

| Pool | 意義 | 是否配置資金 |
|---|---|---|
| Idea Pool | 尚未驗證的 hypotheses | 否 |
| Validated Strategy Pool | 通過 P0–P5、具 evidence package 的候選策略 | 不一定 |
| Active Strategy Pool | 通過 P6 並進入 paper／shadow／live 的策略 | 視狀態而定 |

---

## 3. Current Status

### 3.1 Phase 進度

| Phase | 名稱 | 狀態 | 目前完成內容 |
|---|---|---:|---|
| P0 | Hypothesis Formalization | Partial | Strategy ABC、metadata、parameters、description |
| P1 | Data & Causality Integrity | Partial | OHLCV schema、時間索引、signal validation、next-open execution、PnL timing tests |
| P2 | Statistical Evidence | Partial | Sharpe、block-bootstrap CI、null-bootstrap p-value、基礎 metrics |
| P3 | Robustness & Falsification | Partial | parameter、cost、delay、sample perturbation、BH correction |
| P4 | Regime & Economic Explanation | Planned | 尚未實作 |
| P5 | OOS / Walk-Forward | Planned | 尚未實作 |
| P6 | Portfolio Contribution & Allocation | Planned | 尚未實作 |
| P7 | Paper / Shadow / Live Execution | Planned | 只有 Broker abstraction 與 BacktestBroker |
| P8 | Monitoring / Governance / Feedback | Planned | 尚未實作 |

目前更精確的版本定位：

```text
V0A  Single-strategy end-to-end backtest               Implemented
V0B  Reproducible experiment lineage                   Partial
V0C  Robustness / falsification suite                  Partial
V0D  Trusted backtest accounting + regression tests    Implemented
```

### 3.2 已經可以做什麼

- 產生或讀取 canonical 1-minute OHLCV
- resample 成 5m／15m／1h／4h／1d
- 透過統一 Strategy API 產生 target positions
- 以 next-open execution 跑單資產 backtest
- 正確區分 overnight 與 intraday PnL ownership
- 計算基礎績效、Sharpe CI 與 Sharpe null p-value
- 把 dataset、strategy version、cost model、run 與 metrics 寫入 SQLite
- 執行 parameter、cost、execution-delay 與 sample robustness tests
- 對 parameter candidate family 做 Benjamini–Hochberg correction
- 產生標準化 Markdown research report
- 用 deterministic regression tests 保護 accounting 與 Registry semantics

### 3.3 現在不能做什麼

- 不能據此聲稱 SMA strategy 有 edge
- 尚未接入可信的 point-in-time 真實市場資料
- 尚未完成 trade-level artifact persistence
- 尚未完成正式 PASS／WARN／FAIL gate
- 尚未做 regime、OOS 或 walk-forward
- 尚未管理多資產與多策略 portfolio
- 尚未 paper、shadow 或 live trading
- 尚未具備 production risk controls、reconciliation 或 monitoring

---

## 4. Quick Start

### 4.1 Requirements

- Python 3.11+ recommended
- `pandas`
- `numpy`

```bash
pip install -r requirements.txt
```

有真實資料需求時預計加入：

```bash
pip install pyarrow ccxt
```

### 4.2 Package location

Repository 本身就是 `quant_platform` package，請從 repository 的父目錄執行 module commands：

```text
parent-directory/
└── quant_platform/
```

### 4.3 跑單一 experiment

```bash
cd <quant_platform 的父目錄>
python -m quant_platform.run_experiment \
  --timeframe 1h \
  --fast 20 \
  --slow 100
```

執行流程：

```text
Synthetic 1m OHLCV（如本地尚無資料）
  → Resample
  → SmaCrossStrategy
  → BacktestBroker
  → Metrics + uncertainty
  → SQLite Registry
  → Markdown report
```

### 4.4 跑 robustness suite

```bash
cd <quant_platform 的父目錄>
python -m quant_platform.run_robustness \
  --timeframe 4h \
  --fast 20 \
  --slow 100
```

一次執行 baseline、parameter perturbation、cost stress、execution delay、sample perturbation、parameter-family BH correction、Registry persistence 與 report generation。

### 4.5 跑測試

```bash
cd <quant_platform 的父目錄>
python -m unittest discover -s quant_platform/tests -v
```

目前測試保護：

- 新部位不能取得成交前的 overnight gap
- 舊部位必須取得持倉期間的 overnight gap
- 在 open 平倉後不能取得之後的 intraday move
- Strategy parameters 必須是 version identity 的一部分
- Registry run summary 必須正確還原欄位與參數
- 正 Sharpe synthetic signal 應得到合理的小 null p-value
- 負 Sharpe 不應拒絕 `H0: Sharpe <= 0`

---

## 5. Phase 0–8 Protocol

### Phase 0 — Hypothesis Formalization

**Goal:** 在看到回測結果前，先把策略主張轉成可測試、可否證的 specification。

預期完整內容：

- hypothesis 與 economic mechanism
- instrument／universe／timeframe
- information cutoff
- entry／exit／holding period
- sizing 與 exposure assumptions
- 預期有效與失效 regime
- transaction-cost assumptions
- 預先定義的 falsification criteria

目前實作：

| File | Role |
|---|---|
| `strategy/base.py` | `Strategy` ABC、`StrategyMeta` |
| `strategy/examples/sma_cross.py` | 最小 SMA crossover 驗收策略 |

缺口：formal hypothesis schema、machine-readable strategy spec、pre-registration、DSL、相似 hypothesis／failure lookup。

### Phase 1 — Data & Causality Integrity

**Goal:** 在評估績效前，先確認資料、訊號、成交與損益時間線沒有錯誤或 leakage。

目前實作：

- canonical 1m OHLCV schema
- timezone-aware `DatetimeIndex`
- monotonic／duplicate timestamp validation
- signal index、NaN、range validation
- signal 在 `t` 形成後，最早於 `t+1 open` 成交
- 舊部位承擔 `previous close → execution open`
- 新部位承擔 `execution open → close`
- accounting regression tests

| File | Role |
|---|---|
| `data/loader.py` | 載入、驗證與 resample OHLCV |
| `data/synth.py` | 產生可重現的 synthetic data |
| `backtest/broker.py` | next-open execution、cost 與 PnL accounting |
| `tests/test_broker.py` | causal timing regression tests |

主要缺口：

- missing-bar／bad-tick／OHLC consistency checks
- exchange outage 與 stale data detection
- point-in-time universe 與 delisting
- feature availability／publication lag
- automated truncation／future-mutation leakage tests
- resample、loader、calendar implementation fingerprints
- immutable raw-data manifest

### Phase 2 — Statistical Evidence

**Goal:** 不用單一 point estimate 判斷策略，而是衡量 effect size、不確定性與 false-discovery risk。

目前實作：

- Sharpe ratio
- moving-block bootstrap Sharpe confidence interval
- centered moving-block null bootstrap
- one-sided `H0: Sharpe <= 0` p-value
- CAGR、max drawdown、bar-level win rate
- Benjamini–Hochberg procedure

| File | Role |
|---|---|
| `backtest/metrics.py` | Metrics、CI 與 null-bootstrap p-value |
| `robustness/trials.py` | BH false-discovery-rate correction |
| `tests/test_metrics.py` | Statistical evidence regression tests |

主要缺口：

- annualized volatility、Sortino、Calmar、profit factor
- trade-level expectancy／win rate／holding period
- turnover、exposure、tail ratio、skew、kurtosis、CVaR
- drawdown duration／recovery
- Probabilistic／Deflated Sharpe Ratio
- minimum track-record length 與 power analysis
- stationary／trade-level bootstrap、permutation tests
- 正式定義 hypothesis、trial 與 testing family

> `p_sharpe_positive` 只為舊 Registry/report 相容而保留。新程式應以 `sharpe_p_value` 為正式 evidence 欄位，不應把 `1-p` 解讀成 Bayesian posterior probability。

### Phase 3 — Robustness & Falsification

**Goal:** 主動改變參數、成本、執行與樣本，檢查績效是否只存在於脆弱的單一設定。

目前實作：

- **Parameter perturbation:** 各數值參數做 ±10%／±20% 一維擾動
- **Cost stress:** commission 與 slippage 放大 1x／1.5x／2x／3x
- **Execution delay:** 額外增加 0／1／2／3 bars
- **Sample perturbation:** leave-best-bar-out、non-overlapping rolling-window Sharpe
- **Multiple testing:** parameter candidate family 使用 BH correction

Cost 和 delay 是 robustness diagnostics，不被當成額外 alpha discoveries。

| File | Role |
|---|---|
| `robustness/engine.py` | 串接完整 robustness suite |
| `robustness/param_perturbation.py` | Parameter sensitivity |
| `robustness/cost_stress.py` | Cost sensitivity |
| `robustness/execution_delay.py` | Delay sensitivity |
| `robustness/sample_perturbation.py` | Sample concentration diagnostics |

主要缺口：

- multi-parameter joint grid／surface
- plateau／island detection
- random parameter sampling
- remove best N trades／month／year
- random start/end dates 與 block subsampling
- universe／symbol／exchange perturbation
- nonlinear slippage、spread、partial fill、market impact
- machine-readable `PASS / WARN / FAIL`
- standardized failure reason taxonomy

### Phase 4 — Regime & Economic Explanation

**Goal:** 解釋 edge 在什麼環境存在、何時失效，以及是否符合原始 economic hypothesis。

Planned capabilities：

- bull／bear／sideways
- high／low volatility、liquidity
- trend strength、funding／carry、risk-on／risk-off
- regime-conditional returns、drawdown 與 correlation
- predefined vs exploratory regime separation
- beta／trend／carry／liquidity factor attribution
- strategy failure-condition profile

預期輸出：

```yaml
regime_profile:
  works: [high_vol_trend]
  weak: [low_vol_trend]
  fails: [low_vol_sideways]
```

Status：**Planned — 尚未實作。**

### Phase 5 — Out-of-Sample / Walk-Forward

**Goal:** 凍結研究決策後，檢查策略在未見資料上的可重複性與 degradation。

Planned capabilities：

- train／validation／test separation
- immutable holdout
- expanding／rolling walk-forward
- purge／embargo
- fold-level parameter freeze
- OOS aggregation、IS-to-OOS degradation
- positive-fold ratio、worst-fold diagnostics
- live-like chronological replay
- ML model／feature／seed artifact lineage

```text
Train 2018–2021 → Test 2022
Train 2019–2022 → Test 2023
Train 2020–2023 → Test 2024
```

P0–P5 通過後，strategy version 才能進入 Validated Strategy Registry。

Status：**Planned — 尚未實作。**

### Phase 6 — Portfolio Contribution & Allocation

**Goal:** 不再問「哪個策略 Sharpe 最高」，而是問「加入現有 portfolio 後帶來多少 marginal value」。

Planned capabilities：

- multi-strategy return alignment
- return／downside／tail correlation
- regime-conditional correlation
- marginal Sharpe、drawdown 與 CVaR
- factor exposure、risk contribution
- capital／turnover／capacity constraints
- equal-risk、volatility targeting、risk parity
- constrained optimization
- portfolio acceptance decision

```text
Validated Strategy
        ↓
Correlation / Tail Risk / Capacity / Marginal Value
        ↓
REJECT / WATCH / PAPER / ALLOCATE
```

Status：**Planned — 尚未實作。**

### Phase 7 — Replay / Paper / Shadow / Live Execution

**Goal:** 以可恢復、可對帳、可限制風險的方式把 portfolio targets 轉成真實 orders 與 fills。

```text
Historical Backtest
  → Historical Replay
  → Paper Trading
  → Shadow Trading
  → Canary / Limited Live
  → Live Allocation
```

Planned components：

- `PaperBroker`、`ExchangeBroker`
- market-data stream、signal scheduler
- portfolio target generator
- order／execution manager
- partial fill／reject／cancel lifecycle
- position與account reconciliation
- persistent state／restart recovery
- idempotent order submission
- leverage、exposure、daily-loss、drawdown limits
- stale-data／duplicate-order protection
- kill switch／emergency flatten

目前只有 `Broker` interface、`BacktestBroker` 與簡化的 `Fill`／`BacktestResult`。

Status：**Foundation only — 不可 live trading。**

### Phase 8 — Monitoring, Governance & Feedback

**Goal:** 監控系統與策略是否仍符合研究假設，並管理完整 strategy lifecycle。

Planned monitoring：

- process／data heartbeat
- data freshness／missing bars
- API errors／latency／rejections
- expected vs realized slippage
- position／balance mismatch
- return／volatility／turnover drift
- signal／feature／correlation drift
- live drawdown、strategy health score
- alerts、incident log、postmortem
- backup／restore、secret management、access control

Planned state machine：

```text
IDEA
  → RESEARCHING
  → VALIDATED
  → PORTFOLIO_CANDIDATE
  → PAPER
  → SHADOW
  → LIVE_LIMITED
  → LIVE
  → SUSPENDED
  → RETIRED
```

每次 transition 最終應保存 evidence snapshot、reason、timestamp、configuration 與 rollback decision。

Status：**Planned — 尚未實作。**

---

## 6. Repository Structure

```text
quant_platform/
├── backtest/
│   ├── broker.py              # Broker ABC, BacktestBroker, Fill, PnL accounting
│   ├── metrics.py             # Metrics, Sharpe CI, null-bootstrap evidence
│   └── simulator.py           # Strategy → Broker → Metrics orchestration
├── data/
│   ├── loader.py              # OHLCV validation, checksum, resampling
│   └── synth.py               # Reproducible synthetic 1m OHLCV
├── registry/
│   ├── db.py                  # SQLite schema
│   └── repository.py          # Dataset/strategy/run/sweep persistence
├── report/
│   └── generate.py            # Markdown run and robustness reports
├── robustness/
│   ├── engine.py
│   ├── param_perturbation.py
│   ├── cost_stress.py
│   ├── execution_delay.py
│   ├── sample_perturbation.py
│   └── trials.py
├── strategy/
│   ├── base.py                # Strategy ABC + metadata
│   └── examples/sma_cross.py  # Smoke-test strategy
├── tests/
│   ├── test_broker.py
│   ├── test_metrics.py
│   └── test_registry.py
├── storage/                    # Generated contents ignored by Git
├── config.py
├── runner.py
├── run_experiment.py
├── run_robustness.py
├── requirements.txt
└── README.md
```

---

## 7. Registry & Experiment Lineage

目前 SQLite entities：

```text
Dataset
Strategy
StrategyVersion
Experiment
Run
Metric
Sweep
SweepRun
```

一次 run 會記錄 dataset identity、strategy implementation與parameters、experiment、cost model、status、timestamps、metrics，以及 sweep membership。

尚未落地：

- signals、positions、orders、fills、returns artifacts
- hypothesis、protocol version、phase decision
- failure reasons／Failure Knowledge Base
- regime profile、OOS folds
- portfolio decision／allocation
- deployment／live observation／incident

目標不是只把 Registry 當成結果資料庫，而是讓它成為 research memory 與 strategy evidence system。

---

## 8. Data

目前預設使用 synthetic BTC/USDT-like 1m OHLCV：

- fixed random seed
- weak drift
- volatility clustering
- generated volume
- open anchored to previous close

它的用途是驗證 pipeline，不是驗證 trading edge。

接入真實資料時，loader 應輸出：

```python
DatetimeIndex(tz="UTC")
columns = ["open", "high", "low", "close", "volume"]
```

建議使用 immutable Parquet snapshot，並為 raw source、download time、loader、calendar 與 resample rules 建立 manifest 和 fingerprints。

---

## 9. How to Interpret Research Results

```text
Sharpe = 1.2
```

不代表策略可交易。至少還要問：

- CI 是否很寬？
- null p-value 是否合理？
- 是否經過完整 trial-family correction？
- 成本放大後是否消失？
- 參數附近是否是 plateau？
- 是否依賴最佳 bar／月份？
- 在不同 regime 是否有合理行為？
- OOS／walk-forward 是否維持？
- 對現有 portfolio 是否有 marginal value？

合成近隨機資料上的 SMA crossover 被判定為負 Sharpe，是預期結果。Smoke-test strategy 的任務是揭露 pipeline bugs，而不是示範獲利策略。

---

## 10. Roadmap

### V0E — P1 Integrity & Artifact Persistence

- 完整 OHLC data-quality validation
- signals／positions／fills／returns 落地
- loader／resample fingerprints
- dataset manifest
- machine-readable phase result

### V0F — P2 Statistical Evidence

- 完整 performance／risk／trade metrics
- trial ledger 與 testing-family definition
- Deflated／Probabilistic Sharpe
- stronger bootstrap／permutation framework

### V0G — P3 Robustness Gates

- multi-parameter surfaces
- sample／universe perturbation
- realistic execution stress
- `PASS / WARN / FAIL`
- failure reason taxonomy／Failure Knowledge Base

### V1 — Complete Research System

- P4 regime analysis
- P5 walk-forward／OOS
- validated evidence package
- Registry lifecycle states

### V2 — Portfolio System

- multi-strategy alignment
- portfolio contribution tests
- risk allocation
- capacity／turnover／tail constraints

### V3 — Trading Incubation

- replay、paper broker、shadow execution
- reconciliation
- hard risk controls

### V4 — Limited Live & Operations

- canary allocation
- monitoring／alerts
- strategy health score
- governance／incident／feedback loop

---

## 11. Design Rules

1. Research strategy 不直接控制真實 orders。
2. 所有 alpha sources 都必須通過相同 P0–P5 protocol。
3. Strategy code、parameters、dataset、cost model 與 protocol 都必須版本化。
4. `VALIDATED` 不代表自動配置資金。
5. Cost、delay、regime 與 OOS 結果最終都必須 machine-readable。
6. 失敗實驗是研究資產，不能只保留成功策略。
7. Backtest、paper、shadow、live 應共享 strategy semantics，但 execution adapters 必須分離。
8. Live deployment 前必須具備 hard risk limits、reconciliation、restart recovery 與 kill switch。

---

## 12. Disclaimer

This repository is an educational and research project. It does not provide financial advice and does not guarantee profitability. Backtests, synthetic-data results, statistical estimates, and robustness reports can all be wrong or fail to generalize. Do not trade real capital without independent validation, operational safeguards, and a clear understanding of the risks.
