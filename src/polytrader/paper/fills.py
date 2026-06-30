"""Pure top-of-book fill model for paper trading.

A strategy re-states its desired orders every tick, so a "resting" quote is simply one
that did not fill this tick and is re-evaluated next tick — no separate resting book is
needed. An order fills only when it is marketable against the current snapshot:

  BUY  @ P fills iff best_ask > 0 and P >= best_ask
  SELL @ P fills iff best_bid > 0 and P <= best_bid

Fill price is the intent's limit price P (conservative for a taker, accurate for a maker
who got hit at their quote). Simplifications: top-of-book only, top size assumed
sufficient (no partial fills), no queue position. Good for a fair relative comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..strategy.base import MarketState, OrderIntent


@dataclass
class PaperFill:
    token_id: str
    market_id: str
    side: str
    size: float
    price: float


def is_marketable(side: str, price: float, market: MarketState) -> bool:
    """True if an order at this price would cross the current book (BUY ≥ ask / SELL ≤ bid).

    Used both for taker fills (a new order crossing now) and maker fills (a resting order
    that a later tick's price has moved through)."""
    if side == "BUY":
        return market.best_ask > 0 and price >= market.best_ask
    return market.best_bid > 0 and price <= market.best_bid


def try_fill(intent: OrderIntent, market: MarketState) -> PaperFill | None:
    """Return a fill if the intent is marketable against the snapshot, else None."""
    if not is_marketable(intent.side, intent.price, market):
        return None
    return PaperFill(
        token_id=intent.token_id,
        market_id=intent.market_id,
        side=intent.side,
        size=intent.size,
        price=intent.price,
    )
