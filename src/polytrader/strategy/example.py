"""Bundled example strategy — proves the pipeline end to end (FR-013).

Deliberately trivial and conservative: for each market it places one tiny resting BUY
at the current best bid. It exists to exercise data -> strategy -> risk gate -> record,
not to make money. Real strategies replace it.
"""

from __future__ import annotations

from .base import MarketState, OrderIntent, StrategyContext


class ExampleStrategy:
    name = "example"

    def __init__(self, size: float = 1.0):
        self.size = size

    def on_tick(
        self, markets: list[MarketState], context: StrategyContext
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        for m in markets:
            # Rest a tiny buy at the best bid; skip if the book has no sane price.
            if 0 < m.best_bid < 1:
                intents.append(
                    OrderIntent(
                        market_id=m.market_id,
                        token_id=m.token_id,
                        side="BUY",
                        size=self.size,
                        price=m.best_bid,
                    )
                )
        return intents
