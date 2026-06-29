"""PaperRunner — the paper-trading tick loop.

Each tick: fetch one real market snapshot and feed the SAME snapshot to every strategy,
each with its own broker and risk gate. Every intent passes that strategy's
RiskManager.check (Constitution II); approved intents go to the broker's fill model;
then positions are marked to market and one leaderboard row per strategy is written.
A strategy that raises is isolated so one bad strategy never stops the others.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from ..risk import RiskManager
from ..strategy.base import OrderIntent, PositionView, Strategy, StrategyContext
from .broker import PaperBroker
from .store import PaperStore

log = logging.getLogger("polytrader.paper")

Entry = tuple[Strategy, PaperBroker, RiskManager]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PaperRunner:
    def __init__(self, client, store: PaperStore, entries: list[Entry],
                 tick_ts: Callable[[], str] = _now, tick_interval_seconds: float = 5.0):
        self.client = client
        self.store = store
        self.entries = entries
        self.tick_ts = tick_ts
        self.tick_interval_seconds = tick_interval_seconds

    def _context(self, broker: PaperBroker, risk: RiskManager) -> StrategyContext:
        positions = [
            PositionView(p.market_id, p.token_id, p.size, p.avg_cost)
            for p in broker.positions()
        ]
        remaining = risk.config.total_exposure_max_usd - risk.current_exposure_usd()
        return StrategyContext(positions=positions, remaining_exposure_usd=remaining)

    def tick(self) -> None:
        try:
            snapshot = self.client.get_markets()
        except Exception as e:  # noqa: BLE001 - never fabricate data on a fetch failure
            log.warning("market fetch failed; skipping tick: %s", e)
            return

        market_by_token = {m.token_id: m for m in snapshot}

        for strategy, broker, risk in self.entries:
            try:
                intents = strategy.on_tick(snapshot, self._context(broker, risk))
            except Exception as e:  # noqa: BLE001 - isolate a bad strategy
                log.warning("strategy %s on_tick raised: %s", strategy.name, e)
                intents = []

            for intent in intents:
                if not isinstance(intent, OrderIntent):
                    continue
                if not risk.check(intent).approved:
                    broker.note_reject()
                    continue
                market = market_by_token.get(intent.token_id)
                if market is not None:
                    broker.execute(intent, market)

            broker.mark_to_market(snapshot)

        self.store.write_leaderboard(
            [broker.summary() for _, broker, _ in self.entries], ts=self.tick_ts()
        )

    def run(self) -> None:  # pragma: no cover - long-running loop
        log.info("paper runner started with %d strategies", len(self.entries))
        while True:
            self.tick()
            time.sleep(self.tick_interval_seconds)
