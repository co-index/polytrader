---
description: "Task list for Core Trading Framework implementation"
---

# Tasks: Core Trading Framework

**Input**: Design documents from `specs/001-core-framework/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/interfaces.md

**Tests**: INCLUDED and test-first — Constitution IV (Test-First, Risk-Critical Coverage)
makes this mandatory, not optional. The risk gate must be exhaustively tested before live
mode is trusted; the client is mocked in every test.

**Organization**: By user story. The risk gate's *caps* (per-order, exposure, whitelist)
are Foundational because Constitution II forbids any order path that bypasses the gate, so
US1 cannot exist without it. US3 adds the autonomous daily-loss circuit breaker.

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**: parallelizable (different files, no incomplete dependencies)
- **[Story]**: US1 / US2 / US3 (user-story phases only)

## Path Conventions

Single project: `src/polytrader/`, `tests/` at repo root (per plan.md).

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Create project structure (`src/polytrader/{__init__.py,strategy/__init__.py}`, `tests/unit/`, `tests/integration/`) per plan.md
- [ ] T002 Initialize packaging in `pyproject.toml`: runtime deps (py-clob-client, streamlit, pydantic, pyyaml) + dev deps (pytest, pytest-mock) + `[tool.pytest.ini_options]`
- [ ] T003 [P] Add `config.yaml.example` (risk limits, market_whitelist, tick_interval, default mode=dry_run) and `.env.example` (WALLET_PRIVATE_KEY, CLOB_API_KEY/SECRET/PASSPHRASE placeholders — no real secrets)
- [ ] T004 [P] Configure ruff lint/format in `pyproject.toml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: No user story work begins until this phase is complete. The risk gate and
its tests live here because no order may bypass it (Constitution II) and it must be tested
before any live path exists (Constitution IV).

- [ ] T005 [P] Write failing unit tests for config in `tests/unit/test_config.py` (secrets only from env, yaml limits parsed, validation errors on bad limits)
- [ ] T006 Implement `src/polytrader/config.py` (`Settings`, `RiskConfig` pydantic models; load `.env` + `config.yaml`) to pass T005
- [ ] T007 [P] Write failing unit tests for store in `tests/unit/test_store.py` (schema init, order/fill/position round-trip, `engine_state` command/status read-write, event log)
- [ ] T008 Implement `src/polytrader/store.py` (SQLite schema + record_order/record_fill/upsert_position/log_event, engine_state get/set_command/set_status, reads for dashboard) to pass T007
- [ ] T009 [P] Define strategy types in `src/polytrader/strategy/base.py` (`Strategy` Protocol, `OrderIntent`, `MarketState`, `Decision`, `StrategyContext` with validation)
- [ ] T010 [P] Write failing unit tests for strategy + example in `tests/unit/test_strategy.py` (OrderIntent validation, example returns valid intents, no SDK/IO access)
- [ ] T011 Implement `src/polytrader/strategy/example.py` bundled example strategy to pass T010
- [ ] T012 [P] Write exhaustive failing unit tests for the risk gate caps in `tests/unit/test_risk.py` (per-order cap reject, exposure cap reject, non-whitelisted reject with reason, in-limit approve) — Constitution IV
- [ ] T013 Implement `src/polytrader/risk.py` `RiskManager.check()` (per-order cap, total exposure cap, market whitelist; reads exposure from store; sets specific reason on reject) to pass T012
- [ ] T014 [P] Write failing tests in `tests/unit/test_client.py` (guard: only `client.py` imports `py_clob_client`; mocked-SDK tests for get_markets/place_order/cancel/cancel_all/get_positions/get_balance + rate-limit backoff)
- [ ] T015 Implement `src/polytrader/client.py` `PolymarketClient` — sole `py_clob_client` chokepoint, mockable interface, rate-limit throttling/backoff — to pass T014

**Checkpoint**: config, store, strategy base + example, risk gate (caps), and client are tested and ready.

---

## Phase 3: User Story 1 - Dry-run → live trading core (Priority: P1) 🎯 MVP

**Goal**: The engine runs a strategy end to end — fetch markets, propose orders, pass the
risk gate, simulate in dry-run or place in live — and records everything.

**Independent Test**: Plug in the example strategy, start in dry-run, confirm simulated
orders recorded with no `place_order` call; switch to live (tiny limits), confirm one real
(mocked) order placed.

### Tests for User Story 1 (write first, ensure they FAIL)

- [ ] T016 [P] [US1] Integration test in `tests/integration/test_dry_run_tick.py`: full dry-run tick (data→strategy→risk→simulate→record); assert `place_order` never called, simulated order+fill persisted
- [ ] T017 [P] [US1] Integration test in `tests/integration/test_live_tick.py`: live-mode tick places exactly the risk-approved order via mocked client; an over-limit intent is rejected and not placed

### Implementation for User Story 1

- [ ] T018 [US1] Implement `src/polytrader/engine.py` `Engine`: tick loop, default `mode=dry_run` on start, fetch markets via client, call `strategy.on_tick`, route every intent through `risk.check`, simulate (dry_run) vs `client.place_order` (live), record orders/fills, structured logging (depends on T006/T008/T013/T015)
- [ ] T019 [US1] Add strategy failure isolation in `engine.py` (catch strategy exceptions, drop malformed intents, log error, never crash the loop)
- [ ] T020 [US1] Add engine entry point `python -m polytrader.engine` in `src/polytrader/engine.py` wiring config→store→client→risk→strategy

