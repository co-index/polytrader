"""Integration: PaperRunner feeds one snapshot to N strategies, each isolated."""

from unittest.mock import MagicMock

from polytrader.config import RiskConfig
from polytrader.paper.broker import PaperBroker
from polytrader.paper.runner import PaperRunner
from polytrader.paper.store import PaperStore
from polytrader.risk import RiskManager
from polytrader.strategy.base import MarketState
from polytrader.strategy.example import ExampleStrategy
from polytrader.strategy.market_making import MarketMakingStrategy


def _snapshot():
    # Deliberately crossed top-of-book so marketable test orders fill this tick.
    return [MarketState("m1", "t1", "Q?", best_bid=0.45, best_ask=0.40, midpoint=0.425,
                        timestamp="2026-06-29T00:00:00")]


def _risk(whitelist=("m1",)):
    return RiskConfig(per_order_max_usd=100, total_exposure_max_usd=1000,
                      daily_loss_limit_usd=100, market_whitelist=list(whitelist))


def _entry(strategy, whitelist=("m1",), bankroll=1000.0):
    broker = PaperBroker(strategy.name, bankroll=bankroll)
    return (strategy, broker, RiskManager(_risk(whitelist), broker))


def _runner(entries):
    client = MagicMock()
    client.get_markets.return_value = _snapshot()
    store = PaperStore(":memory:")
    store.init_schema()
    return PaperRunner(client, store, entries, tick_ts=lambda: "t1"), store


def test_each_strategy_evolves_independently_and_writes_one_row():
    entries = [_entry(ExampleStrategy(size=1.0)), _entry(MarketMakingStrategy())]
    runner, store = _runner(entries)
    runner.tick()

    lb = {r["name"]: r for r in store.leaderboard()}
    assert set(lb) == {"example", "market_making"}
    # example: one marketable BUY filled; market_making: BUY+SELL both fill on crossed book.
    assert lb["example"]["fills"] == 1
    assert lb["market_making"]["fills"] == 2


def test_fills_are_persisted_as_per_strategy_orders():
    entries = [_entry(ExampleStrategy(size=1.0))]
    runner, store = _runner(entries)
    runner.tick()
    orders = store.orders("example")
    assert len(orders) == 1
    assert orders[0]["status"] == "filled"
    assert orders[0]["ts"] == "t1"  # the tick timestamp


def test_rejected_intents_are_counted_not_executed():
    entries = [_entry(ExampleStrategy(size=1.0), whitelist=())]  # nothing whitelisted
    runner, store = _runner(entries)
    runner.tick()
    row = store.leaderboard()[0]
    assert row["fills"] == 0
    assert row["rejects"] >= 1


def test_a_raising_strategy_is_isolated():
    class Bad:
        name = "bad"

        def on_tick(self, markets, context):
            raise RuntimeError("boom")

    entries = [_entry(Bad()), _entry(ExampleStrategy(size=1.0))]
    runner, store = _runner(entries)
    runner.tick()  # must not raise

    lb = {r["name"]: r for r in store.leaderboard()}
    assert set(lb) == {"bad", "example"}
    assert lb["bad"]["fills"] == 0
    assert lb["example"]["fills"] == 1  # the healthy strategy still ran
