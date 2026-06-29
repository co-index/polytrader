"""Integration: the engine runs the complementary-arb strategy end to end in dry-run.

Proves the wiring data -> strategy -> risk gate -> simulate -> record works for a real
strategy (not just the example): an underpriced pair produces two simulated BUY fills,
one per leg, with no real order ever placed.
"""

from unittest.mock import MagicMock

from polytrader.config import RiskConfig, Settings
from polytrader.engine import Engine
from polytrader.risk import RiskManager
from polytrader.store import Store
from polytrader.strategy.base import MarketState
from polytrader.strategy.complementary_arb import ComplementaryArbStrategy


def _settings():
    return Settings(
        risk=RiskConfig(
            per_order_max_usd=5,
            total_exposure_max_usd=50,
            daily_loss_limit_usd=20,
            market_whitelist=["m1"],
        )
    )


def _leg(token_id: str, best_ask: float) -> MarketState:
    return MarketState("m1", token_id, "Q?", best_bid=best_ask - 0.02, best_ask=best_ask,
                       midpoint=best_ask, timestamp="2026-06-29T00:00:00")


def test_engine_executes_arb_pair_in_dry_run():
    settings = _settings()
    store = Store(":memory:")
    store.init_schema()
    store.set_command(run=True, mode="dry_run")

    client = MagicMock()
    # YES 0.40 + NO 0.55 = 0.95 -> 0.05 locked-in edge.
    client.get_markets.return_value = [_leg("yes", 0.40), _leg("no", 0.55)]

    engine = Engine(client, RiskManager(settings.risk, store), store,
                    ComplementaryArbStrategy(size=1.0, min_edge=0.01), settings)
    engine.tick()

    client.place_order.assert_not_called()  # dry-run never hits the exchange
    orders = store.recent_orders(10)
    assert len(orders) == 2
    assert {o.token_id for o in orders} == {"yes", "no"}
    assert all(o.status in ("placed", "filled") and o.mode == "dry_run" for o in orders)
    # Both legs now held.
    assert {p.token_id for p in store.positions()} == {"yes", "no"}
