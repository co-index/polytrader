"""Strategy interface and the types passed across the strategy boundary.

A Strategy is a pluggable unit: it receives a market snapshot and returns proposed
orders. It MUST NOT touch the exchange SDK, the store, or the engine directly
(Constitution V) — it is pure logic over the inputs it is handed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

Side = Literal["BUY", "SELL"]


@dataclass
class MarketState:
    """Snapshot of one tradable outcome token at a tick."""

    market_id: str
    token_id: str
    question: str
    best_bid: float
    best_ask: float
    midpoint: float
    timestamp: str


class OrderIntent(BaseModel):
    """A proposed order, before risk evaluation. Validated on construction."""

    market_id: str
    token_id: str
    side: Side
    size: float = Field(gt=0)
    price: float = Field(gt=0, lt=1)


@dataclass
class PositionView:
    market_id: str
    token_id: str
    size: float
    avg_cost: float


@dataclass
class StrategyContext:
    """Read-only context for a tick. A strategy may read remaining budget but cannot
    change risk limits (FR-014)."""

    positions: list[PositionView] = field(default_factory=list)
    remaining_exposure_usd: float = 0.0


@runtime_checkable
class Strategy(Protocol):
    name: str

    def on_tick(
        self, markets: list[MarketState], context: StrategyContext
    ) -> list[OrderIntent]:
        """Return zero or more proposed orders for this tick. No side effects, no I/O."""
        ...
