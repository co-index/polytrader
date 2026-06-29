"""Integration test: a full dry-run tick moves no real money.

data -> strategy -> risk gate -> SIMULATE -> record. The real client's place_order
must never be called in dry-run (SC-005 safety).
"""

from unittest.mock import MagicMock

from polytrader.config import RiskConfig, Settings
from polytrader.engine import Engine
from polytrader.risk import RiskManager
from polytrader.store import Store
from polytrader.strategy.base import MarketState
from polytrader.strategy.example import ExampleStrategy


def _settings():
    return Settings(
        risk=RiskConfig(
            per_order_max_usd=5,
            total_exposure_max_usd=50,
            daily_loss_limit_usd=20,
            market_whitelist=["m1"],
        )
    )


def _market():
    return MarketState("m1", "t1", "Q?", best_bid=0.40, best_ask=0.42, midpoint=0.41,
                       timestamp="2026-06-29T00:00:00")


def test_dry_run_tick_simulates_and_never_places_real_order():
    settings = _settings()
    store = Store(":memory:")
    store.init_schema()
    store.set_command(run=True, mode="dry_run")

    client = MagicMock()
    client.get_markets.return_value = [_market()]

    engine = Engine(client, RiskManager(settings.risk, store), store, ExampleStrategy(), settings)
    engine.tick()

    # No real order placed in dry-run.
    client.place_order.assert_not_called()
    # A simulated order was recorded in dry_run mode.
    orders = store.recent_orders(10)
    assert len(orders) == 1
    assert orders[0].mode == "dry_run"
    assert orders[0].status in ("placed", "filled")


def test_dry_run_tick_does_nothing_when_stopped():
    settings = _settings()
    store = Store(":memory:")
    store.init_schema()  # default run=0 (stopped)

    client = MagicMock()
    client.get_markets.return_value = [_market()]

    engine = Engine(client, RiskManager(settings.risk, store), store, ExampleStrategy(), settings)
    engine.tick()

    assert store.recent_orders(10) == []
    client.place_order.assert_not_called()
