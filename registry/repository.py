"""
Registry Repository。

負責把「一次 run 的完整身分」(用了哪份 dataset、哪個 strategy version、
哪組 cost model)寫進 SQLite，讓事後可以回答：
「這個 run_id 當初到底是用什麼資料、什麼參數、跑出來的？」

刻意把這層跟 db.py 的 schema 分開，之後要換 Postgres 時，
只有這個檔案裡的 SQL 需要改，呼叫端（run_experiment.py）完全不用動。
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from quant_platform.data.loader import DatasetRef
from quant_platform.strategy.base import Strategy


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def code_fingerprint(obj) -> str:
    """用策略 class 原始碼和 canonical params 算 implementation hash。

    Registry 舊 schema 的 unique key 沒有 params_json，因此 fingerprint 必須同時
    包含參數，才不會把「同一份 class，不同參數」錯誤視為同一版本。
    """
    try:
        source = inspect.getsource(obj.__class__)
    except (OSError, TypeError):
        source = repr(obj)
    params_json = json.dumps(obj.meta.params, sort_keys=True, separators=(",", ":"), default=str)
    identity = f"{source}\n--params--\n{params_json}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def ensure_dataset(conn: sqlite3.Connection, ref: DatasetRef) -> str:
    row = conn.execute(
        "SELECT dataset_id FROM datasets WHERE symbol=? AND timeframe=? AND checksum=?",
        (ref.symbol, ref.timeframe, ref.checksum),
    ).fetchone()
    if row:
        return row[0]
    dataset_id = _new_id("ds")
    conn.execute(
        "INSERT INTO datasets (dataset_id, symbol, timeframe, path, checksum, created_at) VALUES (?,?,?,?,?,?)",
        (dataset_id, ref.symbol, ref.timeframe, str(ref.path), ref.checksum, _now()),
    )
    conn.commit()
    return dataset_id


def ensure_strategy(conn: sqlite3.Connection, name: str, description: str = "") -> str:
    row = conn.execute("SELECT strategy_id FROM strategies WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    strategy_id = _new_id("strat")
    conn.execute(
        "INSERT INTO strategies (strategy_id, name, description, created_at) VALUES (?,?,?,?)",
        (strategy_id, name, description, _now()),
    )
    conn.commit()
    return strategy_id


def ensure_strategy_version(conn: sqlite3.Connection, strategy_id: str, strategy: Strategy) -> str:
    fingerprint = code_fingerprint(strategy)
    params_json = json.dumps(strategy.meta.params, sort_keys=True)
    row = conn.execute(
        "SELECT version_id FROM strategy_versions "
        "WHERE strategy_id=? AND version_label=? AND code_fingerprint=? AND params_json=?",
        (strategy_id, strategy.meta.version_label, fingerprint, params_json),
    ).fetchone()
    if row:
        return row[0]
    version_id = _new_id("ver")
    conn.execute(
        "INSERT INTO strategy_versions (version_id, strategy_id, version_label, params_json, code_fingerprint, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (version_id, strategy_id, strategy.meta.version_label, params_json, fingerprint, _now()),
    )
    conn.commit()
    return version_id


def ensure_experiment(conn: sqlite3.Connection, name: str, description: str = "") -> str:
    row = conn.execute("SELECT experiment_id FROM experiments WHERE name=?", (name,)).fetchone()
    if row:
        return row[0]
    experiment_id = _new_id("exp")
    conn.execute(
        "INSERT INTO experiments (experiment_id, name, description, created_at) VALUES (?,?,?,?)",
        (experiment_id, name, description, _now()),
    )
    conn.commit()
    return experiment_id


def start_run(
    conn: sqlite3.Connection,
    experiment_id: str,
    strategy_version_id: str,
    dataset_id: str,
    timeframe: str,
    cost_model: dict,
) -> str:
    run_id = _new_id("run")
    conn.execute(
        "INSERT INTO runs (run_id, experiment_id, strategy_version_id, dataset_id, timeframe, cost_model_json, "
        "status, started_at) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, experiment_id, strategy_version_id, dataset_id, timeframe, json.dumps(cost_model), "running", _now()),
    )
    conn.commit()
    return run_id


def finish_run(conn: sqlite3.Connection, run_id: str, status: str = "completed") -> None:
    conn.execute(
        "UPDATE runs SET status=?, finished_at=? WHERE run_id=?",
        (status, _now(), run_id),
    )
    conn.commit()


def record_metrics(conn: sqlite3.Connection, run_id: str, metrics: dict) -> None:
    for name, value in metrics.items():
        conn.execute(
            "INSERT OR REPLACE INTO metrics (run_id, metric_name, metric_json) VALUES (?,?,?)",
            (run_id, name, json.dumps(value)),
        )
    conn.commit()


def create_sweep(
    conn: sqlite3.Connection,
    experiment_id: str,
    kind: str,
    base_run_id: str | None = None,
    description: str = "",
) -> str:
    sweep_id = _new_id("sweep")
    conn.execute(
        "INSERT INTO sweeps (sweep_id, experiment_id, kind, base_run_id, description, created_at) "
        "VALUES (?,?,?,?,?,?)",
        (sweep_id, experiment_id, kind, base_run_id, description, _now()),
    )
    conn.commit()
    return sweep_id


def link_sweep_run(conn: sqlite3.Connection, sweep_id: str, run_id: str, perturbation_label: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sweep_runs (sweep_id, run_id, perturbation_label) VALUES (?,?,?)",
        (sweep_id, run_id, perturbation_label),
    )
    conn.commit()


def get_sweep_runs(conn: sqlite3.Connection, sweep_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT sr.run_id, sr.perturbation_label, r.status FROM sweep_runs sr "
        "JOIN runs r ON r.run_id = sr.run_id WHERE sr.sweep_id=?",
        (sweep_id,),
    ).fetchall()
    out = []
    for run_id, label, status in rows:
        summary = get_run_summary(conn, run_id)
        summary["perturbation_label"] = label
        out.append(summary)
    return out


def count_all_trials(conn: sqlite3.Connection, experiment_id: str) -> int:
    """算出一個 experiment 底下總共跑了幾個 run（=幾次 trial），
    是計算 multiple-testing 修正時的分母來源。"""
    row = conn.execute(
        "SELECT COUNT(*) FROM runs WHERE experiment_id=? AND status='completed'",
        (experiment_id,),
    ).fetchone()
    return row[0] if row else 0


def get_run_summary(conn: sqlite3.Connection, run_id: str) -> dict:
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"找不到 run_id={run_id}")
    # PRAGMA table_info: (cid, name, type, notnull, default, pk)
    cols = [d[1] for d in conn.execute("PRAGMA table_info(runs)").fetchall()]
    run_dict = dict(zip(cols, run))

    metrics_rows = conn.execute("SELECT metric_name, metric_json FROM metrics WHERE run_id=?", (run_id,)).fetchall()
    run_dict["metrics"] = {name: json.loads(val) for name, val in metrics_rows}

    ver = conn.execute(
        "SELECT sv.version_label, sv.params_json, s.name FROM strategy_versions sv "
        "JOIN strategies s ON s.strategy_id = sv.strategy_id WHERE sv.version_id=?",
        (run_dict["strategy_version_id"],),
    ).fetchone()
    if ver:
        run_dict["strategy_name"], run_dict["strategy_params"] = ver[2], json.loads(ver[1])
        run_dict["strategy_version_label"] = ver[0]

    ds = conn.execute(
        "SELECT symbol, timeframe, checksum FROM datasets WHERE dataset_id=?",
        (run_dict["dataset_id"],),
    ).fetchone()
    if ds:
        run_dict["dataset_symbol"], run_dict["dataset_timeframe"], run_dict["dataset_checksum"] = ds

    return run_dict
