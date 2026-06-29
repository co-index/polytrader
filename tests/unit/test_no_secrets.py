"""Guards for Constitution I: secrets stay out of version control and out of logs."""

from pathlib import Path
from unittest.mock import MagicMock

from polytrader.config import RiskConfig, Settings
from polytrader.engine import Engine
from polytrader.risk import RiskManager
from polytrader.store import Store
from polytrader.strategy.base import MarketState
from polytrader.strategy.example import ExampleStrategy

SECRET = "0xPRIVATEKEYSHOULDNEVERLEAK"


def test_gitignore_blocks_secrets():
    gi = Path(".gitignore").read_text()
    assert ".env" in gi
    assert "*.key" in gi
    assert "*.db" in gi


def test_events_never_contain_the_private_key():
    settings = Settings(
        risk=RiskConfig(per_order_max_usd=0.01, total_exposure_max_usd=50,
                        daily_loss_limit_usd=20, market_whitelist=["m1"]),
        secrets={"wallet_private_key": SECRET, "clob_api_key": "shh"},
    )
    store = Store(":memory:")
    store.init_schema()
    store.set_command(run=True, mode="dry_run")

    client = MagicMock()
    client.get_markets.return_value = [MarketState("m1", "t1", "Q?", 0.4, 0.42, 0.41, "t0")]

    # A tiny per-order cap forces a rejection, which logs a risk event.
    Engine(client, RiskManager(settings.risk, store), store, ExampleStrategy(), settings).tick()

    for ev in store.recent_events(100):
        assert SECRET not in ev.message
        assert "shh" not in ev.message
    for o in store.recent_orders(100):
        assert SECRET not in (o.reason or "")
