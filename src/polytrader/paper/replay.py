"""ReplayClient — a SYNTHETIC market-data source for the paper lab (NOT real data).

Each tick it nudges every token's midpoint by a small random step (a bounded random walk)
and quotes a fixed spread around it, so strategies see real movement and actually trade.
Use only to demonstrate trade/P&L mechanics when no live Polymarket feed is available —
the prices are made up. Drop-in for PolymarketClient: it exposes get_markets().
"""

from __future__ import annotations

import random

from ..strategy.base import MarketState

# (market_id, token_id, question, starting_midpoint)
Spec = tuple[str, str, str, float]


class ReplayClient:
    def __init__(self, specs: list[Spec], seed: int = 0, spread: float = 0.01,
                 vol: float = 0.02):
        self._specs = specs
        self._rng = random.Random(seed)
        self._spread = spread
        self._vol = vol
        self._mid: dict[str, float] = {tok: start for _, tok, _q, start in specs}
        self._n = 0

    def get_markets(self) -> list[MarketState]:
        self._n += 1
        half = self._spread / 2
        out: list[MarketState] = []
        for market_id, token_id, question, _start in self._specs:
            mid = self._mid[token_id] + self._rng.gauss(0, self._vol)
            mid = min(0.97, max(0.03, mid))  # keep a valid two-sided book in (0, 1)
            self._mid[token_id] = mid
            out.append(MarketState(
                market_id=market_id, token_id=token_id, question=question,
                best_bid=round(mid - half, 3), best_ask=round(mid + half, 3),
                midpoint=round(mid, 4), timestamp=f"sim-{self._n}",
            ))
        return out
