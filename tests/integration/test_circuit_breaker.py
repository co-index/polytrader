"""Integration test: when today's realized loss reaches the limit, the engine stops
itself within one tick — no operator action (SC-003).
"""

from datetime import date
from unittest.mock import MagicMock

from polytrader.config import RiskConfig, Settings
from polytrader.engine import Engine
from polytrader.risk import RiskManager
from polytrader.store import Store
from polytrader.strategy.example import ExampleStrategy


def test_engine_auto_stops_when_daily_loss_breached():
    settings = Settings(risk=RiskConfig(
        per_order_max_usd=5, total_exposure_max_usd=50,
        daily_loss_limit_usd=20, market_whitelist=["m1"]))
    store = Store(":memory:")
    store.init_schema()
    store.set_command(run=True, mode="dry_run")
    # Simulate the day's losing fills having already crossed the threshold.
    store.record_realized_pnl(date.today().isoformat(), -25.0)

    client = MagicMock()
    engine = Engine(client, RiskManager(settings.risk, store), store, ExampleStrategy(), settings)
    engine.tick()

    state = store.get_engine_state()
    assert state.run is False
    assert state.stopped_reason == "daily-loss circuit breaker"
    # No trading happened on this tick.
    client.get_markets.assert_not_called()
    assert store.recent_orders(10) == []
