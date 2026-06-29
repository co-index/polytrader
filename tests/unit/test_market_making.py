"""MarketMakingStrategy: symmetric resting quotes around the midpoint."""

from polytrader.strategy.base import MarketState, Strategy, StrategyContext
from polytrader.strategy.market_making import MarketMakingStrategy


def _mkt(mid: float) -> MarketState:
    return MarketState("m1", "t1", "Q?", best_bid=mid - 0.01, best_ask=mid + 0.01,
                       midpoint=mid, timestamp="2026-06-29T00:00:00")


def _ctx() -> StrategyContext:
    return StrategyContext(positions=[], remaining_exposure_usd=100.0)


def test_quotes_both_sides_around_mid():
    strat = MarketMakingStrategy(size=1.0, half_spread=0.02)
    assert isinstance(strat, Strategy)
    intents = strat.on_tick([_mkt(0.50)], _ctx())
    by_side = {i.side: i for i in intents}
    assert by_side["BUY"].price == 0.48
    assert by_side["SELL"].price == 0.52
    assert all(i.size == 1.0 for i in intents)


def test_skips_market_without_a_midpoint():
    strat = MarketMakingStrategy()
    assert strat.on_tick([_mkt(0.0)], _ctx()) == []


def test_clamps_quotes_into_unit_interval():
    strat = MarketMakingStrategy(half_spread=0.02)
    # mid 0.99 -> ask 1.01 is invalid, drop it; keep the BUY at 0.97.
    high = strat.on_tick([_mkt(0.99)], _ctx())
    assert [i.side for i in high] == ["BUY"]
    # mid 0.01 -> bid -0.01 invalid, drop it; keep the SELL at 0.03.
    low = strat.on_tick([_mkt(0.01)], _ctx())
    assert [i.side for i in low] == ["SELL"]
