"""PaperStore: cross-process snapshot of the latest leaderboard."""

from polytrader.paper.store import PaperStore


def _row(name, total_pnl):
    return {"name": name, "equity": 1000 + total_pnl, "total_pnl": total_pnl,
            "realized": 0.0, "unrealized": total_pnl, "fills": 1, "positions": 1,
            "wins": 0, "trades": 0, "rejects": 0}


def test_write_then_read_sorted_by_total_pnl_desc():
    s = PaperStore(":memory:")
    s.init_schema()
    s.write_leaderboard([_row("a", 1.0), _row("b", 3.0), _row("c", 2.0)], ts="t1")
    names = [r["name"] for r in s.leaderboard()]
    assert names == ["b", "c", "a"]


def test_last_update_returns_snapshot_ts_or_none():
    s = PaperStore(":memory:")
    s.init_schema()
    assert s.last_update() is None
    s.write_leaderboard([_row("a", 1.0)], ts="2026-06-30T12:00:00")
    assert s.last_update() == "2026-06-30T12:00:00"


def test_second_write_replaces_snapshot():
    s = PaperStore(":memory:")
    s.init_schema()
    s.write_leaderboard([_row("a", 1.0)], ts="t1")
    s.write_leaderboard([_row("a", 5.0), _row("d", 4.0)], ts="t2")
    lb = s.leaderboard()
    assert [r["name"] for r in lb] == ["a", "d"]
    assert lb[0]["total_pnl"] == 5.0  # replaced, not appended


def _order(ts, token_id="t1", side="BUY", size=5.0, price=0.4):
    return {"ts": ts, "token_id": token_id, "side": side, "size": size,
            "price": price, "status": "filled"}


def test_write_and_read_orders_per_strategy():
    s = PaperStore(":memory:")
    s.init_schema()
    s.write_orders("momentum", [_order("t1"), _order("t2", side="SELL")])
    s.write_orders("example", [_order("t3")])
    rows = s.orders("momentum")
    assert len(rows) == 2
    assert {r["side"] for r in rows} == {"BUY", "SELL"}
    assert s.orders("example")[0]["token_id"] == "t1"


def test_write_orders_replaces_that_strategys_rows_only():
    s = PaperStore(":memory:")
    s.init_schema()
    s.write_orders("momentum", [_order("t1"), _order("t2")])
    s.write_orders("example", [_order("t1")])
    s.write_orders("momentum", [_order("t9")])  # replace momentum only
    assert len(s.orders("momentum")) == 1
    assert s.orders("momentum")[0]["ts"] == "t9"
    assert len(s.orders("example")) == 1  # untouched
