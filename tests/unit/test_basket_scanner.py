"""BasketPaperSim honesty + scan() shaping tests."""

import json
import os
import tempfile

from polytrader.basket_scanner import BasketPaperSim, scan


def _sell(slug="por-cro", edge=0.0075, depth=100.0):
    return {"ts": "t", "side": "sell", "edge": edge, "depth": depth,
            "profit_cap": round(edge * depth, 2), "title": slug, "slug": slug,
            "sum_ask": 1.02, "sum_bid": round(1.0 + edge, 4)}


def _buy(slug="temp-nyc", edge=0.02, depth=50.0):
    return {"ts": "t", "side": "buy", "edge": edge, "depth": depth,
            "profit_cap": round(edge * depth, 2), "title": slug, "slug": slug,
            "sum_ask": round(1.0 - edge, 4), "sum_bid": 0.9}


def test_sell_opp_realizes_profit_capped_by_depth_and_per_trade_cap():
    sim = BasketPaperSim()
    sim.on_cycle("t1", [_sell(depth=100.0)])  # 100 sets * 0.0075 = 0.75
    assert sim.fills == 1 and sim.wins == 1
    assert round(sim.realized, 2) == 0.75
    assert sim.leaderboard_row()["realized"] == 0.75
    # PER_TRADE_CAP=500 caps sets even when depth is huge (sell unit_cost=$1).
    sim2 = BasketPaperSim()
    sim2.on_cycle("t1", [_sell(depth=100000.0, edge=0.01)])
    assert sim2.recent_orders()[-1]["size"] == 500.0  # not 100000


def test_does_not_retake_the_same_resting_book_twice():
    """The core honesty guard: a still-present opportunity at the same depth must not
    be filled again next cycle — that would fabricate profit off orders already taken."""
    sim = BasketPaperSim()
    sim.on_cycle("t1", [_sell(depth=100.0)])
    first = sim.realized
    sim.on_cycle("t2", [_sell(depth=100.0)])  # same book, nothing new
    assert sim.realized == first          # no new profit
    assert sim.fills == 1                  # no new fill
    assert sim.rejects == 1               # logged as a reject (depth exhausted)


def test_consumed_tally_resets_when_opportunity_disappears():
    sim = BasketPaperSim()
    sim.on_cycle("t1", [_sell(depth=100.0)])
    sim.on_cycle("t2", [])                 # opp gone -> real book changed
    sim.on_cycle("t3", [_sell(depth=100.0)])  # reappears -> fresh depth, takeable
    assert sim.fills == 2
    assert round(sim.realized, 2) == 1.50


def test_buy_opp_locks_profit_as_unrealized():
    sim = BasketPaperSim()
    sim.on_cycle("t1", [_buy(edge=0.02, depth=50.0)])  # 50 sets * 0.02 = 1.00 locked
    row = sim.leaderboard_row()
    assert sim.positions == 1
    assert row["realized"] == 0.0
    assert row["unrealized"] == 1.0
    assert row["total_pnl"] == 1.0


def _raw_event(title, yes_tokens):
    """A raw Gamma event with negRisk + one 2-token market per leg."""
    return {
        "title": title, "slug": title, "negRisk": True, "volume24hr": 5.0,
        "markets": [
            {"clobTokenIds": f'["{y}", "{y}-no"]', "closed": False,
             "acceptingOrders": True}
            for y in yes_tokens
        ],
    }


def test_scan_splits_priced_rows_and_threshold_opps():
    """scan() prices every two-sided event but only flags those beating edge_min."""
    events = [
        _raw_event("arb", ["a1", "a2", "a3"]),
        _raw_event("tight", ["b1", "b2", "b3"]),
    ]

    class FakeClob:
        # arb: Σbid=1.02 (sell edge 0.02), Σask=1.05 (no buy edge) -> sell-only.
        # tight: Σbid=0.99, Σask=1.02 -> neither side clears the threshold.
        books = {
            "a1": (0.34, 0.35), "a2": (0.34, 0.35), "a3": (0.34, 0.35),
            "b1": (0.33, 0.34), "b2": (0.33, 0.34), "b3": (0.33, 0.34),
        }

        def get_order_book(self, tok):
            bid, ask = self.books[tok]
            return {"bids": [{"price": bid, "size": 200}],
                    "asks": [{"price": ask, "size": 200}]}

    def fake_get(path):  # first page returns events, later pages empty -> paging stops
        return events if "offset=0" in path else []

    cycle, opps = scan(FakeClob(), get=fake_get, edge_min=0.005)
    assert len(cycle) == 2                 # both priced
    assert [o["slug"] for o in opps] == ["arb"]  # only arb beats the threshold
    assert opps[0]["side"] == "sell"


# --- state persistence tests ---

def test_state_roundtrip_preserves_all_fields():
    """state() + load_state() must restore every field exactly."""
    sim = BasketPaperSim()
    sim.on_cycle("t1", [_sell(depth=200.0)])   # 200 sets * 0.0075 = 1.50 realized
    sim.on_cycle("t2", [_buy(depth=50.0)])     # 50 sets locked
    snapshot = sim.state()
    sim2 = BasketPaperSim()
    sim2.load_state(snapshot)
    assert sim2.cash == sim.cash
    assert sim2.realized == sim.realized
    assert sim2.locked == sim.locked
    assert sim2.locked_edge == sim.locked_edge
    assert sim2.fills == sim.fills
    assert sim2.wins == sim.wins
    assert sim2.trades == sim.trades
    assert sim2.rejects == sim.rejects
    assert sim2.positions == sim.positions
    assert sim2.taken == sim.taken
    assert len(sim2.orders) == len(sim.orders)


def test_from_file_starts_fresh_on_missing_path():
    sim = BasketPaperSim.from_file(None)
    assert sim.cash == BasketPaperSim.BANKROLL
    assert sim.fills == 0


def test_save_and_load_file_roundtrip():
    sim = BasketPaperSim()
    sim.on_cycle("t1", [_sell(depth=100.0)])  # realized=0.75
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    try:
        sim.save_file(path)
        assert os.path.exists(path)
        data = json.loads(open(path).read())
        assert data["realized"] == sim.realized
        sim2 = BasketPaperSim.from_file(path)
        assert sim2.realized == sim.realized
        assert sim2.fills == sim.fills
        assert sim2.cash == sim.cash
    finally:
        os.unlink(path)


def test_from_file_is_resilient_to_corrupt_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{{not json}}")
        path = f.name
    try:
        sim = BasketPaperSim.from_file(path)  # must not raise
        assert sim.cash == BasketPaperSim.BANKROLL  # falls back to fresh
    finally:
        os.unlink(path)
