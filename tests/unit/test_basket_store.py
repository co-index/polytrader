"""BasketStore — SQLite snapshot store for the read-only negRisk basket scanner.

The scanner (an external read-only process) writes one full-scan snapshot per cycle
plus an append-only opportunity log; the dashboard reads both cross-process.
"""

from polytrader.basket import BasketStore


def make_row(slug="ev-1", sum_ask=1.02, sum_bid=0.98):
    return {
        "title": "Test event?", "slug": slug, "n_legs": 3,
        "sum_ask": sum_ask, "sum_bid": sum_bid,
        "buy_depth": 12.0, "sell_depth": 7.5, "vol24": 1234.0,
    }


def make_opp(ts="2026-07-02T06:00:00+00:00", side="buy", edge=0.022):
    return {
        "ts": ts, "side": side, "edge": edge, "depth": 5.0,
        "profit_cap": round(edge * 5.0, 2), "title": "Test event?",
        "slug": "ev-1", "sum_ask": 1 - edge if side == "buy" else 1.0,
        "sum_bid": 1 + edge if side == "sell" else 0.9,
    }


def test_write_cycle_replaces_latest_snapshot_and_sets_heartbeat():
    s = BasketStore(":memory:")
    s.init_schema()
    assert s.last_cycle() is None
    assert s.latest() == []

    s.write_cycle("2026-07-02T06:00:00+00:00", [make_row("a"), make_row("b", 0.99)])
    s.write_cycle("2026-07-02T06:05:00+00:00", [make_row("c", 1.05)])

    rows = s.latest()
    assert [r["slug"] for r in rows] == ["c"]  # replaced, not appended
    assert s.last_cycle() == "2026-07-02T06:05:00+00:00"


def test_latest_is_sorted_by_sum_ask_cheapest_basket_first():
    s = BasketStore(":memory:")
    s.init_schema()
    s.write_cycle("t", [make_row("hi", 1.20), make_row("lo", 0.98), make_row("mid", 1.01)])
    assert [r["slug"] for r in s.latest()] == ["lo", "mid", "hi"]


def test_opps_append_and_read_newest_first():
    s = BasketStore(":memory:")
    s.init_schema()
    s.append_opps([make_opp("2026-07-02T06:00:00+00:00")])
    s.append_opps([make_opp("2026-07-02T06:05:00+00:00", side="sell", edge=0.008)])

    opps = s.opps()
    assert [o["ts"] for o in opps] == [
        "2026-07-02T06:05:00+00:00", "2026-07-02T06:00:00+00:00",
    ]
    assert opps[0]["side"] == "sell"
    assert opps[1]["edge"] == 0.022

    assert len(s.opps(limit=1)) == 1
