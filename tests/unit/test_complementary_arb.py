"""Complementary-outcome arbitrage strategy.

In a binary Polymarket market the two outcome tokens (YES / NO) settle to exactly
$1 between them. So buying one share of each leg costs (ask_yes + ask_no) and is
guaranteed to redeem for $1 — whenever that cost is below 1 (minus a buffer) the
gap is locked-in, outcome-independent profit. These tests pin that behavior through
the public Strategy interface.
"""

from polytrader.strategy.base import MarketState, OrderIntent, Strategy, StrategyContext
from polytrader.strategy.complementary_arb import ComplementaryArbStrategy


def _leg(market_id: str, token_id: str, best_ask: float) -> MarketState:
    return MarketState(
        market_id=market_id,
        token_id=token_id,
        question="Will it rain?",
        best_bid=max(best_ask - 0.02, 0.0),
        best_ask=best_ask,
        midpoint=best_ask,
        timestamp="2026-06-29T00:00:00",
    )


def _ctx() -> StrategyContext:
    return StrategyContext(positions=[], remaining_exposure_usd=100.0)


def test_buys_both_legs_when_pair_is_underpriced():
    strat = ComplementaryArbStrategy(size=1.0, min_edge=0.01)
    assert isinstance(strat, Strategy)

    # YES ask 0.40 + NO ask 0.55 = 0.95 -> 0.05 locked-in profit per pair.
    markets = [_leg("m1", "yes", 0.40), _leg("m1", "no", 0.55)]
    intents = strat.on_tick(markets, _ctx())

    assert len(intents) == 2
    assert all(isinstance(i, OrderIntent) for i in intents)
    assert all(i.side == "BUY" and i.market_id == "m1" for i in intents)
    by_token = {i.token_id: i for i in intents}
    assert by_token["yes"].price == 0.40
    assert by_token["no"].price == 0.55
    assert all(i.size == 1.0 for i in intents)


def test_no_trade_when_pair_sums_to_a_dollar_or_more():
    strat = ComplementaryArbStrategy(size=1.0, min_edge=0.01)
    # 0.50 + 0.55 = 1.05 -> no edge, buying both would lose money.
    markets = [_leg("m1", "yes", 0.50), _leg("m1", "no", 0.55)]
    assert strat.on_tick(markets, _ctx()) == []


def test_no_trade_when_edge_is_thinner_than_min_edge():
    strat = ComplementaryArbStrategy(size=1.0, min_edge=0.01)
    # 0.50 + 0.495 = 0.995 -> 0.005 profit, below the 0.01 buffer.
    markets = [_leg("m1", "yes", 0.50), _leg("m1", "no", 0.495)]
    assert strat.on_tick(markets, _ctx()) == []


def test_ignores_a_market_with_only_one_outcome_configured():
    strat = ComplementaryArbStrategy(size=1.0, min_edge=0.01)
    # Only one leg of m1 is configured -> not a complementary pair.
    markets = [_leg("m1", "yes", 0.40)]
    assert strat.on_tick(markets, _ctx()) == []


def test_skips_a_pair_with_an_empty_book_on_one_leg():
    strat = ComplementaryArbStrategy(size=1.0, min_edge=0.01)
    # NO has no ask (empty book -> best_ask 0.0): cannot complete the pair.
    markets = [_leg("m1", "yes", 0.40), _leg("m1", "no", 0.0)]
    assert strat.on_tick(markets, _ctx()) == []
