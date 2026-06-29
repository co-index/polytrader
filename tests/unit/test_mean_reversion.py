"""MeanReversionStrategy: fade deviations from a rolling mean of the midpoint."""

from polytrader.strategy.base import MarketState, Strategy, StrategyContext
from polytrader.strategy.mean_reversion import MeanReversionStrategy


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
    strat = MeanReversionStrategy(window=3, threshold=0.03)
    assert strat.on_tick([_mkt(0.50)], _ctx()) == []
    assert strat.on_tick([_mkt(0.50)], _ctx()) == []  # still < window


def test_buys_when_price_dips_below_mean():
    strat = MeanReversionStrategy(window=3, threshold=0.03)
    out = _feed(strat, [0.50, 0.50, 0.40])  # mean 0.4667; 0.40 <= 0.4367
    assert [i.side for i in out] == ["BUY"]


def test_sells_when_price_rises_above_mean():
    strat = MeanReversionStrategy(window=3, threshold=0.03)
    out = _feed(strat, [0.50, 0.50, 0.60])  # mean 0.5333; 0.60 >= 0.5633
    assert [i.side for i in out] == ["SELL"]


def test_no_trade_inside_band():
    strat = MeanReversionStrategy(window=3, threshold=0.03)
    out = _feed(strat, [0.50, 0.50, 0.51])  # within +/- 0.03 of mean
    assert out == []


def test_is_a_strategy():
    assert isinstance(MeanReversionStrategy(), Strategy)
