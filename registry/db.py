"""
Strategy Registry / Experiment Lineage 的 SQLite schema。

對應對話文件第9節的核心 entity，V0B 先實作其中最小必要子集：
Dataset、Strategy、StrategyVersion、Experiment、Run、Metric。
Trade/Position/Fill 的逐筆紀錄先只存在 parquet（見 repository.py），
不塞進 SQLite，避免小資料庫被灌爆。

之後要換 Postgres，只需要把這裡的 CREATE TABLE 換成對應方言，
repository.py 的介面（函式簽名）不需要變。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id   TEXT PRIMARY KEY,
    symbol       TEXT NOT NULL,
    timeframe    TEXT NOT NULL,
    path         TEXT NOT NULL,
    checksum     TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategies (
    strategy_id  TEXT PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    description  TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS strategy_versions (
    version_id       TEXT PRIMARY KEY,
    strategy_id      TEXT NOT NULL REFERENCES strategies(strategy_id),
    version_label    TEXT NOT NULL,
    params_json      TEXT NOT NULL,
    code_fingerprint TEXT NOT NULL,
    created_at       TEXT NOT NULL,
    UNIQUE(strategy_id, version_label, code_fingerprint)
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id             TEXT PRIMARY KEY,
    experiment_id      TEXT NOT NULL REFERENCES experiments(experiment_id),
    strategy_version_id TEXT NOT NULL REFERENCES strategy_versions(version_id),
    dataset_id         TEXT NOT NULL REFERENCES datasets(dataset_id),
    timeframe          TEXT NOT NULL,
    cost_model_json    TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'running',
    started_at         TEXT NOT NULL,
    finished_at        TEXT
);

CREATE TABLE IF NOT EXISTS metrics (
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    metric_name  TEXT NOT NULL,
    metric_json  TEXT NOT NULL,
    PRIMARY KEY (run_id, metric_name)
);

-- V0C: Robustness Engine 用來追蹤「一次 sweep 底下跑了哪些 trial」，
-- 這是 multiple-testing / FDR 追蹤的基礎：要先知道一個 experiment 裡
-- 到底跑了幾次 trial，才能算出正確的 false discovery rate。
CREATE TABLE IF NOT EXISTS sweeps (
    sweep_id      TEXT PRIMARY KEY,
    experiment_id TEXT NOT NULL REFERENCES experiments(experiment_id),
    kind          TEXT NOT NULL,  -- 'param_perturbation' | 'cost_stress' | 'execution_delay'
    base_run_id   TEXT REFERENCES runs(run_id),
    description   TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sweep_runs (
    sweep_id            TEXT NOT NULL REFERENCES sweeps(sweep_id),
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    perturbation_label  TEXT NOT NULL,  -- e.g. 'fast=-10%', 'commission_x2', 'delay+1'
    PRIMARY KEY (sweep_id, run_id)
);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Path) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
