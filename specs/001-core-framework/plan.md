# Implementation Plan: Core Trading Framework

**Branch**: `001-core-framework` | **Date**: 2026-06-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/001-core-framework/spec.md`

## Summary

Build a single-operator Python framework that runs pluggable strategies against
Polymarket. The engine polls market data on a tick, hands a market snapshot to the
active strategy, routes every proposed order through a mandatory risk gate, and then
either simulates (dry-run, the default) or places the order via a single
`py-clob-client` chokepoint. All orders, fills, positions, P&L, and errors are
persisted to SQLite. A Streamlit dashboard reads that SQLite store to show state and
to drive controls (start/stop, dry-run↔live, kill switch). Engine and dashboard are
separate processes coupled only through the database, so the dashboard survives an
engine crash.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: `py-clob-client` (stable line — sole exchange integration),
`streamlit` (dashboard), `pydantic` (config + typed models), `pyyaml` (config file),
`pytest` + `pytest-mock` (tests). SQLite via the stdlib `sqlite3`.

**Storage**: Local SQLite file (`data/polytrader.db`, gitignored). Tables for orders,
fills, position snapshots, pnl, engine_state, and event log.

**Testing**: pytest. Unit tests for `risk`, `store`, `config`, `strategy`; integration
test for a dry-run end-to-end tick with a mocked client. No test touches the network
or a real wallet (mandated by Constitution IV).

**Target Platform**: Single operator's local machine (macOS/Linux).

**Project Type**: Single Python project — installable package `polytrader` plus a
Streamlit dashboard entry point.

**Performance Goals**: Not latency-critical. Tick cadence is configurable (default
~10s). Must respect Polymarket's ~60 orders/min/key rate limit via client-side
throttling/backoff.

**Constraints**: Secrets only from environment/`.env` (Constitution I). Every order
passes the risk gate (Constitution II). Fresh start is always dry-run (Constitution
III). No secrets in logs (Constitution VI).

**Scale/Scope**: One operator, small capital, a handful of whitelisted markets, one
active strategy at a time for the MVP.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | How this plan complies | Status |
|-----------|------------------------|--------|
| I. Capital Safety First | Secrets read only via `config.py` from env/`.env`; `.gitignore` already blocks `.env`/keys/db; no secret is logged | ✅ |
| II. Mandatory Risk Gate (NON-NEGOTIABLE) | `engine.py` calls `risk.RiskManager.check()` for every intent; `client.py` placement is only reached for approved orders; no other order path exists | ✅ |
| III. Dry-Run First, Explicit Live | `engine.py` starts `mode=dry_run`; live requires explicit config flag or dashboard toggle write to `engine_state` | ✅ |
| IV. Test-First, Risk-Critical Coverage (NON-NEGOTIABLE) | TDD via superpowers; `risk` gets exhaustive unit tests before live trust; client is mocked in all tests | ✅ |
| V. Modular Isolation & Single SDK Chokepoint | Six modules; `client.py` is the only importer of `py_clob_client`; strategies use `strategy/base.py` types; engine↔dashboard talk only via `store.py` | ✅ |
| VI. Observability & Auditable State | All orders/fills/positions/pnl/errors persisted in `store.py`; structured logging without secrets; engine mode/state always stored | ✅ |

No violations — Complexity Tracking section omitted.

## Project Structure

### Documentation (this feature)

```text
specs/001-core-framework/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (strategy + risk-gate + store contracts)
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/polytrader/
├── __init__.py
├── config.py            # Settings + RiskConfig; loads .env + config.yaml
├── client.py            # PolymarketClient — ONLY module importing py_clob_client
├── risk.py              # RiskManager.check(intent, state) -> Decision (the gate)
├── store.py             # SQLite persistence: orders, fills, positions, pnl, state, events
├── engine.py            # Engine: tick loop, start/stop, dry-run/live, kill switch
├── strategy/
│   ├── __init__.py
│   ├── base.py          # Strategy protocol, OrderIntent, MarketState dataclasses
│   └── example.py       # bundled example strategy (proves the pipeline)
└── dashboard.py         # Streamlit app reading store.py

tests/
├── unit/
│   ├── test_risk.py     # exhaustive risk-gate coverage (Constitution IV)
│   ├── test_config.py
│   ├── test_store.py
│   └── test_strategy.py
└── integration/
    └── test_dry_run_tick.py   # end-to-end tick with mocked client

config.yaml.example      # risk limits, market whitelist, tick interval, mode default
.env.example             # WALLET_PRIVATE_KEY, CLOB_API_KEY/SECRET/PASSPHRASE (placeholders)
pyproject.toml           # package metadata + deps + pytest config
README.md                # setup + run instructions
```

**Structure Decision**: Single project. The framework is one installable package
(`src/polytrader/`) with a Streamlit dashboard entry point; the engine runs as a
separate process. This matches the spec's single-operator scope and keeps the six
constitution modules as six focused files.

## Complexity Tracking

No constitution violations; section intentionally empty.
