<!--
Sync Impact Report
- Version change: (template) → 1.0.0
- Ratification: initial adoption (template placeholders replaced with concrete principles)
- Modified principles: all 6 defined fresh from project brainstorm
    I. Capital Safety First
    II. Mandatory Risk Gate (NON-NEGOTIABLE)
    III. Dry-Run First, Explicit Live
    IV. Test-First, Risk-Critical Coverage (NON-NEGOTIABLE)
    V. Modular Isolation & Single SDK Chokepoint
    VI. Observability & Auditable State
- Added sections: Security & Funds Constraints; Development Workflow & Quality Gates
- Removed sections: none
- Templates requiring updates:
    ✅ .specify/templates/plan-template.md  — Constitution Check gate references generic principles; compatible
    ✅ .specify/templates/spec-template.md  — no mandatory-section conflict
    ✅ .specify/templates/tasks-template.md — testing/observability task types align
- Deferred TODOs: none
-->

# polytrader Constitution

polytrader is a Python framework for running automated trading strategies on
Polymarket with real funds. These principles are binding because mistakes here
lose money or leak wallet keys. They supersede convenience.

## Core Principles

### I. Capital Safety First
Wallet private keys and API credentials MUST live only in `.env` (or the process
environment) and MUST never be committed, logged, printed, or sent to any external
service. `.gitignore` MUST keep `.env`, `*.key`, `*.pem`, and wallet files out of
version control. Code MUST read secrets from the environment, never from literals.
Rationale: a single leaked key drains the wallet irreversibly; this is the one
mistake with no recovery.

### II. Mandatory Risk Gate (NON-NEGOTIABLE)
Every order, without exception, MUST pass through the RiskManager before reaching
the exchange client. The RiskManager enforces, at minimum: per-order size cap,
total open-exposure cap, daily realized-loss circuit breaker (auto-stops the
engine), a market whitelist, and a kill switch (stop engine + cancel all open
orders). No code path may place an order that bypasses this gate.
Rationale: a bug in a strategy must not be able to spend more than the configured
limits; the gate is the single enforceable safety boundary.

### III. Dry-Run First, Explicit Live
The engine MUST default to dry-run (simulated bookkeeping, no real orders) on every
fresh start. Switching to live trading MUST be an explicit, deliberate action
(config flag or dashboard toggle), never the default and never implicit.
Rationale: the costly failure mode is sending real orders before the strategy is
validated; the default must fail safe.

### IV. Test-First, Risk-Critical Coverage (NON-NEGOTIABLE)
Development follows TDD: write a failing test, then implement. The RiskManager MUST
have unit tests covering every limit and every rejection path before it is trusted
with live mode. Tests MUST mock the Polymarket SDK — no test may place a real order
or require network/wallet access.
Rationale: the risk gate is the component whose correctness protects funds; it is
the least acceptable place for an untested assumption.

### V. Modular Isolation & Single SDK Chokepoint
The framework is split into single-purpose modules (config, client, risk, strategy,
engine, store, dashboard). The client module is the ONLY code that touches the
Polymarket SDK; strategies interact through the strategy interface and never call
the SDK directly. The engine and dashboard communicate only through the persisted
store, never by sharing in-memory state.
Rationale: a single SDK chokepoint makes auth, rate-limiting, and order routing
auditable in one place, and DB-decoupling lets the dashboard survive engine crashes.

### VI. Observability & Auditable State
All orders, fills, position snapshots, P&L, and errors MUST be persisted to the
local store (SQLite) and be visible in the dashboard. Logging MUST be structured and
MUST never include secrets. The current engine state (running/stopped, dry-run/live)
MUST always be observable.
Rationale: with real money moving, you must be able to answer "what did it do and
why" after the fact, and spot a misbehaving strategy in time to hit the kill switch.

## Security & Funds Constraints

- Default risk limits ship conservative (per-order ≤ $5, total exposure ≤ $50, daily
  loss circuit breaker $20) and live trading starts small until a strategy is proven.
- The SDK is `py-clob-client` (stable); migration to v2 is a deliberate, separately
  reviewed change.
- The Polymarket CLOB rate limit (~60 orders/min/key) MUST be respected; the client
  applies backoff and the engine treats repeated failures as a circuit-breaker signal.
- No strategy may widen a risk limit at runtime; limits change only via reviewed config.

## Development Workflow & Quality Gates

- Specs and plans are managed with Spec Kit (`/speckit-*`); implementation uses the
  superpowers TDD and plan-execution skills.
- Before any code is trusted in live mode: RiskManager unit tests pass, a dry-run
  end-to-end run completes, and the kill switch is verified to cancel open orders.
- Changes to RiskManager or the client module require extra scrutiny and full test
  coverage of new paths.

## Governance

This constitution supersedes other practices when they conflict. Amendments MUST be
documented in this file with a version bump and a Sync Impact Report. Versioning is
semantic: MAJOR for principle removals/redefinitions, MINOR for new principles or
materially expanded guidance, PATCH for clarifications. The NON-NEGOTIABLE principles
(II and IV) may not be relaxed to ship faster; if they block progress, fix the design,
not the principle. Every plan's Constitution Check MUST verify compliance with these
principles before implementation proceeds.

**Version**: 1.0.0 | **Ratified**: 2026-06-29 | **Last Amended**: 2026-06-29
