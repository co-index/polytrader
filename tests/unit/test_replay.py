"""ReplayClient: a synthetic (NOT real) market-data source for demoing the paper lab.

Generates moving prices so the strategies actually trade. Clearly synthetic — used only
to demonstrate trade/P&L mechanics when no live feed is available.
"""

from polytrader.paper.replay import ReplayClient
from polytrader.strategy.base import MarketState

SPECS = [("simA", "a", "Synthetic A", 0.50), ("simB", "b", "Synthetic B", 0.30)]


def test_get_markets_returns_marketstate_for_each_spec():
    c = ReplayClient(SPECS, seed=1)
    ms = c.get_markets()
    assert len(ms) == 2
    assert all(isinstance(m, MarketState) for m in ms)
    assert {m.token_id for m in ms} == {"a", "b"}


def test_prices_move_between_calls():
    c = ReplayClient(SPECS, seed=1, vol=0.02)
    first = {m.token_id: m.midpoint for m in c.get_markets()}
    moved = False
    for _ in range(5):
        nxt = {m.token_id: m.midpoint for m in c.get_markets()}
        if any(nxt[t] != first[t] for t in first):
            moved = True
            break
    assert moved


def test_book_is_valid_and_in_unit_interval():
    c = ReplayClient(SPECS, seed=2, spread=0.01, vol=0.05)
    for _ in range(50):
        for m in c.get_markets():
            assert 0 < m.best_bid < m.best_ask < 1
            assert abs((m.best_ask - m.best_bid) - 0.01) < 1e-6


def test_deterministic_for_a_given_seed():
    a = [m.midpoint for m in ReplayClient(SPECS, seed=7, vol=0.02).get_markets()]
    b = [m.midpoint for m in ReplayClient(SPECS, seed=7, vol=0.02).get_markets()]
    assert a == b
