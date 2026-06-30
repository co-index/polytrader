"""MomentumStrategy: follow the trend over a rolling window of the midpoint."""

from polytrader.strategy.base import MarketState, Strategy, StrategyContext
from polytrader.strategy.momentum import MomentumStrategy


def _mkt(mid: float) -> MarketState:
    return MarketState("m1", "t1", "Q?", best_bid=mid - 0.01, best_ask=mid + 0.01,
                       midpoint=mid, timestamp="2026-06-29T00:00:00")


def _ctx() -> StrategyContext:
    return StrategyContext(positions=[], remaining_exposure_usd=100.0)


def _feed(strat, mids):
    last = []
    for mid in mids:
        last = strat.on_tick([_mkt(mid)], _ctx())
    return last


def test_no_trade_while_warming_up():
    strat = MomentumStrategy(window=3, threshold=0.03)
    assert strat.on_tick([_mkt(0.50)], _ctx()) == []
    assert strat.on_tick([_mkt(0.52)], _ctx()) == []


def test_buys_on_uptrend():
    strat = MomentumStrategy(window=3, threshold=0.03)
    out = _feed(strat, [0.40, 0.45, 0.50])  # oldest 0.40; 0.50 >= 0.43
    assert [i.side for i in out] == ["BUY"]


def test_sells_on_downtrend():
    strat = MomentumStrategy(window=3, threshold=0.03)
    out = _feed(strat, [0.50, 0.45, 0.40])  # oldest 0.50; 0.40 <= 0.47
    assert [i.side for i in out] == ["SELL"]


def test_no_trade_when_flat():
    strat = MomentumStrategy(window=3, threshold=0.03)
    out = _feed(strat, [0.50, 0.50, 0.51])
    assert out == []


def test_no_trade_when_move_does_not_beat_a_wide_spread():
    # Wide book: spread 0.10. A 0.04 move beats threshold 0.03 but not the spread,
    # so crossing would lose -> no trade.
    def _wide(mid):
        return MarketState("m1", "t1", "Q?", best_bid=mid - 0.05, best_ask=mid + 0.05,
                           midpoint=mid, timestamp="t")
    strat = MomentumStrategy(window=3, threshold=0.03)
    last = []
    for mid in [0.40, 0.42, 0.44]:  # rose 0.04 over the window
        last = strat.on_tick([_wide(mid)], _ctx())
    assert last == []


def test_is_a_strategy():
    assert isinstance(MomentumStrategy(), Strategy)
