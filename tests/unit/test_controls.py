"""The dashboard controls the engine only through the store's command channel.
These tests assert that commands written to the store change engine behavior.
"""

from unittest.mock import MagicMock

from polytrader.client import PlacedOrder
from polytrader.config import RiskConfig, Settings
from polytrader.engine import Engine
from polytrader.risk import RiskManager
from polytrader.store import Store
from polytrader.strategy.base import MarketState
from polytrader.strategy.example import ExampleStrategy


def _setup():
    settings = Settings(risk=RiskConfig(
        per_order_max_usd=5, total_exposure_max_usd=50,
        daily_loss_limit_usd=20, market_whitelist=["m1"]))
    store = Store(":memory:")
    store.init_schema()
    client = MagicMock()
    client.get_markets.return_value = [MarketState("m1", "t1", "Q?", 0.4, 0.42, 0.41, "t0")]
    client.place_order.return_value = PlacedOrder(client_order_id="X")
    engine = Engine(client, RiskManager(settings.risk, store), store, ExampleStrategy(), settings)
    return store, client, engine


def test_mode_switch_command_takes_effect_on_next_tick():
    store, client, engine = _setup()

    store.set_command(run=True, mode="dry_run")
    engine.tick()
    client.place_order.assert_not_called()  # dry-run: no real order

    store.set_command(mode="live")
    engine.tick()
    client.place_order.assert_called_once()  # live: real order placed


def test_stop_command_idles_the_engine():
    store, client, engine = _setup()
    store.set_command(run=True, mode="dry_run")
    engine.tick()
    assert len(store.recent_orders(10)) == 1

    store.set_command(run=False)
    engine.tick()
    assert len(store.recent_orders(10)) == 1  # no new orders while stopped


def test_kill_command_cancels_all_via_engine():
    store, client, engine = _setup()
    store.set_command(run=True, mode="live", kill=True)
    engine.tick()
    client.cancel_all.assert_called_once()
    assert store.get_engine_state().run is False
