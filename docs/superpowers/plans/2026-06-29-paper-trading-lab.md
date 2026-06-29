# Paper Trading Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run 5 strategies side by side against live Polymarket data in a realistic
simulation and compare them on a dashboard leaderboard.

**Architecture:** A separate `paper/` subsystem — pure fill model, one `PaperBroker`
per strategy (reuses `RiskManager` via duck typing), a `PaperRunner` tick loop feeding
one shared snapshot to all strategies, a `PaperStore` for cross-process reads, and a
bilingual dashboard leaderboard tab. The audited live engine/store are untouched.

**Tech Stack:** Python 3.11, pydantic, sqlite3, Streamlit, pytest, ruff.

## Global Constraints

- Constitution II: every order intent passes `RiskManager.check()` — no bypass.
- Constitution V: strategies are pure logic; only `PolymarketClient` touches the SDK.
- Strategies use only top-of-book (`best_bid/best_ask/midpoint`) + internal state.
- Tests run via: `PYTHONPATH=src /Users/index/project/polytrader/.venv/bin/python -m pytest`.
- Lint: `/Users/index/project/polytrader/.venv/bin/python -m ruff check src tests`.
- Fill rule: BUY fills iff `best_ask>0 and P>=best_ask`; SELL iff `best_bid>0 and P<=best_bid`; fill price = limit P.

---

### Task 1: Fill model (pure)

**Files:** Create `src/polytrader/paper/__init__.py`, `src/polytrader/paper/fills.py`;
Test `tests/unit/test_paper_fills.py`.

**Produces:** `PaperFill(token_id, market_id, side, size, price)` dataclass;
`try_fill(intent: OrderIntent, market: MarketState) -> PaperFill | None`.

- [ ] Tests: BUY P>=ask fills at P; BUY P<ask no fill; SELL P<=bid fills at P; SELL P>bid no fill; best_ask==0 → BUY no fill; best_bid==0 → SELL no fill.
- [ ] Implement `try_fill` per the fill rule; fill price = intent.price.
- [ ] Run, green, commit.

### Task 2: PaperBroker

**Files:** Create `src/polytrader/paper/broker.py`; Test `tests/unit/test_paper_broker.py`.

**Consumes:** `try_fill`; `Position`, `PnL` from store; `OrderIntent`, `MarketState`.
**Produces:** `PaperBroker(name, bankroll=1000.0)` with:
- `execute(intent, market) -> PaperFill | None` (gate already passed upstream; applies fill, updates cash/position/realized)
- `mark_to_market(markets: list[MarketState]) -> None`
- `positions() -> list[Position]` and `pnl_today() -> PnL` (so `RiskManager` accepts it)
- `summary() -> dict` with keys: name, equity, total_pnl, realized, unrealized, fills, positions, wins, trades, rejects
- `note_reject() -> None` (increments reject count)

- [ ] Tests: BUY sets position size & avg_cost, cash decreases; second BUY averages cost; SELL reduces and books realized `(price-avg_cost)*qty`; `mark_to_market` sets unrealized `(mid-avg_cost)*size`; `equity == cash + Σ size*mid`; `positions()`/`pnl_today()` return correct types; a closed profitable round-trip counts a win.
- [ ] Test RiskManager interop: `RiskManager(RiskConfig(...), broker).check(intent)` approves/rejects using broker positions.
- [ ] Implement broker. Realized P&L recorded internally; `pnl_today()` returns `PnL(realized, unrealized)`.
- [ ] Run, green, commit.

### Task 3: Market-making strategy

**Files:** Create `src/polytrader/strategy/market_making.py`; Test `tests/unit/test_market_making.py`.

**Produces:** `MarketMakingStrategy(size=1.0, half_spread=0.02)` with `name="market_making"`,
quotes BUY at `round(mid - half_spread, 3)` and SELL at `round(mid + half_spread, 3)` for
each market with `0 < mid < 1`; skips legs where a computed price would be `<=0` or `>=1`.

- [ ] Tests: returns one BUY + one SELL per valid market at the right prices; is a `Strategy`; skips market with mid==0; clamps so prices stay in (0,1).
- [ ] Implement.
- [ ] Run, green, commit.

### Task 4: Mean-reversion strategy

**Files:** Create `src/polytrader/strategy/mean_reversion.py`; Test `tests/unit/test_mean_reversion.py`.

**Produces:** `MeanReversionStrategy(size=1.0, window=20, threshold=0.03)` with
`name="mean_reversion"`, keeps a per-token deque of midpoints; once window full, if
`mid <= mean - threshold` emit BUY at best_ask (marketable), if `mid >= mean + threshold`
emit SELL at best_bid; else nothing. No trade before window fills.

