"""Copy-follow / 跟单 (Constitution V: pure logic, no I/O).

Follows the market's most recent move by taking liquidity in the same direction: if the
midpoint rose since the last tick, BUY at the ask; if it fell, SELL at the bid. Because it
crosses the spread, it actually fills (a taker) — unlike the passive market-making/example
quotes. It pays the spread on every move, so it trades a lot; whether that wins is exactly
what the paper lab measures.
"""

from __future__ import annotations

from .base import MarketState, OrderIntent, StrategyContext


class FollowStrategy:
    name = "follow"

    def __init__(self, size: float = 1.0):
        self.size = size
        self._last: dict[str, float] = {}

    def on_tick(
        self, markets: list[MarketState], context: StrategyContext
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        for m in markets:
            prev = self._last.get(m.token_id)
            self._last[m.token_id] = m.midpoint
            if prev is None:
                continue
            # Spread-aware: only chase a move large enough to clear the spread we cross.
            spread = m.best_ask - m.best_bid if m.best_ask > 0 and m.best_bid > 0 else 0.0
            move = m.midpoint - prev
            if move > spread and m.best_ask > 0:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="BUY", size=self.size, price=m.best_ask))
            elif -move > spread and m.best_bid > 0:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="SELL", size=self.size, price=m.best_bid))
        return intents
