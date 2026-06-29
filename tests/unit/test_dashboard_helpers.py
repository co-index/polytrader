"""Unit tests for the dashboard's pure helpers (no Streamlit runtime needed)."""

import pytest

pytest.importorskip("streamlit")
from polytrader.dashboard import _filter_orders  # noqa: E402

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
