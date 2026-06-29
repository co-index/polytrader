"""Unit tests for polytrader.client — the SOLE py_clob_client chokepoint.

The real SDK is never imported at module top (so the rest of the package and the test
suite don't depend on it). All tests inject a fake underlying clob client; none touch
the network.
"""

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from polytrader.client import PlacedOrder, PolymarketClient
from polytrader.config import Settings
from polytrader.strategy.base import OrderIntent

CLIENT_SRC = Path("src/polytrader/client.py").read_text()


def _settings():
    return Settings(
        risk=dict(
            per_order_max_usd=5,
            total_exposure_max_usd=50,
            daily_loss_limit_usd=20,
            market_whitelist=["m1"],
        )
    )


def _intent():
    return OrderIntent(market_id="m1", token_id="t1", side="BUY", size=2.0, price=0.4)


def test_sdk_is_not_imported_at_module_top():
    # py_clob_client may only be imported INSIDE functions, never at module scope,
    # so importing polytrader.client (or the rest of the package) never pulls the SDK.
    top_level = [
        ln for ln in CLIENT_SRC.splitlines()
        if re.match(r"^(import|from)\s+py_clob_client", ln)
    ]
    assert top_level == [], f"py_clob_client must not be imported at top level: {top_level}"


def test_place_order_calls_create_and_post_and_returns_id():
    clob = MagicMock()
    clob.create_and_post_order.return_value = {"orderID": "abc123", "success": True}
    client = PolymarketClient(_settings(), clob=clob)

    placed = client.place_order(_intent())

    assert isinstance(placed, PlacedOrder)
    assert placed.client_order_id == "abc123"
    assert clob.create_and_post_order.call_count == 1


def test_cancel_order_delegates():
    clob = MagicMock()
    client = PolymarketClient(_settings(), clob=clob)
    client.cancel_order("oid-1")
    clob.cancel.assert_called_once_with("oid-1")


def test_cancel_all_delegates():
    clob = MagicMock()
    client = PolymarketClient(_settings(), clob=clob)
    client.cancel_all()
    clob.cancel_all.assert_called_once()


def test_market_state_built_from_order_book():
    clob = MagicMock()
    clob.get_order_book.return_value = SimpleNamespace(
        market="m1",
        asset_id="t1",
        bids=[SimpleNamespace(price="0.39", size="10"), SimpleNamespace(price="0.40", size="5")],
        asks=[SimpleNamespace(price="0.43", size="7"), SimpleNamespace(price="0.42", size="3")],
        timestamp="2026-06-29T00:00:00",
    )
    client = PolymarketClient(_settings(), clob=clob)
    ms = client.market_state("m1", "t1", "Will it rain?")
    assert ms.best_bid == 0.40  # highest bid
    assert ms.best_ask == 0.42  # lowest ask
    assert ms.midpoint == 0.41


def test_place_order_retries_then_succeeds_on_transient_error():
    clob = MagicMock()
    clob.create_and_post_order.side_effect = [
        RuntimeError("429 rate limited"),
        {"orderID": "ok", "success": True},
    ]
    sleeps = []
    client = PolymarketClient(_settings(), clob=clob, sleep=sleeps.append, max_retries=3)

    placed = client.place_order(_intent())

    assert placed.client_order_id == "ok"
    assert clob.create_and_post_order.call_count == 2
    assert len(sleeps) == 1  # backed off once before the retry