**Checkpoint**: Trading core works in dry-run and live (mocked); MVP demonstrable.

---

## Phase 4: User Story 2 - Dashboard monitor + control (Priority: P1)

**Goal**: A Streamlit dashboard shows positions/P&L/orders/state and drives start/stop,
dry-run↔live, and the kill switch — reading and writing only the store.

**Independent Test**: With recorded data, dashboard renders state; Stop idles the engine;
Kill switch cancels all open orders; dashboard still renders with engine stopped.

### Tests for User Story 2 (write first, ensure they FAIL)

- [ ] T021 [P] [US2] Unit test in `tests/unit/test_controls.py`: dashboard `set_command` (run/stop, mode, kill) → engine reads and acts on commands (mocked client); kill triggers `cancel_all`

### Implementation for User Story 2

- [ ] T022 [P] [US2] Implement `src/polytrader/dashboard.py` Streamlit app: render positions, pnl_today, recent orders/fills, engine run-state + mode, recent events from store
- [ ] T023 [US2] Add dashboard controls in `src/polytrader/dashboard.py` writing commands via `store.set_command` (start/stop, dry_run↔live toggle, kill switch)
- [ ] T024 [US2] Implement engine command handling in `src/polytrader/engine.py`: each tick read `engine_state`; stop→idle, apply mode switch, kill→`client.cancel_all()` + stop with `stopped_reason` (depends on T018)

**Checkpoint**: Operator can monitor and control trading; dashboard survives engine being down (SC-007).

---

## Phase 5: User Story 3 - Automatic loss cap (Priority: P2)

**Goal**: The engine stops itself when the day's realized loss reaches the configured
threshold — no operator action needed.

**Independent Test**: With a low daily-loss limit, feed simulated losing fills until the
threshold is crossed; engine auto-stops within one tick with the breaker reason.

### Tests for User Story 3 (write first, ensure they FAIL)

- [ ] T025 [P] [US3] Add failing tests in `tests/unit/test_risk.py`: realized daily loss ≥ limit → `daily_loss_breached()` True; below → False
- [ ] T026 [P] [US3] Integration test in `tests/integration/test_circuit_breaker.py`: losing fills cross threshold → engine auto-stops within one tick, `stopped_reason="daily-loss circuit breaker"`

### Implementation for User Story 3

- [ ] T027 [US3] Implement realized-P&L-per-day tracking from fills in `src/polytrader/store.py` (`pnl_today`) and `src/polytrader/risk.py`
- [ ] T028 [US3] Implement `RiskManager.daily_loss_breached()` and engine auto-stop wiring in `src/polytrader/engine.py` (set stop + `stopped_reason` within one tick) to pass T025/T026

**Checkpoint**: All three stories independently functional; unattended small-money trading is loss-capped.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T029 [P] Write `README.md` (setup + run, derived from quickstart.md)
- [ ] T030 [P] Add secrets-leak guard test in `tests/unit/test_no_secrets.py` (no key patterns in event log output; `.env` is gitignored)
- [ ] T031 Run `quickstart.md` validation end-to-end (tests green, dry-run tick, dashboard render, kill switch, circuit breaker)
- [ ] T032 Final verification (superpowers verification-before-completion): `pytest -q` fully green and Constitution gates re-checked before any live use

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: after Setup. BLOCKS all user stories.
- **US1 (Phase 3)**: after Foundational. The MVP.
- **US2 (Phase 4)**: after Foundational; integrates with the engine from US1 (T024 depends on T018).
- **US3 (Phase 5)**: after US1 (needs fills/pnl from the trading core).
- **Polish (Phase 6)**: after the desired stories.

### Within Each Story

- Tests written FIRST and must FAIL before implementation (TDD, Constitution IV).
- config/store/strategy-base/risk/client (Foundational) before engine (US1).
- Engine (US1) before command-handling (US2 T024) and before circuit breaker (US3).

### Parallel Opportunities

- Setup: T003, T004 in parallel.
- Foundational: test-writing tasks T005/T007/T010/T012/T014 in parallel; T009 in parallel; then their implementations (T006/T008/T011/T013/T015) respecting each test→impl pair.
- US1 tests T016/T017 in parallel before implementation.
- Polish: T029/T030 in parallel.

---

## Implementation Strategy

### MVP First (Foundational + US1)

1. Phase 1 Setup → 2. Phase 2 Foundational (risk gate tested!) → 3. Phase 3 US1.
4. STOP and VALIDATE: run a dry-run tick with the example strategy; confirm no real orders.
5. This is the safe MVP — trading core proven in dry-run before any dashboard or live use.

### Incremental Delivery

Foundational+US1 (MVP, dry-run validated) → US2 (see + control + kill switch) → US3
(automatic loss cap) → Polish + final verification before live.

### Implementation handoff

Per the agreed workflow, implementation runs under **superpowers** skills
(`test-driven-development` per task, `subagent-driven-development`/`executing-plans` for
parallel-safe tasks, `verification-before-completion` at T032), NOT `/speckit-implement`.

---

## Notes

- [P] = different files, no incomplete dependencies.
- Commit after each task or logical group.
- No test may touch the network or a real wallet (Constitution IV).
- Verify each test fails before implementing it.
- Do not enter live mode until T032 passes and the kill switch is verified.
