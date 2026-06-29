"""Paper fill model: marketable-only fills against a top-of-book snapshot."""

from polytrader.paper.fills import PaperFill, try_fill
from polytrader.strategy.base import MarketState, OrderIntent


def _mkt(best_bid=0.40, best_ask=0.42) -> MarketState:
    return MarketState("m1", "t1", "Q?", best_bid=best_bid, best_ask=best_ask,
                       midpoint=(best_bid + best_ask) / 2, timestamp="2026-06-29T00:00:00")


def _intent(side, price, size=1.0) -> OrderIntent:
    return OrderIntent(market_id="m1", token_id="t1", side=side, size=size, price=price)


def test_buy_fills_when_marketable_at_limit_price():
    fill = try_fill(_intent("BUY", 0.42), _mkt(best_ask=0.42))
    assert isinstance(fill, PaperFill)
    assert fill.side == "BUY" and fill.price == 0.42 and fill.size == 1.0


def test_buy_does_not_fill_below_ask():
    assert try_fill(_intent("BUY", 0.41), _mkt(best_ask=0.42)) is None


def test_sell_fills_when_marketable_at_limit_price():
    fill = try_fill(_intent("SELL", 0.40), _mkt(best_bid=0.40))
    assert isinstance(fill, PaperFill)
    assert fill.side == "SELL" and fill.price == 0.40


def test_sell_does_not_fill_above_bid():
    assert try_fill(_intent("SELL", 0.41), _mkt(best_bid=0.40)) is None


def test_no_fill_on_empty_book():
    assert try_fill(_intent("BUY", 0.42), _mkt(best_ask=0.0)) is None
    assert try_fill(_intent("SELL", 0.40), _mkt(best_bid=0.0)) is None
