# Paper Trading Lab — Design

**Date:** 2026-06-29
**Status:** Approved (design)
**Feature:** Run several strategies side by side against live Polymarket data in a
realistic simulation, compare them on a dashboard leaderboard, then promote the
winner to live trading.

## Goal & Motivation

The operator wants to run several strategies at once, simulate them fairly first,
and only fund the winner with real money. Two facts shaped this design:

1. The live read path (`PolymarketClient.market_state`) is verified against real
   Polymarket data — top-of-book `best_bid/best_ask/midpoint` per outcome token.
2. The engine's current dry-run fills every order instantly at its own price. That
   is far too optimistic for passive (market-making) strategies and would make every
   strategy look profitable — useless for comparison.

So we build a **separate Paper Lab subsystem** with a realistic fill model and one
isolated simulated account per strategy. The audited live engine/store are left
untouched: the live path stays sacred, the lab is for fair comparison.

## Non-Goals (YAGNI)

- No live order placement (the existing live `Engine` already owns that path).
- No historical backtest (no historical data available; forward paper-trading only).
- No partial fills, queue position, or intra-tick price-path modeling.
- No cross-process runner persistence/recovery — restarting the runner resets paper
  accounts. Documented, acceptable for v1.

## Architecture

New package `src/polytrader/paper/`:

| Module | Responsibility |
|---|---|
| `fills.py` | Pure fill model: `try_fill(intent, market) -> Fill \| None`. No state. |
| `broker.py` | `PaperBroker` — one strategy's simulated account (cash, positions, realized P&L, fills). Exposes `positions()` + `pnl_today()` so `RiskManager` works on it unchanged. |
| `runner.py` | `PaperRunner` — owns N `(strategy, broker, risk)` triples + one client + one `PaperStore`. Drives the tick loop. |
| `store.py` | `PaperStore` — new, paper-only SQLite for the dashboard to read cross-process. Does NOT touch the audited `Store`. |

**Reused unchanged:** `Strategy` protocol and all 5 strategies; `OrderIntent`,
`MarketState`, `Position`, `PnL`; `RiskManager` (via duck typing — it only calls
`store.positions()` and `store.pnl_today()`); `PolymarketClient` read path.

### Why RiskManager reuse is clean

`RiskManager.__init__(config, store)` and only ever calls `store.positions()` and
`store.pnl_today()`. `PaperBroker` implements both with the same return types, so
`RiskManager(config, broker)` works with zero changes — every paper intent still
passes the risk gate (Constitution II honored in the lab too).

## Data Flow (one tick)

1. `runner` calls `client.get_markets()` **once** — one real snapshot shared by all
   strategies (saves rate-limit budget).
2. For each strategy:
   a. Build `StrategyContext` from that strategy's broker (positions, remaining
      exposure) → `strategy.on_tick(snapshot, ctx)`.
   b. Each intent → that strategy's `risk.check()` (Constitution II). Rejections are
      counted with their reason.
   c. Approved intents → `broker.execute(intent, market)` → the fill model decides
      whether it fills this tick.
   d. `broker.mark_to_market(snapshot)` updates unrealized P&L.
3. `runner` writes one `summary()` row per strategy into `PaperStore` (leaderboard
   snapshot).
4. `sleep(tick_interval)`; loop.

Strategy internal state (mean-reversion / momentum rolling windows) lives in each
strategy instance; account state lives in each broker.

## Fill Model (the core — determines comparison fairness)

Each tick, the strategy re-states its desired orders (that is what `on_tick` returns),
and we match those **current** intents against the **current** snapshot. A "resting"
quote is simply one that did not fill this tick and is re-evaluated next tick — so no
separate multi-tick resting book is needed.

Rules (in `fills.try_fill`):

- **BUY @ P:** fills iff `best_ask > 0` and `P >= best_ask`; else no fill.
- **SELL @ P:** fills iff `best_bid > 0` and `P <= best_bid`; else no fill.
- **Fill price = the intent's limit price P** (single rule; conservative for a taker,
  accurate for a maker who got hit at their quote).

Consequence: when price moves across a quote between ticks, the passive order fills —
so a market maker captures the spread in an oscillating market. Unbounded accumulation
is prevented by the per-strategy exposure cap in the risk gate.

**Explicit simplifications (documented):** top-of-book only; assumes top size is
sufficient (no partial fills); no queue position; no intra-tick path. Good enough for
a fair *relative* comparison, not real-fill accuracy.

## Accounting & P&L

- Starting `bankroll` (default $1000 paper, configurable).
- BUY: `cash -= size*price`, update position avg_cost. SELL: `cash += size*price`.
- **Realized P&L:** on closing/reducing a position, `(fill_price - avg_cost) * reduced_size`.
  Recorded so `pnl_today()` feeds the daily-loss circuit breaker.
- **Unrealized P&L (mark-to-market):** per open position, `(midpoint - avg_cost) * size`.
- **Equity = cash + Σ(position_size * midpoint)**; total P&L = equity − initial bankroll.
- **Win rate:** share of closed round-trips with positive realized P&L.
- Note: binary tokens ultimately redeem at $1/$0; short-horizon comparison marks to
  midpoint. Documented.

## Strategies in the Comparison (5)

New (this feature), all using only top-of-book + internal state, all through the risk
gate and fill model:

1. **Market-making / spread capture** — quote BUY below mid and SELL above mid by a
   configurable half-spread; earns the spread when price oscillates.
2. **Mean reversion** — internal rolling window of midpoint; BUY when price dips a
   threshold below the mean, SELL when above.
3. **Momentum / trend** — same rolling window; BUY when the trend is up.

Existing, kept as controls:

4. **Complementary arbitrage** — already built; near-never fires (zero baseline).
5. **Example** — naive resting buy at best bid (control).

## Dashboard Leaderboard

A new bilingual tab (reusing the `i18n` table) on the existing Streamlit dashboard:
one row per strategy, sorted by **total P&L descending**:

`strategy | equity | total P&L | realized | unrealized | fills | positions | win rate | rejects`

Reads the latest `PaperStore` snapshot; remains usable when the runner is stopped
(reusing the store-decoupling pattern). New i18n keys added for the column headers.

## Error Handling

- A strategy that raises in `on_tick` is isolated (logged, skipped that tick) — same
  contract the live engine already enforces; the runner must not crash on one bad
  strategy.
- A failed market fetch logs and skips the tick (no fabricated data).
- Malformed intents (not `OrderIntent`) are dropped and counted, like the engine does.

## Testing (TDD, red-green per behavior)

- `fills`: BUY/SELL fill & no-fill boundaries, empty-book skip, fill price = P.
- `broker`: avg_cost on adds, realized P&L on close, unrealized MTM, equity,
  `positions()`/`pnl_today()` shapes accepted by `RiskManager`.
- Each of the 3 new strategies: unit tests (MM symmetric quotes; mean-reversion and
  momentum direction by window).
- `runner` integration: one fake snapshot fed to N strategies → independent account
  evolution, reject counting, leaderboard rows written.
- All tests run via the main checkout venv (worktree rule):
  `PYTHONPATH=src /Users/index/project/polytrader/.venv/bin/python -m pytest`.

## Open Risks / Follow-ups

- Fill realism is a relative-comparison tool, not a live-accuracy predictor. Before
  trusting a winner live, validate against real fills.
- Live promotion path (feed the winning strategy into the live `Engine`) is a separate
  later step, after the operator opens a funded account.
