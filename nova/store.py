from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import Decision


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS decisions (
  decision_id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, symbol TEXT NOT NULL,
  action TEXT NOT NULL, confidence REAL NOT NULL, reference_price REAL NOT NULL,
  notional_usd REAL NOT NULL, stop_price REAL, take_profit_price REAL,
  strategy_version TEXT NOT NULL, rationale TEXT NOT NULL, data_sha256 TEXT NOT NULL,
  status TEXT NOT NULL, payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cycles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, provider TEXT NOT NULL,
  bars INTEGER NOT NULL, latency_ms INTEGER NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        finally:
            db.close()

    def save_decision(self, decision: Decision) -> None:
        p = decision.to_dict()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*[p[k] for k in ("decision_id", "timestamp", "symbol", "action", "confidence", "reference_price", "notional_usd", "stop_price", "take_profit_price", "strategy_version", "rationale", "data_sha256", "status")], json.dumps(p, sort_keys=True)),
            )

    def save_cycle(self, started: str, provider: str, bars: int, latency_ms: int, outcome: str, detail: str) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO cycles(started_at,provider,bars,latency_ms,outcome,detail) VALUES(?,?,?,?,?,?)", (started, provider, bars, latency_ms, outcome, detail))

    def latest(self, limit: int = 20) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT payload_json FROM decisions ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def health(self) -> dict:
        with self.connect() as db:
            cycle = db.execute("SELECT * FROM cycles ORDER BY id DESC LIMIT 1").fetchone()
            count = db.execute("SELECT COUNT(*) FROM decisions").fetchone()[0]
        return {"ok": bool(cycle and cycle["outcome"] == "ok"), "latest_cycle": dict(cycle) if cycle else None, "decision_count": count}

