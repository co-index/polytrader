"""Unit tests for the dashboard's pure helpers (no Streamlit runtime needed)."""

from datetime import UTC, datetime, timedelta

import pytest

pytest.importorskip("streamlit")
from polytrader.dashboard import _filter_orders, _heartbeat_ok, _localize_ts  # noqa: E402

ORDERS = [
    {"ts": "t1", "token_id": "alpha", "side": "BUY", "size": 5.0,
     "price": 0.40, "status": "filled"},
    {"ts": "t2", "token_id": "beta", "side": "SELL", "size": 5.0,
     "price": 0.55, "status": "filled"},
]


def test_empty_query_returns_all_orders():
    assert _filter_orders(ORDERS, "") == ORDERS
    assert _filter_orders(ORDERS, "   ") == ORDERS


def test_filter_matches_any_field_case_insensitively():
    assert [o["token_id"] for o in _filter_orders(ORDERS, "ALPHA")] == ["alpha"]
    assert [o["side"] for o in _filter_orders(ORDERS, "sell")] == ["SELL"]


def test_filter_matches_numeric_fields():
    assert [o["token_id"] for o in _filter_orders(ORDERS, "0.55")] == ["beta"]


def test_no_match_returns_empty():
    assert _filter_orders(ORDERS, "zzz") == []


_NOW = datetime(2026, 6, 30, 12, 0, 0, tzinfo=UTC)


def test_heartbeat_false_when_never_ticked():
    assert _heartbeat_ok(None, _NOW, 30) is False
    assert _heartbeat_ok("", _NOW, 30) is False


def test_heartbeat_true_when_recent():
    recent = (_NOW - timedelta(seconds=5)).isoformat()
    assert _heartbeat_ok(recent, _NOW, 30) is True


def test_heartbeat_false_when_stale():
    stale = (_NOW - timedelta(seconds=120)).isoformat()
    assert _heartbeat_ok(stale, _NOW, 30) is False


def test_heartbeat_false_on_unparseable_timestamp():
    assert _heartbeat_ok("not-a-time", _NOW, 30) is False


def test_localize_ts_converts_utc_to_browser_timezone():
    # 04:32 UTC -> 12:32 in Shanghai (UTC+8)
    assert _localize_ts("2026-06-30T04:32:00+00:00", "Asia/Shanghai") == "2026-06-30 12:32:00"


def test_localize_ts_assumes_utc_when_naive():
    assert _localize_ts("2026-06-30T04:32:00", "Asia/Shanghai") == "2026-06-30 12:32:00"


def test_localize_ts_falls_back_on_bad_input():
    assert _localize_ts("not-a-time", "Asia/Shanghai") == "not-a-time"
    # Unknown tz -> render in UTC rather than crash.
    assert _localize_ts("2026-06-30T04:32:00+00:00", "Bogus/Zone") == "2026-06-30 04:32:00"
    assert _localize_ts("2026-06-30T04:32:00+00:00", None) == "2026-06-30 04:32:00"
