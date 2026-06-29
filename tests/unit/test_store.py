"""Unit tests for polytrader.store — SQLite persistence + engine control channel."""

from polytrader.store import Order, Position, Store


def _store(tmp_path) -> Store:
    s = Store(str(tmp_path / "t.db"))
    s.init_schema()
    return s


def test_fresh_engine_state_is_stopped_dry_run(tmp_path):
    s = _store(tmp_path)
    state = s.get_engine_state()
    assert state.run is False
    assert state.mode == "dry_run"
    assert state.kill is False


def test_record_order_roundtrip(tmp_path):
    s = _store(tmp_path)
    oid = s.record_order(
        Order(
            ts="2026-06-29T00:00:00",
            market_id="m1",
            token_id="t1",
            side="BUY",
            size=2.0,
            price=0.4,
            mode="dry_run",
            status="placed",
        )
    )
    assert isinstance(oid, int)
    orders = s.recent_orders(10)
    assert len(orders) == 1
    assert orders[0].market_id == "m1"
    assert orders[0].status == "placed"


def test_set_command_updates_only_given_fields(tmp_path):
    s = _store(tmp_path)
    s.set_command(run=True, mode="live")
    state = s.get_engine_state()
    assert state.run is True
    assert state.mode == "live"
    assert state.kill is False  # untouched

    s.set_command(kill=True)
    state = s.get_engine_state()
    assert state.kill is True
    assert state.run is True  # untouched


def test_log_event_and_recent_events(tmp_path):
    s = _store(tmp_path)
    s.log_event("error", "engine", "boom")
    events = s.recent_events(10)
    assert len(events) == 1
    assert events[0].level == "error"
    assert events[0].message == "boom"


def test_upsert_position_replaces(tmp_path):
    s = _store(tmp_path)
    s.upsert_position(Position(market_id="m1", token_id="t1", size=1.0, avg_cost=0.4, ts="t0"))
    s.upsert_position(Position(market_id="m1", token_id="t1", size=3.0, avg_cost=0.5, ts="t1"))
    positions = s.positions()
    assert len(positions) == 1
    assert positions[0].size == 3.0
    assert positions[0].avg_cost == 0.5
