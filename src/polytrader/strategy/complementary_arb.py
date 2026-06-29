"""Complementary-outcome arbitrage (Constitution V: pure logic, no I/O).

A binary market's two outcome tokens redeem to exactly $1 between them: one pays $1,
the other $0. So one share of each leg always redeems for $1 regardless of outcome.
When the two best asks sum to less than $1, buying both legs locks in the difference
as outcome-independent profit. We act only when that profit clears `min_edge` (a buffer
for fees/slippage), and never on a market whose book is incomplete.

The two legs of a market are the two `MarketState`s sharing a `market_id` — configure
both outcome tokens of a market in settings.markets for this strategy to see a pair.
"""

from __future__ import annotations

from collections import defaultdict

from .base import MarketState, OrderIntent, StrategyContext


class ComplementaryArbStrategy:
    name = "complementary_arb"

    def __init__(self, size: float = 1.0, min_edge: float = 0.01):
        self.size = size
        self.min_edge = min_edge

    def on_tick(
        self, markets: list[MarketState], context: StrategyContext
    ) -> list[OrderIntent]:
        by_market: dict[str, list[MarketState]] = defaultdict(list)
        for m in markets:
            by_market[m.market_id].append(m)

        intents: list[OrderIntent] = []
        for legs in by_market.values():
            # Only a clean two-outcome market is a complementary pair.
            if len(legs) != 2:
                continue
            a, b = legs
            # Both legs need a real ask to buy against.
            if a.best_ask <= 0 or b.best_ask <= 0:
                continue
            cost = a.best_ask + b.best_ask
            if cost <= 1 - self.min_edge:
                intents.append(self._buy(a))
                intents.append(self._buy(b))
        return intents

    def _buy(self, leg: MarketState) -> OrderIntent:
        return OrderIntent(
            market_id=leg.market_id,
            token_id=leg.token_id,
            side="BUY",
            size=self.size,
            price=leg.best_ask,
        )
