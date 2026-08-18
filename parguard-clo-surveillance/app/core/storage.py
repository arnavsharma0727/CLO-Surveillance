"""SQLite persistence for local ParGuard scenario runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("parguard_scenarios.sqlite3")


def _connect(path: str | Path | None = None):
    con = sqlite3.connect(path or DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript('''
    CREATE TABLE IF NOT EXISTS scenario_runs (run_id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id TEXT NOT NULL, scenario_name TEXT NOT NULL, timestamp TEXT NOT NULL, deal_configuration TEXT NOT NULL, assumptions TEXT NOT NULL, summary_results TEXT NOT NULL, waterfall_output TEXT, coverage_test_results TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS loan_level_changes (id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL REFERENCES scenario_runs(run_id) ON DELETE CASCADE, loan_id TEXT NOT NULL, obligor_name TEXT, industry TEXT, changes TEXT NOT NULL);
    ''')
    return con


def save_scenario_run(run: dict[str, Any], deal_configuration: dict[str, Any] | None = None, waterfall_output: dict[str, Any] | None = None, db_path: str | Path | None = None) -> int:
    with _connect(db_path) as con:
        cur = con.execute("""INSERT INTO scenario_runs (scenario_id, scenario_name, timestamp, deal_configuration, assumptions, summary_results, waterfall_output, coverage_test_results) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", (run["scenario_id"], run["scenario_name"], run["timestamp"], json.dumps(deal_configuration or {}, default=str), json.dumps(run.get("assumptions_limitations", []), default=str), json.dumps({k: run[k] for k in ("change_in_adjusted_collateral", "change_in_portfolio_interest_income", "change_in_oc_ic_ratios", "tests_changed_from_pass")}, default=str), json.dumps(waterfall_output or {}, default=str), json.dumps(run.get("scenario_kpi_snapshot", {}), default=str)))
        run_id = int(cur.lastrowid)
        for ch in run.get("impacted_loans", []):
            con.execute("INSERT INTO loan_level_changes (run_id, loan_id, obligor_name, industry, changes) VALUES (?, ?, ?, ?, ?)", (run_id, ch["loan_id"], ch.get("obligor_name"), ch.get("industry"), json.dumps(ch.get("changes", {}), default=str)))
        return run_id


def list_scenario_runs(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with _connect(db_path) as con:
        return [dict(r) for r in con.execute("SELECT run_id, scenario_id, scenario_name, timestamp FROM scenario_runs ORDER BY run_id DESC")]


def get_scenario_run(run_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with _connect(db_path) as con:
        row = con.execute("SELECT * FROM scenario_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None: return None
        data = dict(row)
        for key in ["deal_configuration", "assumptions", "summary_results", "waterfall_output", "coverage_test_results"]: data[key] = json.loads(data[key])
        data["loan_level_changes"] = [dict(r) | {"changes": json.loads(r["changes"])} for r in con.execute("SELECT loan_id, obligor_name, industry, changes FROM loan_level_changes WHERE run_id=?", (run_id,))]
        return data


def compare_scenario_runs(run_a_id: int, run_b_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    a, b = get_scenario_run(run_a_id, db_path), get_scenario_run(run_b_id, db_path)
    if a is None or b is None: raise ValueError("both scenario runs must exist")
    return {"run_a": a, "run_b": b, "summary_delta": {k: b["summary_results"].get(k) for k in b["summary_results"]}}


def delete_scenario_run(run_id: int, db_path: str | Path | None = None) -> bool:
    with _connect(db_path) as con:
        cur = con.execute("DELETE FROM scenario_runs WHERE run_id=?", (run_id,))
        return cur.rowcount > 0
