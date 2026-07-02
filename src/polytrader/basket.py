"""BasketStore — SQLite store for the read-only negRisk basket-arb scanner.

A basket = one YES share of every outcome in a multi-outcome (negRisk) event; it
pays exactly $1 at resolution, so Σask < 1 (buy) or Σbid > 1 (mint & sell) is a
structural mispricing. An external read-only scanner writes one full snapshot per
cycle (replacing the last) plus an append-only opportunity log; the dashboard reads
both cross-process, so data stays visible when the scanner is stopped.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_LATEST_COLS = ("title", "slug", "n_legs", "sum_ask", "sum_bid",
                "buy_depth", "sell_depth", "vol24")

_OPP_COLS = ("ts", "side", "edge", "depth", "profit_cap",
             "title", "slug", "sum_ask", "sum_bid")


class BasketStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS basket_latest (
                ts TEXT, title TEXT, slug TEXT, n_legs INTEGER, sum_ask REAL,
                sum_bid REAL, buy_depth REAL, sell_depth REAL, vol24 REAL
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS basket_opps (
                ts TEXT, side TEXT, edge REAL, depth REAL, profit_cap REAL,
                title TEXT, slug TEXT, sum_ask REAL, sum_bid REAL
            )
            """
        )
        self._conn.commit()

    def write_cycle(self, ts: str, rows: list[dict]) -> None:
        """Replace the full-scan snapshot; ts doubles as the scanner heartbeat."""
        c = self._conn
        c.execute("DELETE FROM basket_latest")
        c.executemany(
            "INSERT INTO basket_latest (ts, title, slug, n_legs, sum_ask, sum_bid,"
            " buy_depth, sell_depth, vol24) VALUES (?,?,?,?,?,?,?,?,?)",
            [(ts, *(r[k] for k in _LATEST_COLS)) for r in rows],
        )
        c.commit()

    def latest(self) -> list[dict]:
        """Latest full scan, cheapest basket (lowest Σask) first."""
        rows = self._conn.execute(
            "SELECT * FROM basket_latest ORDER BY sum_ask ASC"
        ).fetchall()
        return [{k: r[k] for k in _LATEST_COLS} for r in rows]

    def last_cycle(self) -> str | None:
        row = self._conn.execute("SELECT MAX(ts) AS ts FROM basket_latest").fetchone()
        return row["ts"] if row and row["ts"] else None

    def append_opps(self, rows: list[dict]) -> None:
        self._conn.executemany(
            "INSERT INTO basket_opps (ts, side, edge, depth, profit_cap, title,"
            " slug, sum_ask, sum_bid) VALUES (?,?,?,?,?,?,?,?,?)",
            [tuple(r[k] for k in _OPP_COLS) for r in rows],
        )
        self._conn.commit()

    def opps(self, limit: int = 200) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM basket_opps ORDER BY rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        return [{k: r[k] for k in _OPP_COLS} for r in rows]
