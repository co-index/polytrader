"""Integration test: a live tick places exactly the risk-approved order, and rejects
intents that breach a limit without placing them.
"""

from unittest.mock import MagicMock

from polytrader.client import PlacedOrder
from polytrader.config import RiskConfig, Settings
from polytrader.engine import Engine
from polytrader.risk import RiskManager
from polytrader.store import Store
from polytrader.strategy.base import MarketState
from polytrader.strategy.example import ExampleStrategy


def _market():
    return MarketState("m1", "t1", "Q?", best_bid=0.40, best_ask=0.42, midpoint=0.41,
                       timestamp="2026-06-29T00:00:00")


def _engine(store, settings, client):
    return Engine(client, RiskManager(settings.risk, store), store, ExampleStrategy(), settings)


def test_live_tick_places_the_approved_order():
    settings = Settings(risk=RiskConfig(
        per_order_max_usd=5, total_exposure_max_usd=50,
        daily_loss_limit_usd=20, market_whitelist=["m1"]))
    store = Store(":memory:")
    store.init_schema()
    store.set_command(run=True, mode="live")

    client = MagicMock()
    client.get_markets.return_value = [_market()]
    client.place_order.return_value = PlacedOrder(client_order_id="X1")

    _engine(store, settings, client).tick()

    client.place_order.assert_called_once()
    placed_intent = client.place_order.call_args.args[0]
    assert placed_intent.market_id == "m1"
    orders = store.recent_orders(10)
    assert orders[0].status == "placed"
    assert orders[0].mode == "live"
    assert orders[0].client_order_id == "X1"


def test_live_tick_rejects_over_limit_intent_without_placing():
    # per-order cap below the example's notional (size 1 * price 0.40 = 0.40) -> reject.
    settings = Settings(risk=RiskConfig(
        per_order_max_usd=0.10, total_exposure_max_usd=50,
        daily_loss_limit_usd=20, market_whitelist=["m1"]))
    store = Store(":memory:")
    store.init_schema()
    store.set_command(run=True, mode="live")

    client = MagicMock()
    client.get_markets.return_value = [_market()]

    _engine(store, settings, client).tick()

    client.place_order.assert_not_called()
    orders = store.recent_orders(10)
    assert orders[0].status == "rejected"
    assert "per-order" in orders[0].reason.lower()
