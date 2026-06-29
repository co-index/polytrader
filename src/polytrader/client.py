"""PolymarketClient — the ONLY module that touches py_clob_client (Constitution V).

The SDK is imported lazily inside helpers, never at module top, so the rest of the
package (and the test suite) never depends on it. Tests inject a fake `clob`; the real
client is built only when none is injected. Order placement/cancel are reached solely
for risk-approved intents in live mode (the engine enforces that).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .config import Settings
from .strategy.base import MarketState, OrderIntent

# Transient errors worth retrying (rate limits, brief network blips). We match on the
# message because the SDK surfaces these as generic exceptions.
_RETRYABLE = ("429", "rate limit", "timeout", "temporarily", "503", "502")


@dataclass
class PlacedOrder:
    client_order_id: str
    raw: object = None


@dataclass
class AccountPosition:
    market_id: str
    token_id: str
    size: float
    avg_cost: float


class PolymarketClient:
    def __init__(
        self,
        settings: Settings,
        clob=None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ):
        self.settings = settings
        self._sleep = sleep
        self.max_retries = max_retries
        # Dependency injection: tests pass a fake; production builds the real SDK client.
        self._clob = clob if clob is not None else self._build_clob(settings)

    @staticmethod
    def _build_clob(settings: Settings):
        # Lazy import: keeps py_clob_client out of module-load for everyone else.
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds

        s = settings.secrets
        creds = None
        if s.clob_api_key:
            creds = ApiCreds(
                api_key=s.clob_api_key,
                api_secret=s.clob_api_secret,
                api_passphrase=s.clob_api_passphrase,
            )
        return ClobClient(
            s.clob_host,
            chain_id=s.chain_id,
            key=s.wallet_private_key or None,
            creds=creds,
        )

    def _with_retry(self, fn, *args, **kwargs):
        last = None
        for attempt in range(self.max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as e:  # noqa: BLE001 - SDK raises generic exceptions
                msg = str(e).lower()
                if not any(tok in msg for tok in _RETRYABLE) or attempt == self.max_retries - 1:
                    raise
                last = e
                self._sleep(2**attempt)  # exponential backoff: 1s, 2s, 4s, ...
        raise last  # pragma: no cover

    # ---- market data ----
    def market_state(self, market_id: str, token_id: str, question: str = "") -> MarketState:
        book = self._with_retry(self._clob.get_order_book, token_id)
        best_bid = max((float(b.price) for b in (book.bids or [])), default=0.0)
        best_ask = min((float(a.price) for a in (book.asks or [])), default=0.0)
        midpoint = round((best_bid + best_ask) / 2, 6) if best_bid and best_ask else 0.0
        return MarketState(
            market_id=market_id,
            token_id=token_id,
            question=question,
            best_bid=best_bid,
            best_ask=best_ask,
            midpoint=midpoint,
            timestamp=getattr(book, "timestamp", ""),
        )

    # ---- trading (live only) ----
    def place_order(self, intent: OrderIntent) -> PlacedOrder:
        from py_clob_client.clob_types import OrderArgs

        args = OrderArgs(
            token_id=intent.token_id,
            price=intent.price,
            size=intent.size,
            side=intent.side,
        )
        resp = self._with_retry(self._clob.create_and_post_order, args)
        order_id = resp.get("orderID") if isinstance(resp, dict) else getattr(resp, "orderID", "")
        return PlacedOrder(client_order_id=order_id or "", raw=resp)

    def cancel_order(self, client_order_id: str) -> None:
        self._with_retry(self._clob.cancel, client_order_id)

    def cancel_all(self) -> None:
        self._with_retry(self._clob.cancel_all)

    # ---- account ----
    def get_balance(self) -> float:
        resp = self._with_retry(self._clob.get_balance_allowance)
        if isinstance(resp, dict):
            return float(resp.get("balance", 0) or 0)
        return float(getattr(resp, "balance", 0) or 0)
