"""Engine resilience: a throwing strategy never crashes the loop; the kill switch
cancels all open orders and stops.
"""

from unittest.mock import MagicMock

from polytrader.config import RiskConfig, Settings
from polytrader.engine import Engine
from polytrader.risk import RiskManager
from polytrader.store import Store
from polytrader.strategy.base import MarketState


def _settings():
    return Settings(risk=RiskConfig(
        per_order_max_usd=5, total_exposure_max_usd=50,
        daily_loss_limit_usd=20, market_whitelist=["m1"]))


def _store():
    s = Store(":memory:")
    s.init_schema()
    return s


class _BoomStrategy:
    name = "boom"

    def on_tick(self, markets, context):
        raise ValueError("strategy blew up")


def test_throwing_strategy_does_not_crash_tick():
    settings = _settings()
    store = _store()
    store.set_command(run=True, mode="dry_run")
    client = MagicMock()
    client.get_markets.return_value = [
        MarketState("m1", "t1", "Q?", 0.4, 0.42, 0.41, "t0")
    ]

    engine = Engine(client, RiskManager(settings.risk, store), store, _BoomStrategy(), settings)
    engine.tick()  # must not raise

    assert store.recent_orders(10) == []
    events = store.recent_events(10)
    assert any(e.level == "error" and "on_tick" in e.message for e in events)


def test_kill_switch_cancels_all_and_stops():
    settings = _settings()
    store = _store()
    store.set_command(run=True, mode="live", kill=True)
    client = MagicMock()

    engine = Engine(client, RiskManager(settings.risk, store), store, MagicMock(), settings)
    engine.tick()

    client.cancel_all.assert_called_once()
    state = store.get_engine_state()
    assert state.run is False
    assert state.stopped_reason == "kill switch"
