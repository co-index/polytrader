"""The engine: one tick = fetch markets, run the strategy, gate every intent, then
simulate (dry-run) or place (live), recording everything.

Constitution II: every intent goes through risk.check() — there is no other order path.
Constitution III: a fresh start is dry_run; live is entered only via an explicit command.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from .client import PolymarketClient
from .config import Settings
from .risk import RiskManager
from .store import Fill, Order, Position, Store
from .strategy.base import OrderIntent, PositionView, Strategy, StrategyContext


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Engine:
    def __init__(
        self,
        client: PolymarketClient,
        risk: RiskManager,
        store: Store,
        strategy: Strategy,
        settings: Settings,
    ):
        self.client = client
        self.risk = risk
        self.store = store
        self.strategy = strategy
        self.settings = settings

    def _context(self) -> StrategyContext:
        positions = [
            PositionView(p.market_id, p.token_id, p.size, p.avg_cost)
            for p in self.store.positions()
        ]
        remaining = self.settings.risk.total_exposure_max_usd - self.risk.current_exposure_usd()
        return StrategyContext(positions=positions, remaining_exposure_usd=remaining)

    def tick(self) -> None:
        state = self.store.get_engine_state()

        # Kill switch: cancel everything and stop, even if a command race just happened.
        if state.kill:
            try:
                self.client.cancel_all()
            except Exception as e:  # noqa: BLE001
                self.store.log_event("error", "kill", f"cancel_all failed: {e}")
            self.store.set_command(run=False, kill=False)
            self.store.set_status(stopped_reason="kill switch")
            self.store.log_event("warn", "engine", "kill switch: cancelled all, stopped")
            return

        if not state.run:
            return

        # Daily-loss circuit breaker: stop autonomously before trading any further.
        if self.risk.daily_loss_breached():
            self.store.set_command(run=False)
            self.store.set_status(stopped_reason="daily-loss circuit breaker")
            self.store.log_event("warn", "risk", "daily-loss circuit breaker tripped; stopped")
            return

        # Strategy failures are isolated — a bad tick must never crash the loop.
        try:
            intents = self.strategy.on_tick(self.client.get_markets(), self._context())
        except Exception as e:  # noqa: BLE001
            self.store.log_event("error", "strategy", f"on_tick raised: {e}")
            return

        for intent in intents:
            if not isinstance(intent, OrderIntent):
                self.store.log_event("error", "strategy", f"dropped malformed intent: {intent!r}")
                continue
            self._handle_intent(intent, state.mode)

        self.store.set_status(last_tick_ts=_now())

    def _handle_intent(self, intent: OrderIntent, mode: str) -> None:
        decision = self.risk.check(intent)
        if not decision.approved:
            self.store.record_order(self._order(intent, mode, "rejected", reason=decision.reason))
            self.store.log_event("warn", "risk", f"rejected {intent.market_id}: {decision.reason}")
            return

        if mode == "live":
            try:
                placed = self.client.place_order(intent)
            except Exception as e:  # noqa: BLE001
                self.store.record_order(
                    self._order(intent, mode, "rejected", reason=f"place failed: {e}")
                )
                self.store.log_event("error", "client", f"place_order failed: {e}")
                return
            self.store.record_order(
                self._order(intent, mode, "placed", client_order_id=placed.client_order_id)
            )
        else:
            # dry_run: simulate a fill at the intent's price so P&L/positions populate.
            oid = self.store.record_order(self._order(intent, mode, "placed"))
            self.store.record_fill(Fill(order_id=oid, ts=_now(), size=intent.size,
                                        price=intent.price, mode=mode))
            self._apply_simulated_fill(intent)

    def _apply_simulated_fill(self, intent: OrderIntent) -> None:
        delta = intent.size if intent.side == "BUY" else -intent.size
        existing = {(p.market_id, p.token_id): p for p in self.store.positions()}
        prev = existing.get((intent.market_id, intent.token_id))
        new_size = (prev.size if prev else 0.0) + delta
        self.store.upsert_position(
            Position(intent.market_id, intent.token_id, new_size, intent.price, _now())
        )

    def _order(self, intent: OrderIntent, mode: str, status: str, *, reason=None,
               client_order_id=None) -> Order:
        return Order(
            ts=_now(), market_id=intent.market_id, token_id=intent.token_id, side=intent.side,
            size=intent.size, price=intent.price, mode=mode, status=status, reason=reason,
            client_order_id=client_order_id,
        )

    def run(self) -> None:
        self.store.log_event("info", "engine", "engine loop started")
        while True:
            self.tick()
            if self.store.get_engine_state().stopped_reason == "kill switch":
                break
            time.sleep(self.settings.tick_interval_seconds)


def main() -> None:  # pragma: no cover - wiring entry point
    import os

    settings = Settings.load("config.yaml", env=os.environ)
    store = Store(settings.db_path)
    store.init_schema()
    # A fresh start is always dry_run (Constitution III); operator switches to live in the UI.
    store.set_command(run=True, mode="dry_run")
    client = PolymarketClient(settings)
    risk = RiskManager(settings.risk, store)
    from .strategy.example import ExampleStrategy

    Engine(client, risk, store, ExampleStrategy(), settings).run()


if __name__ == "__main__":  # pragma: no cover
    main()
