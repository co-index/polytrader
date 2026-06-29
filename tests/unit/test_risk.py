"""Exhaustive unit tests for the risk gate — every limit and every rejection path.

Constitution IV: the risk gate is the component that protects funds; it must be the
most thoroughly tested. Tests use a real in-memory Store (no mocks).
"""

from datetime import date

import pytest

from polytrader.config import RiskConfig
from polytrader.risk import RiskManager
from polytrader.store import Position, Store
from polytrader.strategy.base import OrderIntent


@pytest.fixture
def store():
    s = Store(":memory:")
    s.init_schema()
    return s


def _risk(store, **overrides):
    cfg = RiskConfig(
        per_order_max_usd=overrides.get("per_order_max_usd", 5.0),
        total_exposure_max_usd=overrides.get("total_exposure_max_usd", 50.0),
        daily_loss_limit_usd=overrides.get("daily_loss_limit_usd", 20.0),
        market_whitelist=overrides.get("market_whitelist", ["m1"]),
    )
    return RiskManager(cfg, store)


def _today():
    return date.today().isoformat()


def _intent(market_id="m1", size=1.0, price=0.4, side="BUY"):
    return OrderIntent(market_id=market_id, token_id="t1", side=side, size=size, price=price)


def test_approves_within_all_limits(store):
    rm = _risk(store)
    d = rm.check(_intent(size=2, price=0.4))  # notional 0.8
    assert d.approved is True
    assert d.reason is None


def test_rejects_over_per_order_cap(store):
    rm = _risk(store, per_order_max_usd=5.0)
    d = rm.check(_intent(size=20, price=0.5))  # notional 10 > 5
    assert d.approved is False
    assert "per-order" in d.reason.lower()


def test_rejects_non_whitelisted_market(store):
    rm = _risk(store, market_whitelist=["m1"])
    d = rm.check(_intent(market_id="m_other", size=1, price=0.4))
    assert d.approved is False
    assert "whitelist" in d.reason.lower()


def test_rejects_when_total_exposure_would_be_exceeded(store):
    # Existing exposure 45 (size 100 * avg_cost 0.45); cap 50; new notional 10 -> 55 > 50.
    store.upsert_position(Position("m1", "t1", size=100.0, avg_cost=0.45, ts="t0"))
    rm = _risk(store, per_order_max_usd=100.0, total_exposure_max_usd=50.0)
    d = rm.check(_intent(size=20, price=0.5))  # notional 10
    assert d.approved is False
    assert "exposure" in d.reason.lower()


def test_approves_when_exposure_stays_under_cap(store):
    store.upsert_position(Position("m1", "t1", size=100.0, avg_cost=0.45, ts="t0"))  # 45
    rm = _risk(store, per_order_max_usd=100.0, total_exposure_max_usd=50.0)
    d = rm.check(_intent(size=6, price=0.5))  # notional 3 -> 48 <= 50
    assert d.approved is True


def test_per_order_cap_checked_before_exposure(store):
    # An order over BOTH caps should report the per-order reason (checked first).
    rm = _risk(store, per_order_max_usd=5.0, total_exposure_max_usd=50.0)
    d = rm.check(_intent(size=200, price=0.5))
    assert d.approved is False
    assert "per-order" in d.reason.lower()


def test_daily_loss_not_breached_when_under_limit(store):
    rm = _risk(store, daily_loss_limit_usd=20.0)
    store.record_realized_pnl(_today(), -10.0)
    assert rm.daily_loss_breached() is False


def test_daily_loss_breached_when_loss_reaches_limit(store):
    rm = _risk(store, daily_loss_limit_usd=20.0)
    store.record_realized_pnl(_today(), -15.0)
    store.record_realized_pnl(_today(), -6.0)  # total -21 <= -20
    assert rm.daily_loss_breached() is True
