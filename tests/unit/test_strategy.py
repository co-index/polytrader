"""Unit tests for the strategy interface and the bundled example strategy."""

import pytest
from pydantic import ValidationError

from polytrader.strategy.base import MarketState, OrderIntent, Strategy, StrategyContext
from polytrader.strategy.example import ExampleStrategy


def _market(best_bid=0.40, best_ask=0.42) -> MarketState:
    return MarketState(
        market_id="m1",
        token_id="t1",
        question="Will it rain?",
        best_bid=best_bid,
        best_ask=best_ask,
        midpoint=(best_bid + best_ask) / 2,
        timestamp="2026-06-29T00:00:00",
    )


def _ctx() -> StrategyContext:
    return StrategyContext(positions=[], remaining_exposure_usd=50.0)


def test_order_intent_rejects_zero_size():
    with pytest.raises(ValidationError):
        OrderIntent(market_id="m1", token_id="t1", side="BUY", size=0, price=0.4)


def test_order_intent_rejects_price_out_of_range():
    with pytest.raises(ValidationError):
        OrderIntent(market_id="m1", token_id="t1", side="BUY", size=1, price=1.0)
    with pytest.raises(ValidationError):
        OrderIntent(market_id="m1", token_id="t1", side="BUY", size=1, price=0.0)


def test_order_intent_rejects_bad_side():
    with pytest.raises(ValidationError):
        OrderIntent(market_id="m1", token_id="t1", side="HODL", size=1, price=0.4)


def test_order_intent_valid():
    oi = OrderIntent(market_id="m1", token_id="t1", side="BUY", size=1.5, price=0.4)
    assert oi.side == "BUY"
    assert oi.size == 1.5


def test_example_strategy_is_a_strategy_and_returns_valid_intents():
    strat = ExampleStrategy()
    assert isinstance(strat, Strategy)
    intents = strat.on_tick([_market()], _ctx())
    assert all(isinstance(i, OrderIntent) for i in intents)
    for i in intents:
        assert i.size > 0
        assert 0 < i.price < 1
        assert i.market_id == "m1"
