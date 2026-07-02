"""READ-ONLY continuous basket-arb scanner for Polymarket negRisk events.

A basket = one YES share of every outcome in a multi-outcome (negRisk) event; it
pays exactly $1 at resolution. Every cycle this rescans open negRisk events and
records structural mispricings:
  buy basket : edge = 1 - Σask, fillable sets = min ASK size across legs
  sell basket: edge = Σbid - 1, fillable sets = min BID size across legs
The paper sim (`BasketPaperSim`) executes each opportunity under honest constraints
and publishes a `basket_arb` row to the shared Paper Lab leaderboard.

This process is READ-ONLY against Polymarket: it fetches order books and event
metadata and never places, signs, or cancels an order. Safe to run anywhere.

Run:  python -m polytrader.basket_scanner   (or the `polytrader-scanner` script)
Config via env: POLYTRADER_BASKET_DB, POLYTRADER_PAPER_DB, POLYTRADER_SCAN_INTERVAL,
POLYTRADER_SCAN_EDGE_MIN, POLYTRADER_SCAN_MAX_EVENTS.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import UTC, datetime

GAMMA = "https://gamma-api.polymarket.com"
CLOB_HOST = "https://clob.polymarket.com"

DEFAULT_EDGE_MIN = 0.005
DEFAULT_INTERVAL_S = 300
DEFAULT_MAX_EVENTS = 250


def gamma_get(path: str) -> list | dict:
    """Fetch a Gamma API path. Gamma rejects urllib (403) but accepts curl, which is
    present on any server; keeping curl avoids a brittle User-Agent dance."""
    out = subprocess.run(
        ["curl", "-s", "--max-time", "30", f"{GAMMA}{path}"],
        capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)


def fetch_negrisk_events(get=gamma_get, max_events: int = DEFAULT_MAX_EVENTS) -> list[dict]:
    """Open multi-outcome (negRisk, >=3 legs) events, highest 24h volume first."""
    events: list[dict] = []
    offset = 0
    while len(events) < max_events:
        try:
            batch = get(
                f"/events?closed=false&active=true&limit=100&offset={offset}"
                "&order=volume24hr&ascending=false"
            )
        except Exception:  # noqa: BLE001 - a transient fetch error just ends paging
            break
        if not batch:
            break
        events.extend(batch)
        offset += 100
    multi = []
    for ev in events[:max_events]:
        if not ev.get("negRisk"):
            continue
        legs = []
        for m in ev.get("markets") or []:
            if m.get("closed") or not m.get("acceptingOrders", True):
                continue
            try:
                tok = json.loads(m.get("clobTokenIds") or "[]")
            except json.JSONDecodeError:
                tok = []
            if len(tok) == 2:
                legs.append(tok[0])  # YES token
        if len(legs) >= 3:
            multi.append({
                "title": (ev.get("title") or "")[:60],
                "slug": ev.get("slug"),
                "legs": legs,
                "vol24": float(ev.get("volume24hr") or 0),
            })
    return multi


def _book_levels(ob, key):
    """Normalize a v1 (attr objects) or v2 (dict) order book side to (price, size)."""
    side = ob.get(key) if isinstance(ob, dict) else getattr(ob, key, None)
    out = []
    for lvl in side or []:
        if isinstance(lvl, dict):
            out.append((float(lvl["price"]), float(lvl["size"])))
        else:
            out.append((float(lvl.price), float(lvl.size)))
    return out


def snapshot(clob, ev: dict) -> dict | None:
    """Σask/Σbid + per-side min depth for one event. None unless every leg is two-sided
    (a one-sided leg makes the basket un-priceable this instant)."""
    sum_ask = sum_bid = 0.0
    min_ask_sz = min_bid_sz = float("inf")
    for tok in ev["legs"]:
        try:
            ob = clob.get_order_book(tok)
        except Exception:  # noqa: BLE001 - skip the whole event on any book error
            return None
        bids, asks = _book_levels(ob, "bids"), _book_levels(ob, "asks")
        if not bids or not asks:
            return None
        best_ask, ask_sz = min(asks, key=lambda x: x[0])
        best_bid, bid_sz = max(bids, key=lambda x: x[0])
        sum_ask += best_ask
        sum_bid += best_bid
        min_ask_sz = min(min_ask_sz, ask_sz)
        min_bid_sz = min(min_bid_sz, bid_sz)
    return {
        "sum_ask": round(sum_ask, 4),
        "sum_bid": round(sum_bid, 4),
        "buy_depth": round(min_ask_sz, 1),
        "sell_depth": round(min_bid_sz, 1),
    }


def scan(clob, get=gamma_get, edge_min: float = DEFAULT_EDGE_MIN,
         max_events: int = DEFAULT_MAX_EVENTS) -> tuple[list[dict], list[dict]]:
    """One full pass. Returns (cycle_rows, opp_rows) — the full priced snapshot and
    the subset that clears the edge threshold, tagged with side/edge/depth/profit_cap."""
    ts = datetime.now(UTC).isoformat(timespec="seconds")
    cycle_rows, opp_rows = [], []
    for ev in fetch_negrisk_events(get, max_events):
        s = snapshot(clob, ev)
        if s is None:
            continue
        cycle_rows.append({"title": ev["title"], "slug": ev["slug"],
                           "n_legs": len(ev["legs"]), "vol24": ev["vol24"], **s})
        buy_edge = round(1.0 - s["sum_ask"], 4)
        sell_edge = round(s["sum_bid"] - 1.0, 4)
        if buy_edge >= edge_min or sell_edge >= edge_min:
            side = "buy" if buy_edge >= edge_min else "sell"
            edge = buy_edge if side == "buy" else sell_edge
            depth = s["buy_depth"] if side == "buy" else s["sell_depth"]
            opp_rows.append({"ts": ts, "side": side, "edge": edge, "depth": depth,
                             "profit_cap": round(edge * depth, 2),
                             "title": ev["title"], "slug": ev["slug"], **s})
    return cycle_rows, opp_rows


class BasketPaperSim:
    """Paper-executes detected basket opportunities under honest constraints.

    sell opp: mint N sets for $N on-chain, sell every leg at bid -> instant realized
              profit N*(Σbid-1).
    buy opp : buy every leg at ask, hold to resolution -> profit N*(1-Σask) locked as
              unrealized until settlement.
    Honesty: N is capped at the top-of-book depth MINUS what we've already virtually
    consumed on that book — re-taking the same resting orders each cycle would
    fabricate profit. The consumed tally resets when the opportunity disappears
    (gone => the real book changed, so future depth is genuinely new).
    """

    BANKROLL = 1000.0
    PER_TRADE_CAP = 500.0  # max $ committed per basket take (risk cap)

    def __init__(self):
        self.cash = self.BANKROLL
        self.locked = 0.0        # buy-basket cost held to resolution
        self.locked_edge = 0.0   # guaranteed profit on held baskets (unrealized)
        self.realized = 0.0
        self.fills = self.wins = self.trades = self.rejects = self.positions = 0
        self.taken: dict[tuple, float] = {}  # (slug, side) -> sets already consumed
        self.orders: list[dict] = []

    def on_cycle(self, ts: str, opps: list[dict]) -> None:
        seen = set()
        for o in opps:
            key = (o["slug"], o["side"])
            seen.add(key)
            depth_left = max(0.0, o["depth"] - self.taken.get(key, 0.0))
            unit_cost = 1.0 if o["side"] == "sell" else o["sum_ask"]
            sets = float(int(min(depth_left, self.PER_TRADE_CAP / unit_cost,
                                 self.cash / unit_cost)))
            if sets < 1.0:
                self.rejects += 1
                self.orders.append({
                    "ts": ts, "token_id": o["slug"], "side": o["side"].upper(),
                    "size": 0.0,
                    "price": o["sum_bid"] if o["side"] == "sell" else o["sum_ask"],
                    "status": "rejected", "pnl": 0.0,
                })
                continue
            self.taken[key] = self.taken.get(key, 0.0) + sets
            if o["side"] == "sell":
                pnl = round(sets * (o["sum_bid"] - 1.0), 2)
                self.cash += pnl  # mint -sets, sell +sets*Σbid, net = pnl
                self.realized += pnl
                self.wins += 1
                price = o["sum_bid"]
            else:
                cost = sets * o["sum_ask"]
                self.cash -= cost
                self.locked += cost
                pnl = round(sets * (1.0 - o["sum_ask"]), 2)
                self.locked_edge += pnl
                self.positions += 1
                price = o["sum_ask"]
            self.fills += 1
            self.trades += 1
            self.orders.append({
                "ts": ts, "token_id": o["slug"], "side": o["side"].upper(),
                "size": sets, "price": round(price, 4), "status": "filled", "pnl": pnl,
            })
        for key in [k for k in self.taken if k not in seen]:
            del self.taken[key]

    def leaderboard_row(self) -> dict:
        equity = self.cash + self.locked + self.locked_edge
        return {
            "name": "basket_arb", "equity": round(equity, 2),
            "total_pnl": round(self.realized + self.locked_edge, 2),
            "realized": round(self.realized, 2),
            "unrealized": round(self.locked_edge, 2),
            "fills": self.fills, "positions": self.positions, "wins": self.wins,
            "trades": self.trades, "rejects": self.rejects,
        }

    def recent_orders(self, limit: int = 400) -> list[dict]:
        return self.orders[-limit:]

    def state(self) -> dict:
        return {
            "cash": self.cash, "locked": self.locked, "locked_edge": self.locked_edge,
            "realized": self.realized, "fills": self.fills, "wins": self.wins,
            "trades": self.trades, "rejects": self.rejects, "positions": self.positions,
            "taken": [[slug, side, sets] for (slug, side), sets in self.taken.items()],
            "orders": self.orders[-400:],
        }

    def load_state(self, d: dict) -> None:
        self.cash = float(d.get("cash", self.BANKROLL))
        self.locked = float(d.get("locked", 0.0))
        self.locked_edge = float(d.get("locked_edge", 0.0))
        self.realized = float(d.get("realized", 0.0))
        self.fills = int(d.get("fills", 0))
        self.wins = int(d.get("wins", 0))
        self.trades = int(d.get("trades", 0))
        self.rejects = int(d.get("rejects", 0))
        self.positions = int(d.get("positions", 0))
        self.taken = {(row[0], row[1]): float(row[2]) for row in d.get("taken", [])}
        self.orders = list(d.get("orders", []))

    @classmethod
    def from_file(cls, path: str | None) -> "BasketPaperSim":
        sim = cls()
        if path and os.path.exists(path):
            try:
                with open(path) as f:
                    sim.load_state(json.load(f))
            except (json.JSONDecodeError, OSError, KeyError, IndexError, ValueError):
                pass  # corrupt state -> start fresh
        return sim

    def save_file(self, path: str) -> None:
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(self.state(), f)
        os.replace(tmp, path)  # atomic write


def run(clob, basket_store, paper_store, *, interval_s: int = DEFAULT_INTERVAL_S,
        edge_min: float = DEFAULT_EDGE_MIN, max_events: int = DEFAULT_MAX_EVENTS,
        sim: BasketPaperSim | None = None, state_file: str | None = None,
        once: bool = False) -> None:
    """Scan → persist snapshot + opps → paper-sim → publish leaderboard, forever."""
    sim = sim or BasketPaperSim()
    while True:
        t0 = time.time()
        cycle_rows, opp_rows = scan(clob, edge_min=edge_min, max_events=max_events)
        ts = opp_rows[0]["ts"] if opp_rows else datetime.now(UTC).isoformat(timespec="seconds")
        basket_store.write_cycle(ts, cycle_rows)
        if opp_rows:
            basket_store.append_opps(opp_rows)
        sim.on_cycle(ts, opp_rows)
        paper_store.write_leaderboard([sim.leaderboard_row()], ts=ts)
        paper_store.write_orders("basket_arb", sim.recent_orders())
        if state_file:
            sim.save_file(state_file)
        print(f"[{ts}] cycle: {len(cycle_rows)} priced, {len(opp_rows)} opps, "
              f"sim pnl={sim.realized + sim.locked_edge:.2f} ({time.time() - t0:.0f}s)",
              flush=True)
        if once:
            return
        time.sleep(max(0, interval_s - (time.time() - t0)))


def main() -> None:  # pragma: no cover - process entry point
    from py_clob_client.client import ClobClient

    from polytrader.basket import BasketStore
    from polytrader.paper.store import PaperStore

    basket_db = os.environ.get("POLYTRADER_BASKET_DB", "data/basket.db")
    paper_db = os.environ.get("POLYTRADER_PAPER_DB", "data/paper.db")
    state_file = os.environ.get("POLYTRADER_SCANNER_STATE", "data/basket_sim_state.json")
    interval = int(os.environ.get("POLYTRADER_SCAN_INTERVAL", DEFAULT_INTERVAL_S))
    edge_min = float(os.environ.get("POLYTRADER_SCAN_EDGE_MIN", DEFAULT_EDGE_MIN))
    max_events = int(os.environ.get("POLYTRADER_SCAN_MAX_EVENTS", DEFAULT_MAX_EVENTS))

    clob = ClobClient(CLOB_HOST, chain_id=137)
    basket_store = BasketStore(basket_db)
    basket_store.init_schema()
    paper_store = PaperStore(paper_db)
    paper_store.init_schema()
    paper_store.set_meta("data_source", "live")
    sim = BasketPaperSim.from_file(state_file)
    restored = sim.fills > 0
    print(f"basket-scanner starting: interval={interval}s edge_min={edge_min} "
          f"max_events={max_events} basket_db={basket_db} paper_db={paper_db} "
          f"state={'restored' if restored else 'fresh'} pnl={sim.realized + sim.locked_edge:.2f}",
          flush=True)
    run(clob, basket_store, paper_store, interval_s=interval, edge_min=edge_min,
        max_events=max_events, sim=sim, state_file=state_file)


if __name__ == "__main__":  # pragma: no cover
    main()
