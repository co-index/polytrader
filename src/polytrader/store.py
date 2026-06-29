"""SQLite persistence and the engine<->dashboard control channel.

Both the engine and the dashboard talk only through this store; they never share
in-memory state (Constitution V). The store is also the audit log (Constitution VI):
all orders, fills, positions, and events land here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class Order:
    ts: str
    market_id: str
    token_id: str
    side: str
    size: float
    price: float
    mode: str
    status: str
    reason: str | None = None
    client_order_id: str | None = None
    id: int | None = None


@dataclass
class Fill:
    order_id: int
    ts: str
    size: float
    price: float
    mode: str


@dataclass
class Position:
    market_id: str
    token_id: str
    size: float
    avg_cost: float
    ts: str


@dataclass
class Event:
    ts: str
    level: str
    category: str
    message: str


@dataclass
class PnL:
    realized_usd: float
    unrealized_usd: float = 0.0


@dataclass
class EngineState:
    run: bool
    mode: str
    kill: bool
    last_tick_ts: str | None = None
    stopped_reason: str | None = None


class Store:
    def __init__(self, db_path: str):
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False so the engine and a dashboard process opening the same
        # file don't trip sqlite's thread guard; each call uses a short-lived cursor.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        c = self._conn
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, market_id TEXT, token_id TEXT, side TEXT,
                size REAL, price REAL, mode TEXT, status TEXT,
                reason TEXT, client_order_id TEXT
            );
            CREATE TABLE IF NOT EXISTS fills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER, ts TEXT, size REAL, price REAL, mode TEXT
            );
            CREATE TABLE IF NOT EXISTS positions (
                market_id TEXT, token_id TEXT, size REAL, avg_cost REAL, ts TEXT,
                PRIMARY KEY (market_id, token_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT, level TEXT, category TEXT, message TEXT
            );
            CREATE TABLE IF NOT EXISTS pnl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                day TEXT, realized_usd REAL
            );
            CREATE TABLE IF NOT EXISTS engine_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                run INTEGER, mode TEXT, kill INTEGER,
                last_tick_ts TEXT, stopped_reason TEXT
            );
            """
        )
        # Single control row; a fresh start is stopped + dry_run (Constitution III).
        c.execute(
            "INSERT OR IGNORE INTO engine_state (id, run, mode, kill) VALUES (1, 0, 'dry_run', 0)"
        )
        c.commit()

    # ---- writes ----
    def record_order(self, order: Order) -> int:
        cur = self._conn.execute(
            "INSERT INTO orders (ts, market_id, token_id, side, size, price, mode, status,"
            " reason, client_order_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                order.ts, order.market_id, order.token_id, order.side, order.size,
                order.price, order.mode, order.status, order.reason, order.client_order_id,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def record_fill(self, fill: Fill) -> None:
        self._conn.execute(
            "INSERT INTO fills (order_id, ts, size, price, mode) VALUES (?,?,?,?,?)",
            (fill.order_id, fill.ts, fill.size, fill.price, fill.mode),
        )
        self._conn.commit()

    def upsert_position(self, position: Position) -> None:
        self._conn.execute(
            "INSERT INTO positions (market_id, token_id, size, avg_cost, ts) VALUES (?,?,?,?,?)"
            " ON CONFLICT(market_id, token_id) DO UPDATE SET"
            " size=excluded.size, avg_cost=excluded.avg_cost, ts=excluded.ts",
            (position.market_id, position.token_id, position.size, position.avg_cost, position.ts),
        )
        self._conn.commit()

    def log_event(self, level: str, category: str, message: str, ts: str = "") -> None:
        self._conn.execute(
            "INSERT INTO events (ts, level, category, message) VALUES (?,?,?,?)",
            (ts, level, category, message),
        )
        self._conn.commit()

    def record_realized_pnl(self, day: str, amount_usd: float) -> None:
        self._conn.execute(
            "INSERT INTO pnl (day, realized_usd) VALUES (?, ?)", (day, amount_usd)
        )
        self._conn.commit()

    # ---- control / state ----
    def get_engine_state(self) -> EngineState:
        row = self._conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()
        return EngineState(
            run=bool(row["run"]),
            mode=row["mode"],
            kill=bool(row["kill"]),
            last_tick_ts=row["last_tick_ts"],
            stopped_reason=row["stopped_reason"],
        )

    def set_command(self, *, run: bool | None = None, mode: str | None = None,
                    kill: bool | None = None) -> None:
        sets, params = [], []
        if run is not None:
            sets.append("run = ?")
            params.append(1 if run else 0)
        if mode is not None:
            sets.append("mode = ?")
            params.append(mode)
        if kill is not None:
            sets.append("kill = ?")
            params.append(1 if kill else 0)
        if not sets:
            return
        self._conn.execute(f"UPDATE engine_state SET {', '.join(sets)} WHERE id = 1", params)
        self._conn.commit()

    def set_status(self, *, last_tick_ts: str | None = None,
                   stopped_reason: str | None = None) -> None:
        self._conn.execute(
            "UPDATE engine_state SET last_tick_ts = COALESCE(?, last_tick_ts),"
            " stopped_reason = ? WHERE id = 1",
            (last_tick_ts, stopped_reason),
        )
        self._conn.commit()

    # ---- reads ----
    def recent_orders(self, n: int) -> list[Order]:
        rows = self._conn.execute(
            "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [
            Order(
                id=r["id"], ts=r["ts"], market_id=r["market_id"], token_id=r["token_id"],
                side=r["side"], size=r["size"], price=r["price"], mode=r["mode"],
                status=r["status"], reason=r["reason"], client_order_id=r["client_order_id"],
            )
            for r in rows
        ]

    def positions(self) -> list[Position]:
        rows = self._conn.execute("SELECT * FROM positions").fetchall()
        return [
            Position(
                market_id=r["market_id"], token_id=r["token_id"], size=r["size"],
                avg_cost=r["avg_cost"], ts=r["ts"],
            )
            for r in rows
        ]

    def pnl_today(self) -> PnL:
        today = date.today().isoformat()
        row = self._conn.execute(
            "SELECT COALESCE(SUM(realized_usd), 0) AS r FROM pnl WHERE day = ?", (today,)
        ).fetchone()
        return PnL(realized_usd=float(row["r"]))

    def recent_events(self, n: int) -> list[Event]:
        rows = self._conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        return [
            Event(ts=r["ts"], level=r["level"], category=r["category"], message=r["message"])
            for r in rows
        ]
