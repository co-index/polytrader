"""PaperBroker — one strategy's isolated simulated account.

Holds cash, signed positions (with cost basis), realized P&L, and counters. It exposes
`positions()` and `pnl_today()` with the same shapes the live Store returns, so a
`RiskManager` can be constructed against a broker unchanged (Constitution II in the lab).
Fills are decided by the pure `try_fill` model; the risk gate runs upstream in the runner.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from ..store import PnL, Position
from ..strategy.base import MarketState, OrderIntent
from .fills import PaperFill, is_marketable


@dataclass
class _Pos:
    market_id: str
    size: float = 0.0
    avg_cost: float = 0.0
    last_mid: float = 0.0


@dataclass
class PaperBroker:
    name: str
    bankroll: float = 1000.0
    cash: float = field(default=0.0)
    realized: float = 0.0
    fills: int = 0
    rejects: int = 0
    wins: int = 0
    trades: int = 0

    def __post_init__(self) -> None:
        self.cash = self.bankroll
        self._pos: dict[str, _Pos] = {}
        # Every order the strategy places is logged (filled / resting / rejected); capped
        # so a re-quoting strategy doesn't grow it without bound.
        self._orders: deque[dict] = deque(maxlen=400)
        # Resting (non-marketable) orders from the current tick, checked for maker fills
        # against the next tick's book, then cancel-replaced.
        self._resting: list[tuple[str, str, str, float, float]] = []

    # ---- order handling (gate already passed upstream) ----
    def execute(self, intent: OrderIntent, market: MarketState, ts: str = "") -> PaperFill | None:
        """Taker path: fill now if the order crosses the book; otherwise let it rest."""
        if not is_marketable(intent.side, intent.price, market):
            self._resting.append((intent.token_id, intent.market_id, intent.side,
                                  intent.size, intent.price))
            self._log(ts, intent.token_id, intent.side, intent.size, intent.price, "resting")
            return None
        self._fill(intent.token_id, intent.market_id, intent.side, intent.size, intent.price, ts)
        return PaperFill(intent.token_id, intent.market_id, intent.side, intent.size, intent.price)

    def settle_resting(self, market_by_token: dict[str, MarketState], ts: str = "") -> None:
        """Maker path: fill resting orders the new tick's price moved through, then cancel
        the rest (cancel-replace — strategies re-quote every tick)."""
        for token_id, market_id, side, size, price in self._resting:
            m = market_by_token.get(token_id)
            if m is not None and is_marketable(side, price, m):
                self._fill(token_id, market_id, side, size, price, ts)
        self._resting = []

    def _fill(self, token_id: str, market_id: str, side: str, size: float, price: float,
              ts: str) -> None:
        delta = size if side == "BUY" else -size
        self._apply(token_id, market_id, delta, price)
        self.cash += -delta * price
        self.fills += 1
        self._log(ts, token_id, side, size, price, "filled")

    def record_rejected(self, intent: OrderIntent, ts: str = "", reason: str = "") -> None:
        """Log a risk-rejected order and count it."""
        self.rejects += 1
        self._log(ts, intent.token_id, intent.side, intent.size, intent.price, "rejected")

    def _log(self, ts: str, token_id: str, side: str, size: float, price: float,
             status: str) -> None:
        self._orders.append({"ts": ts, "token_id": token_id, "side": side,
                             "size": size, "price": price, "status": status})

    def orders(self) -> list[dict]:
        """Every order placed (filled / resting / rejected), oldest first, capped."""
        return list(self._orders)

    def _apply(self, token_id: str, market_id: str, delta: float, price: float) -> None:
        p = self._pos.setdefault(token_id, _Pos(market_id=market_id))
        old = p.size
        if old == 0 or (old > 0) == (delta > 0):
            # Opening or increasing on the same side: blend the cost basis.
            new_size = old + delta
            p.avg_cost = (abs(old) * p.avg_cost + abs(delta) * price) / abs(new_size)
            p.size = new_size
            return
        # Reducing / closing / flipping: book realized P&L on the closed quantity.
        closed = min(abs(old), abs(delta))
        gain = (price - p.avg_cost) if old > 0 else (p.avg_cost - price)
        self.realized += gain * closed
        self.trades += 1
        if gain > 0:
            self.wins += 1
        new_size = old + delta
        if abs(delta) > abs(old):
            p.avg_cost = price  # flipped — remainder opens a fresh position
        elif new_size == 0:
            p.avg_cost = 0.0
        p.size = new_size

    # ---- valuation ----
    def mark_to_market(self, markets: list[MarketState]) -> None:
        mids = {m.token_id: m.midpoint for m in markets}
        for token_id, p in self._pos.items():
            if token_id in mids and mids[token_id] > 0:
                p.last_mid = mids[token_id]

    def _unrealized(self) -> float:
        return sum(p.size * (p.last_mid - p.avg_cost) for p in self._pos.values() if p.size)

    def _equity(self) -> float:
        return self.cash + sum(p.size * p.last_mid for p in self._pos.values() if p.size)

    # ---- store-shaped reads (so RiskManager accepts the broker) ----
    def positions(self) -> list[Position]:
        return [
            Position(p.market_id, token_id, p.size, p.avg_cost, "")
            for token_id, p in self._pos.items()
            if p.size
        ]

    def pnl_today(self) -> PnL:
        return PnL(realized_usd=self.realized, unrealized_usd=self._unrealized())

    # ---- leaderboard row ----
    def summary(self) -> dict:
        return {
            "name": self.name,
            "equity": round(self._equity(), 4),
            "total_pnl": round(self._equity() - self.bankroll, 4),
            "realized": round(self.realized, 4),
            "unrealized": round(self._unrealized(), 4),
            "fills": self.fills,
            "positions": sum(1 for p in self._pos.values() if p.size),
            "wins": self.wins,
            "trades": self.trades,
            "rejects": self.rejects,
        }
