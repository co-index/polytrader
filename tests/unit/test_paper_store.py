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


def test_second_write_replaces_snapshot():
    s = PaperStore(":memory:")
    s.init_schema()
    s.write_leaderboard([_row("a", 1.0)], ts="t1")
    s.write_leaderboard([_row("a", 5.0), _row("d", 4.0)], ts="t2")
    lb = s.leaderboard()
    assert [r["name"] for r in lb] == ["a", "d"]
    assert lb[0]["total_pnl"] == 5.0  # replaced, not appended
