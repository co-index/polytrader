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
        ts = self.tick_ts()

        for strategy, broker, risk in self.entries:
            # Maker fills first: did this tick's price move through last tick's resting quotes?
            broker.settle_resting(market_by_token, ts)
            try:
                intents = strategy.on_tick(snapshot, self._context(broker, risk))
            except Exception as e:  # noqa: BLE001 - isolate a bad strategy
                log.warning("strategy %s on_tick raised: %s", strategy.name, e)
                intents = []

            for intent in intents:
                if not isinstance(intent, OrderIntent):
                    continue
                decision = risk.check(intent)
                if not decision.approved:
                    broker.record_rejected(intent, ts, decision.reason or "")
                    continue
                market = market_by_token.get(intent.token_id)
                if market is not None:
                    broker.execute(intent, market, ts)

            broker.mark_to_market(snapshot)
            self.store.write_orders(strategy.name, broker.orders())

        self.store.write_leaderboard(
            [broker.summary() for _, broker, _ in self.entries], ts=ts
        )

    def run(self) -> None:  # pragma: no cover - long-running loop
        log.info("paper runner started with %d strategies", len(self.entries))
        while True:
            self.tick()
            time.sleep(self.tick_interval_seconds)


def main() -> None:  # pragma: no cover - retired entry point
    """RETIRED. The six directional/market-making paper strategies (market_making,
    mean_reversion, momentum, follow, complementary_arb, example) are no longer run:
    on real Polymarket books they essentially never profit (moves < spread; arb sum
    > 1). The Paper Lab now runs only the basket-arb scanner, which captures the one
    structural edge that actually exists.

    The `PaperRunner` class above and the strategy classes remain importable for
    experiments/tests, but this launcher will not spawn them. Run the scanner instead:

        polytrader-scanner        # or: python -m polytrader.basket_scanner
    """
    import sys

    sys.stderr.write(
        "polytrader.paper.runner is retired (the 6 directional strategies never "
        "profited on real books).\nRun the basket-arb scanner instead:\n"
        "    polytrader-scanner\n"
    )
    raise SystemExit(2)


if __name__ == "__main__":  # pragma: no cover
    main()
