"""The risk gate — every order passes here before it can reach the exchange.

Constitution II (NON-NEGOTIABLE): no order path may bypass this. check() approves or
rejects a single intent against all caps; daily_loss_breached() is the autonomous
circuit breaker the engine consults each tick (wired in US3).
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import RiskConfig
from .store import Store
from .strategy.base import OrderIntent


@dataclass
class Decision:
    approved: bool
    intent: OrderIntent
    reason: str | None = None


class RiskManager:
    def __init__(self, config: RiskConfig, store: Store):
        self.config = config
        self.store = store

    def current_exposure_usd(self) -> float:
        """Notional value of open positions in USD."""
        return sum(abs(p.size) * p.avg_cost for p in self.store.positions())

    def check(self, intent: OrderIntent) -> Decision:
        notional = intent.size * intent.price

        # Market whitelist.
        if intent.market_id not in self.config.market_whitelist:
            return Decision(False, intent, f"market not in whitelist: {intent.market_id}")

        # Per-order cap (checked before exposure so the most local limit reports first).
        if notional > self.config.per_order_max_usd:
            return Decision(
                False,
                intent,
                f"per-order cap exceeded: {notional:.2f} > {self.config.per_order_max_usd:.2f}",
            )

        # Total open-exposure cap.
        projected = self.current_exposure_usd() + notional
        if projected > self.config.total_exposure_max_usd:
            return Decision(
                False,
                intent,
                f"total exposure cap exceeded: {projected:.2f} > "
                f"{self.config.total_exposure_max_usd:.2f}",
            )

        return Decision(True, intent, None)

    def daily_loss_breached(self) -> bool:
        """True when today's realized loss has reached the configured limit."""
        return self.store.pnl_today().realized_usd <= -self.config.daily_loss_limit_usd
