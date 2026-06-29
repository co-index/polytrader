"""Market-making / spread capture (Constitution V: pure logic, no I/O).

Each tick, quote a resting BUY a half-spread below the midpoint and a resting SELL a
half-spread above it. When price oscillates across these quotes between ticks, the paper
fill model executes them and the strategy captures the spread. Quotes that would fall
outside (0, 1) are dropped.
"""

from __future__ import annotations

from .base import MarketState, OrderIntent, StrategyContext


class MarketMakingStrategy:
    name = "market_making"

    def __init__(self, size: float = 1.0, half_spread: float = 0.02):
        self.size = size
        self.half_spread = half_spread

    def on_tick(
        self, markets: list[MarketState], context: StrategyContext
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        for m in markets:
            if not 0 < m.midpoint < 1:
                continue
            bid = round(m.midpoint - self.half_spread, 3)
            ask = round(m.midpoint + self.half_spread, 3)
            if 0 < bid < 1:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="BUY", size=self.size, price=bid))
            if 0 < ask < 1:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="SELL", size=self.size, price=ask))
        return intents
