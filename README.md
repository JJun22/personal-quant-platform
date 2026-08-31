# Personal Quant Research & Execution Platform — V0

Evidence-Driven Trading Research System 的 V0 骨架。目前完成 **V0A（單策略跑通全程）**
+ **V0B（可重現、可追蹤的 experiment lineage）** + **V0C（Robustness / Falsification
Engine 雛形）**。

## V0A + V0B：跑單一策略

```
python -m quant_platform.run_experiment --timeframe 1h --fast 20 --slow 100
```

會依序：

1. 若本地沒有資料，用 `data/synth.py` 產生一份合成 1m OHLCV（見下方「關於資料」）。
2. 把 1m 資料 resample 成指定 timeframe（`data/loader.py`，1m 為 canonical base）。
3. 用 `SmaCrossStrategy` 產生 signal，丟進 `BacktestBroker` 跑出
   Signal → Position → Order/Fill → PnL 的完整事件鏈（`backtest/`）。
4. 計算績效指標，**包含 Sharpe 的 bootstrap 信賴區間**，不是只有 point estimate
   （`backtest/metrics.py`，對應對話文件第7節）。
5. 把這次 run 的完整身分 —— 用了哪個 dataset checksum、哪個 strategy version
   （用程式碼 hash 當 fingerprint）、哪組 cost model —— 寫進 SQLite Registry
   （`registry/`，對應文件第9節 lineage 設計）。
6. 產生一份 markdown research report（`report/`）。

重跑同樣的策略/參數會重用同一個 `strategy_version`；重跑同一份底層資料
（用 checksum 判斷）會重用同一個 `dataset` row。每次 run 都有獨立的 `run_id`
可以回溯完整參數與結果。

## 關於資料：目前是合成的

這個 sandbox **沒有對外網路**，沒辦法直接接 Binance/ccxt 拉真實 BTC/USDT 資料，
也裝不了 `pyarrow`（所以先用 pandas 內建的 pickle 存資料，不是文件裡建議的 parquet）。

要接真實資料時：

1. 在有網路的環境安裝 `ccxt`，寫一個 `data/exchange_loader.py`，
   輸出跟 `synth.py` 一樣 schema 的 DataFrame（index=UTC DatetimeIndex,
   columns=[open,high,low,close,volume]），存檔路徑放進 `config.DATA_DIR`。
2. 有 `pyarrow` 的話，把 `data/synth.py` 的 `to_pickle` 和 `data/loader.py` 的
   `read_pickle` 換回 `to_parquet` / `read_parquet`（原本設計就是為此留的縫）。
3. 其餘所有層（strategy/backtest/registry/report）完全不用動。

## V0C：跑完整 Robustness / Falsification Suite

```
python -m quant_platform.run_robustness --timeframe 4h --fast 20 --slow 100
```

一次會做：

1. **Parameter perturbation**（`robustness/param_perturbation.py`）：`fast`/`slow`
   各自獨立做 ±10%/±20% 擾動，檢查績效是否只是孤島最佳點。
2. **Cost stress**（`robustness/cost_stress.py`）：commission/slippage 同時放大
   1x/1.5x/2x/3x，找出 Sharpe 轉負的 breakeven 倍數。
3. **Execution delay sensitivity**（`robustness/execution_delay.py`）：在既有的
   1-bar 必要延遲之上，再多延遲 0/1/2/3 根 bar，檢查對進出場時機的依賴程度。
4. **Sample perturbation**（`robustness/sample_perturbation.py`）：
   leave-best-trade-out（拿掉單筆最佳報酬看 Sharpe 掉多少）+
   rolling-window Sharpe（切成不重疊區塊看績效是否集中在特定時段）。
5. **Multiple-testing correction**（`robustness/trials.py`）：對 parameter candidate
   family 作 Benjamini-Hochberg 修正（α=0.10）。Cost stress 和 execution
   delay 是穩健性診斷，不當成額外的 alpha discoveries。

Sharpe 顯著性使用「報酬置中後」的 moving-block null bootstrap 估計單尾
`H0: Sharpe <= 0` p-value，不再把觀察樣本自身的 bootstrap 比例當成 posterior
probability。

每個 trial 都是一次完整、獨立記錄進 Registry 的 run（`sweeps`/`sweep_runs` 表
記錄哪些 run 屬於同一次 sweep），所以 V0C 會比 V0A 產生多很多筆 run 紀錄——
這是刻意的，穩健性判斷本來就需要足夠的樣本數才有意義。

