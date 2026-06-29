"""PaperBroker — one strategy's isolated simulated account.

Holds cash, signed positions (with cost basis), realized P&L, and counters. It exposes
`positions()` and `pnl_today()` with the same shapes the live Store returns, so a
`RiskManager` can be constructed against a broker unchanged (Constitution II in the lab).
Fills are decided by the pure `try_fill` model; the risk gate runs upstream in the runner.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..store import PnL, Position
from ..strategy.base import MarketState, OrderIntent
from .fills import PaperFill, try_fill


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
        self._orders: list[dict] = []

    # ---- order handling (gate already passed upstream) ----
    def execute(self, intent: OrderIntent, market: MarketState, ts: str = "") -> PaperFill | None:
        fill = try_fill(intent, market)
        if fill is None:
            return None
        delta = fill.size if fill.side == "BUY" else -fill.size
        self._apply(intent.token_id, intent.market_id, delta, fill.price)
        self.cash += -delta * fill.price
        self.fills += 1
        self._orders.append({
            "ts": ts, "token_id": fill.token_id, "side": fill.side,
            "size": fill.size, "price": fill.price, "status": "filled",
        })
        return fill

    def orders(self) -> list[dict]:
        """The per-fill order log (executed trades, newest last)."""
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

    def note_reject(self) -> None:
        self.rejects += 1

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
