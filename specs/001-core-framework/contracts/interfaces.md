# Phase 1 Contracts: Internal Interfaces

These are the framework's internal contracts — the boundaries the constitution requires
(single SDK chokepoint, pluggable strategy, mandatory risk gate). They are Python
interfaces, not network APIs. Signatures are the stable surface; bodies belong to tasks.

## Strategy contract (`strategy/base.py`)

The pluggable unit. A strategy receives market state and returns proposed intents. It
MUST NOT import `py_clob_client` or touch the store/engine directly.

```python
class Strategy(Protocol):
    name: str

    def on_tick(self, markets: list[MarketState], context: StrategyContext) -> list[OrderIntent]:
        """Return zero or more proposed orders for this tick. Pure: no side effects,
        no I/O, no SDK calls. Raising is isolated by the engine."""
```

- `StrategyContext` exposes read-only current positions and remaining risk budget so a
  strategy can self-limit, but cannot mutate limits (FR-014).
- Bundled `example.py` implements `Strategy` trivially (e.g. quote a tiny resting order
  or no-op) to prove the pipeline end to end (FR-013).

## Risk gate contract (`risk.py`)

Every intent passes here before placement. No bypass path exists (Constitution II).

```python
class RiskManager:
    def __init__(self, config: RiskConfig, store: Store): ...

    def check(self, intent: OrderIntent) -> Decision:
        """Approve or reject one intent against ALL limits:
        per-order cap, total exposure cap, market whitelist.
        Returns Decision(approved, reason)."""

    def daily_loss_breached(self) -> bool:
        """True when today's realized loss >= daily_loss_limit_usd. Engine stops when True."""
```

- Rejection MUST set a specific `reason` naming the rule that fired.
- `check` reads current exposure/positions from the store; it never places orders.

## Exchange client contract (`client.py`) — sole SDK chokepoint

The ONLY module importing `py_clob_client` (Constitution V). Exposes a thin, mockable
interface so tests never touch the network.

```python
class PolymarketClient:
    def __init__(self, settings: Settings): ...

    # market data
    def get_markets(self, whitelist: list[str]) -> list[MarketState]: ...
    # trading (live only; engine calls these solely for risk-approved intents in live mode)
    def place_order(self, intent: OrderIntent) -> PlacedOrder: ...
    def cancel_order(self, client_order_id: str) -> None: ...
    def cancel_all(self) -> None: ...
    # account
    def get_positions(self) -> list[Position]: ...
    def get_balance(self) -> float: ...
```

- Applies rate-limit throttling/backoff (~60/min) and surfaces failures as typed errors
  the engine records (FR-012).
- Read methods may be used in dry-run; placement/cancel are reached only in live mode.

## Store contract (`store.py`)

Persistence + the engine/dashboard control channel. Both processes use this; no shared
in-memory state (Constitution V).

```python
class Store:
    def __init__(self, db_path: str): ...
    def init_schema(self) -> None: ...

    # writes
    def record_order(self, order) -> int: ...
    def record_fill(self, fill) -> None: ...
    def upsert_position(self, position) -> None: ...
    def log_event(self, level: str, category: str, message: str) -> None: ...

    # control / state (engine_state row)
    def get_engine_state(self) -> EngineState: ...
    def set_command(self, *, run=None, mode=None, kill=None) -> None: ...
    def set_status(self, *, last_tick_ts=None, stopped_reason=None) -> None: ...

    # reads for dashboard
    def recent_orders(self, n: int) -> list: ...
    def positions(self) -> list: ...
    def pnl_today(self) -> PnL: ...
    def recent_events(self, n: int) -> list: ...
```

## Engine control contract (`engine.py`)

```python
class Engine:
    def __init__(self, client, risk, store, strategy, settings): ...
    def run(self) -> None:
        """Loop: read engine_state command; if kill -> cancel_all + stop; if not run -> idle;
        else fetch markets -> strategy.on_tick -> for each intent risk.check ->
        if approved: place (live) or simulate (dry_run) -> record. After loop body,
        if risk.daily_loss_breached(): set stop + stopped_reason."""
```

## Contract tests (inform `/speckit-tasks`)

- Strategy: a fake strategy returning a known intent → engine produces a recorded order.
- Risk gate: over-cap / over-exposure / non-whitelisted / daily-loss intents → rejected
  with correct reason; in-limit intent → approved. (Exhaustive — Constitution IV.)
- Client: mocked; verify engine never calls `place_order` in dry-run and only for
  approved intents in live.
- Store: schema round-trips; `set_command`/`get_engine_state` reflect control writes.
