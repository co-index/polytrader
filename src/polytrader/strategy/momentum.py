"""Momentum / trend following (Constitution V: pure logic, no I/O).

Keeps a rolling window of each token's midpoint. Once full, it compares the current
midpoint to the oldest value in the window: BUY (marketable, at the ask) on an uptrend of
at least `threshold`, SELL (at the bid) on a downtrend. No trade while warming up or flat.
"""

from __future__ import annotations

from collections import defaultdict, deque

from .base import MarketState, OrderIntent, StrategyContext


class MomentumStrategy:
    name = "momentum"

    def __init__(self, size: float = 1.0, window: int = 20, threshold: float = 0.03):
        self.size = size
        self.window = window
        self.threshold = threshold
        self._hist: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=window))

    def on_tick(
        self, markets: list[MarketState], context: StrategyContext
    ) -> list[OrderIntent]:
        intents: list[OrderIntent] = []
        for m in markets:
            hist = self._hist[m.token_id]
            hist.append(m.midpoint)
            if len(hist) < self.window:
                continue
            oldest = hist[0]
            if m.midpoint >= oldest + self.threshold and m.best_ask > 0:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="BUY", size=self.size, price=m.best_ask))
            elif m.midpoint <= oldest - self.threshold and m.best_bid > 0:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="SELL", size=self.size, price=m.best_bid))
        return intents