- [ ] Tests: no trade while warming up; BUY when price dips below mean−threshold; SELL when above; nothing inside band; is a `Strategy`.
- [ ] Implement (use `collections.deque(maxlen=window)` per token).
- [ ] Run, green, commit.

### Task 5: Momentum strategy

**Files:** Create `src/polytrader/strategy/momentum.py`; Test `tests/unit/test_momentum.py`.

**Produces:** `MomentumStrategy(size=1.0, window=20, threshold=0.03)` with
`name="momentum"`, per-token deque; once full, if `mid >= oldest + threshold` (uptrend)
emit BUY at best_ask; if `mid <= oldest - threshold` (downtrend) emit SELL at best_bid.

- [ ] Tests: no trade warming up; BUY on uptrend; SELL on downtrend; flat → nothing; is a `Strategy`.
- [ ] Implement.
- [ ] Run, green, commit.

### Task 6: PaperStore

**Files:** Create `src/polytrader/paper/store.py`; Test `tests/unit/test_paper_store.py`.

**Produces:** `PaperStore(db_path)` with `init_schema()`,
`write_leaderboard(rows: list[dict], ts: str)` (replaces the latest snapshot),
`leaderboard() -> list[dict]` (latest snapshot, sorted by total_pnl desc).
Table `paper_leaderboard(ts, name, equity, total_pnl, realized, unrealized, fills, positions, wins, trades, rejects)`.

- [ ] Tests: write then read returns the rows sorted by total_pnl desc; a second write replaces (not appends) the snapshot.
- [ ] Implement (delete-then-insert per write; `:memory:` supported).
- [ ] Run, green, commit.

### Task 7: PaperRunner

**Files:** Create `src/polytrader/paper/runner.py`; Test `tests/integration/test_paper_runner.py`.

**Consumes:** `PaperBroker`, `PaperStore`, `RiskManager`, `Strategy`, client with `get_markets()`.
**Produces:** `PaperRunner(client, store, entries, tick_ts=_now)` where `entries` is a list of
`(strategy, broker, risk)`; `tick()` does the §2 data flow; `run()` loops with sleep.

- [ ] Test (integration): fake client returns a fixed snapshot; two strategies (e.g. market_making + example) with their own brokers/risk; after `tick()`, each broker evolved independently and `store.leaderboard()` has one row per strategy. A strategy that raises in on_tick is isolated (logged, others still run). A rejected intent increments that broker's reject count.
- [ ] Implement; isolate per-strategy exceptions; drop non-`OrderIntent` items.
- [ ] Run, green, commit.

### Task 8: Dashboard leaderboard tab + i18n

**Files:** Modify `src/polytrader/dashboard.py`, `src/polytrader/i18n.py`;
Modify `tests/integration/test_dashboard_smoke.py`.

**Produces:** A leaderboard section/tab reading `PaperStore` (path from
`POLYTRADER_PAPER_DB`, default `data/paper.db`), shown as a dataframe sorted by total
P&L; bilingual column header via new i18n keys (`leaderboard`, `strategy_col`, `equity`,
`total_pnl`, `realized`, `unrealized`, `fills`, `win_rate`, `rejects`).

- [ ] Test: seed a PaperStore, set env, render → leaderboard header (EN) present; switch to 中文 → Chinese leaderboard header present.
- [ ] Implement; keep existing English-default behavior; empty store → caption "No paper results yet." (i18n key `no_paper`).
- [ ] Run, green, commit.

### Task 9: Runner entry point + manual run

**Files:** Modify `src/polytrader/paper/runner.py` (add `main()`); update `README` note.

**Produces:** `python -m polytrader.paper.runner` builds the 5 strategies + brokers +
risk from `config.yaml`, uses real `PolymarketClient`, loops writing to `data/paper.db`.

- [ ] Wire `main()` (pragma: no cover): build client, the 5 strategies, one broker+risk each, PaperStore, PaperRunner; run.
- [ ] Full suite + ruff green; commit.

---

## Self-Review

- **Spec coverage:** fills (T1), broker+RiskManager interop+accounting (T2), 3 new strategies (T3-5), PaperStore (T6), runner+data flow+error isolation (T7), leaderboard+i18n (T8), entry point (T9). Controls (complementary-arb, example) reused in T7/T9. ✓
- **Placeholders:** none. **Types:** `summary()` dict keys match the leaderboard columns and PaperStore schema; `try_fill`/`PaperFill` consistent across T1/T2/T7. ✓
