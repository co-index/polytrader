"""Mean reversion (Constitution V: pure logic, no I/O).

Keeps a rolling window of each token's midpoint. Once the window is full, it fades
deviations: BUY (marketable, at the ask) when the midpoint sits a threshold below the
window mean, SELL (at the bid) when it sits a threshold above. No trade while warming up
or inside the band.
"""

from __future__ import annotations

from collections import defaultdict, deque

from .base import MarketState, OrderIntent, StrategyContext


class MeanReversionStrategy:
    name = "mean_reversion"

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
            mean = sum(hist) / len(hist)
            if m.midpoint <= mean - self.threshold and m.best_ask > 0:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="BUY", size=self.size, price=m.best_ask))
            elif m.midpoint >= mean + self.threshold and m.best_bid > 0:
                intents.append(OrderIntent(market_id=m.market_id, token_id=m.token_id,
                                           side="SELL", size=self.size, price=m.best_bid))
        return intents
