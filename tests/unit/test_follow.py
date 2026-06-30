"""FollowStrategy (跟单): take the market in the direction it just moved."""

from polytrader.strategy.base import MarketState, Strategy, StrategyContext
from polytrader.strategy.follow import FollowStrategy


def _mkt(mid: float) -> MarketState:
    return MarketState("m1", "t1", "Q?", best_bid=mid - 0.01, best_ask=mid + 0.01,
                       midpoint=mid, timestamp="2026-06-30T00:00:00")


def _ctx() -> StrategyContext:
    return StrategyContext(positions=[], remaining_exposure_usd=100.0)


def _feed(strat, mids):
    last = []
    for mid in mids:
        last = strat.on_tick([_mkt(mid)], _ctx())
    return last


def test_no_trade_on_first_tick():
    assert FollowStrategy().on_tick([_mkt(0.50)], _ctx()) == []


def test_follows_up_move_by_buying_the_ask():
    strat = FollowStrategy(size=1.0)
    out = _feed(strat, [0.50, 0.52])  # price rose
    assert len(out) == 1
    assert out[0].side == "BUY"
    assert out[0].price == _mkt(0.52).best_ask  # marketable (crosses) -> will fill


def test_follows_down_move_by_selling_the_bid():
    strat = FollowStrategy(size=1.0)
    out = _feed(strat, [0.50, 0.48])  # price fell
    assert len(out) == 1
    assert out[0].side == "SELL"
    assert out[0].price == _mkt(0.48).best_bid


def test_no_trade_when_price_unchanged():
    strat = FollowStrategy(size=1.0)
    assert _feed(strat, [0.50, 0.50]) == []


def test_is_a_strategy():
    assert isinstance(FollowStrategy(), Strategy)
