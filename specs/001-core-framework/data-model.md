# Phase 1 Data Model: Core Trading Framework

Types live in `strategy/base.py` (in-memory dataclasses passed across modules) and in
SQLite tables (persistence via `store.py`). Money values are USDC; sizes are share
counts; prices are probabilities in `[0, 1]`.

## In-memory types (dataclasses / pydantic)

### MarketState
Snapshot handed to a strategy each tick.
- `market_id: str` — Polymarket condition/market id
- `token_id: str` — outcome token being priced
- `question: str` — human-readable market question
- `best_bid: float` / `best_ask: float` — top of book (probability 0–1)
- `midpoint: float`
- `timestamp: datetime`
- (optional) `order_book: list[(price, size)]` per side

### OrderIntent
A strategy's proposed action, **before** risk evaluation.
- `market_id: str`
- `token_id: str`
- `side: Literal["BUY", "SELL"]`
- `size: float` — shares
- `price: float` — limit price (0–1)
- Validation: `size > 0`, `0 < price < 1`, side in {BUY, SELL}.

### Decision
Result of `RiskManager.check(intent, context)`.
- `approved: bool`
- `reason: str | None` — required when `approved is False` (which limit/rule fired)
- `intent: OrderIntent` — echoed for traceability

### RiskConfig
- `per_order_max_usd: float` (default 5)
- `total_exposure_max_usd: float` (default 50)
- `daily_loss_limit_usd: float` (default 20)
- `market_whitelist: list[str]` — allowed `market_id`s
- Invariants: all limits `> 0`; whitelist non-empty before live mode.

## Persisted entities (SQLite tables)

### orders
- `id` INTEGER PK
- `ts` TEXT (ISO8601)
- `market_id` TEXT, `token_id` TEXT
- `side` TEXT, `size` REAL, `price` REAL
- `mode` TEXT — `dry_run` | `live`
- `status` TEXT — `pending` | `placed` | `cancelled` | `filled` | `rejected`
- `reason` TEXT — populated when `rejected`
- `client_order_id` TEXT NULL — exchange order id when placed live

State transitions:
`pending → placed → (filled | cancelled)`; `pending → rejected` (risk gate);
dry-run orders go `pending → placed → filled` simulated, never hit the exchange.

### fills
- `id` PK, `order_id` FK→orders.id
- `ts`, `size` REAL, `price` REAL, `mode`
- Drives position + realized P&L.

### positions
Latest snapshot per market/token (upsert).
- `market_id`, `token_id` (composite key)
- `size` REAL (signed), `avg_cost` REAL, `ts`

### pnl
- `day` TEXT (date), `realized_usd` REAL, `unrealized_usd` REAL, `ts`
- The `realized_usd` for the current day feeds the circuit breaker.

### engine_state
Single-row control + status table (id = 1).
- `run` INTEGER (0/1), `mode` TEXT (`dry_run`|`live`), `kill` INTEGER (0/1)
- `last_tick_ts` TEXT, `stopped_reason` TEXT NULL (e.g. "daily-loss circuit breaker")
- Written by dashboard (commands) and engine (status); read by both.

### events
Append-only structured log.
- `id` PK, `ts`, `level` TEXT (`info`|`warn`|`error`), `category` TEXT, `message` TEXT
- Never stores secrets.

## Relationships

```
RiskConfig ──governs──> RiskManager ──gates──> OrderIntent ──approved──> orders
orders ──1:N──> fills ──aggregate──> positions ──value──> pnl ──feeds──> circuit breaker
engine_state <──read/write──> {engine, dashboard}
* ──append──> events
```
