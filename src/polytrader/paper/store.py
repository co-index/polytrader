"""PaperStore — a paper-only SQLite holding the latest leaderboard snapshot.

Separate from the audited live Store. The runner writes one row per strategy each tick
(replacing the prior snapshot); the dashboard reads the latest snapshot cross-process, so
the leaderboard stays visible even when the runner is stopped.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_COLS = ("name", "equity", "total_pnl", "realized", "unrealized",
         "fills", "positions", "wins", "trades", "rejects")

_ORDER_COLS = ("ts", "token_id", "side", "size", "price", "status")


class PaperStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_leaderboard (
                ts TEXT, name TEXT, equity REAL, total_pnl REAL, realized REAL,
                unrealized REAL, fills INTEGER, positions INTEGER, wins INTEGER,
                trades INTEGER, rejects INTEGER
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_orders (
                strategy TEXT, ts TEXT, token_id TEXT, side TEXT,
                size REAL, price REAL, status TEXT
            )
            """
        )
        self._conn.commit()

    def write_leaderboard(self, rows: list[dict], ts: str) -> None:
        c = self._conn
        c.execute("DELETE FROM paper_leaderboard")  # keep only the latest snapshot
        c.executemany(
            "INSERT INTO paper_leaderboard (ts, name, equity, total_pnl, realized,"
            " unrealized, fills, positions, wins, trades, rejects)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(ts, *(r[k] for k in _COLS)) for r in rows],
        )
        c.commit()

    def leaderboard(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM paper_leaderboard ORDER BY total_pnl DESC"
        ).fetchall()
        return [{k: r[k] for k in _COLS} for r in rows]

    def last_update(self) -> str | None:
        """Timestamp of the latest leaderboard snapshot (a runner heartbeat), or None."""
        row = self._conn.execute("SELECT MAX(ts) AS ts FROM paper_leaderboard").fetchone()
        return row["ts"] if row and row["ts"] else None

    def write_orders(self, strategy: str, rows: list[dict]) -> None:
        """Replace the stored order log for one strategy (leaves others intact)."""
        c = self._conn
        c.execute("DELETE FROM paper_orders WHERE strategy = ?", (strategy,))
        c.executemany(
            "INSERT INTO paper_orders (strategy, ts, token_id, side, size, price, status)"
            " VALUES (?,?,?,?,?,?,?)",
            [(strategy, *(r[k] for k in _ORDER_COLS)) for r in rows],
        )
        c.commit()

    def orders(self, strategy: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM paper_orders WHERE strategy = ? ORDER BY rowid", (strategy,)
        ).fetchall()
        return [{k: r[k] for k in _ORDER_COLS} for r in rows]