在合成的近隨機遊走資料上驗證過：SMA crossover 的 breakeven 倍數是 1x
（一開始就是負的）、BH 修正後沒有任何 trial 顯著——這是**正確且預期**的結果，
代表 falsification 機制有把關到，不是隨便放行漂亮數字。

## 架構對照（vs. 今天的設計文件）

| 文件章節 | 對應程式 |
|---|---|
| 4.1 Market Data Layer | `data/loader.py`, `data/synth.py` |
| 4.2/4.3 Strategy + Simulator | `strategy/base.py`, `backtest/simulator.py`, `backtest/broker.py` |
| 第7節 Uncertainty（不只存 point estimate）| `backtest/metrics.py` 的 `bootstrap_sharpe_ci` |
| 第9節 Strategy Registry / Lineage | `registry/db.py`, `registry/repository.py` |
| Phase 3 Robustness/Falsification Engine | `robustness/`（param perturbation, cost stress, execution delay, sample perturbation, BH correction）|
| Phase 0-8 protocol | 目前做到 P0（可測試 hypothesis）雛形 + P1 基本防線 + P3 的四項穩健性檢查雛形，P2（更完整的統計檢定框架）跟 P4-P8 尚未開始 |

## 已經內建的 P1 (Data & Causality Integrity) 防線

- `data/loader._validate_ohlcv_schema`：強制檢查 index 必須是帶時區的
  DatetimeIndex、嚴格遞增、不可重複。
- `strategy/base.Strategy.validate_signals`：signal 必須跟輸入資料完全對齊、
  不可有 NaN、不可超出 [-1,1]。
- `backtest/broker.BacktestBroker`：signal 會被 lag 一根 bar，且用**下一根
  bar 的 open** 成交，而不是產生訊號當下那根 bar 的 close，避免最常見的
  lookahead bug。
- PnL accounting 會把 `previous close -> execution open` 歸給舊部位，將
  `execution open -> close` 歸給新部位，新部位不會誤吃到成交前已發生的跳空。

## 回歸測試

```bash
cd <repo 根目錄的上一層>
python -m unittest discover -s quant_platform/tests -v
```

測試包含成交/PnL 時間線、Registry version identity/run summary，以及 Sharpe null
bootstrap evidence。

這些防線可以從 V0A 的驗證結果側面確認有效：SMA crossover 在近似隨機遊走的
合成資料上跑出**負** Sharpe（見範例輸出），這是預期行為 —— 如果在純噪音資料上
跑出漂亮正報酬，就代表某處有 lookahead。

## 下一步（尚未做）

**V0B 剩餘部分：**
- Trade/Position/Fill 逐筆紀錄目前只留在記憶體（`BacktestResult.fills`），
  還沒落地到 registry 或獨立檔案，之後查特定 run 的逐筆交易還做不到。
- resample 的邏輯本身沒有被 fingerprint 進 dataset lineage
  （目前假設 resample 規則不變；一旦改了 aggregation 規則，舊 run 的
  可重現性會被默默破壞，值得之後補一個 code fingerprint）。

**V0C 尚未做的部分：**
- Parameter perturbation 目前是各參數獨立擾動（1D），還沒做聯合網格
  （例如 fast x slow 的 2D 熱力圖），看不出參數間的交互作用。
- Sample perturbation 的「移除最佳交易」目前只拿掉單一一根 bar；
  更完整的版本應該試著移除最好的 N 筆交易、或整段最佳月份，
  看策略的存活力。
- 還沒有 Strategy Failure Knowledge Base（文件裡提到的「記錄為什麼失敗」）—
  目前 sweep 結果都在 registry 裡，但沒有一個地方把「這個策略被 P3 判定
  不穩健，原因是 XXX」這種結論性知識沉澱下來，給未來的研究或 AI agent 參考。

**Phase 0-8 裡完全還沒碰的部分：** P2 更完整的統計檢定框架、P4 以後的內容
（execution/monitoring/risk 等），可以等你想推進的時候再排優先序。

想先補 V0B/V0C 的缺口，還是先接真實資料，都可以直接接著做，架構不需要重構。

## 執行環境

```
pip install pandas numpy   # V0 唯一硬需求
# 有網路時建議加裝：pip install pyarrow ccxt
```

```
cd <repo 根目錄的上一層>
python -m quant_platform.run_experiment --timeframe 1h --fast 20 --slow 100
```
