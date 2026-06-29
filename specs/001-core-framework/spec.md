# Feature Specification: Core Trading Framework

**Feature Branch**: `001-core-framework`

**Created**: 2026-06-29

**Status**: Draft

**Input**: User description: "Build the base framework for running automated trading strategies on Polymarket with real funds. Strategies are pluggable and added later. The framework must connect to Polymarket, read market data, place and cancel orders, enforce strict risk limits, and present a dashboard where the operator can watch positions/P&L/logs and start/stop trading. Start with small real money, but keep a dry-run mode for safe first runs."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator runs a strategy safely in dry-run, then goes live (Priority: P1)

The operator configures wallet credentials and risk limits, starts the framework,
and it runs in dry-run by default: it reads live Polymarket prices and a plugged-in
strategy proposes orders, but no real money moves. Every proposed order is checked
against risk limits and recorded. Once satisfied, the operator explicitly switches to
live mode and the same strategy now places real orders within the configured limits.

**Why this priority**: This is the core value and the core safety story. Without
dry-run-then-live, the framework either can't trade or can't be trusted with funds.
A working version of just this story is a usable MVP.

**Independent Test**: Plug in the bundled example strategy, start in dry-run, confirm
simulated orders appear in the store/dashboard with no on-chain activity; switch to
live with tiny limits and confirm one real order is placed and recorded.

**Acceptance Scenarios**:

1. **Given** valid credentials and default config, **When** the operator starts the framework, **Then** it starts in dry-run mode and this mode is clearly shown.
2. **Given** a strategy proposing an order within limits in dry-run, **When** a tick runs, **Then** a simulated order is recorded and no real order is sent.
3. **Given** dry-run validated, **When** the operator explicitly switches to live, **Then** subsequent in-limit proposals place real orders and are recorded.
4. **Given** live mode, **When** a strategy proposes an order exceeding a risk limit, **Then** the order is rejected, not sent, and the rejection is recorded with a reason.

---

### User Story 2 - Operator monitors and controls trading from a dashboard (Priority: P1)

The operator opens a web dashboard and sees current positions, realized/unrealized
P&L, recent orders and fills, the engine's run state and mode (dry-run/live), and a
log of recent activity and errors. From the dashboard the operator can start and stop
the engine, toggle dry-run/live, and hit a kill switch that stops trading and cancels
all open orders.

**Why this priority**: With real money moving, the operator must be able to see what
the system is doing and stop it fast. Monitoring + kill switch is as essential as
trading itself.

**Independent Test**: With the engine running, open the dashboard and confirm
positions/P&L/orders/logs render from stored data; click stop and confirm the engine
halts; click the kill switch and confirm open orders are cancelled.

**Acceptance Scenarios**:

1. **Given** the engine has traded, **When** the operator opens the dashboard, **Then** positions, P&L, recent orders, mode, and run state are displayed.
2. **Given** the engine is running, **When** the operator clicks stop, **Then** the engine stops placing new orders and the dashboard reflects the stopped state.
3. **Given** open orders exist, **When** the operator activates the kill switch, **Then** the engine stops and all open orders are cancelled.
4. **Given** the engine crashes, **When** the operator opens the dashboard, **Then** the last recorded state is still visible (dashboard does not depend on the engine being alive).

---

### User Story 3 - Risk limits cap losses automatically (Priority: P2)

While trading, the framework enforces a per-order size cap, a total open-exposure cap,
a per-day realized-loss circuit breaker, and a market whitelist. If cumulative
realized loss for the day reaches the configured threshold, the engine stops trading
on its own without operator intervention.

**Why this priority**: Automated loss control is what makes unattended small-money
trading acceptable. It depends on the trading core (P1) existing first.

**Independent Test**: Configure a low daily-loss threshold, feed simulated losing
fills until the threshold is crossed, and confirm the engine auto-stops and records
why.

**Acceptance Scenarios**:

1. **Given** an order larger than the per-order cap, **When** it is evaluated, **Then** it is rejected before reaching the exchange.
2. **Given** open exposure at the cap, **When** a new order would exceed total exposure, **Then** it is rejected.
3. **Given** day's realized loss reaches the circuit-breaker threshold, **When** the next tick runs, **Then** the engine auto-stops and records the trigger.
4. **Given** a market not on the whitelist, **When** a strategy proposes trading it, **Then** the order is rejected.

---

### Edge Cases

- What happens when the Polymarket API is unreachable or returns errors? The engine retries with backoff, records the failure, and treats repeated failures as a circuit-breaker signal rather than spamming orders.
- What happens when the order rate limit (~60/min) is hit? The client throttles and defers rather than erroring out the whole tick.
- What happens when credentials are missing or invalid at startup? The framework refuses to start live mode and reports the problem; dry-run with read-only data may still run.
- What happens when a strategy throws or returns malformed order intents? The engine isolates the failure, skips that tick's bad intents, and records the error without crashing.
- What happens if the operator switches to live without a validated dry-run? Allowed, but the system defaults to dry-run on every fresh start so this is always a deliberate action.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read live market data from Polymarket (markets, order books, prices) for whitelisted markets.
- **FR-002**: System MUST place and cancel orders on Polymarket and retrieve the operator's positions and balances.
- **FR-003**: System MUST expose a strategy interface so strategies can be added as pluggable units that receive market state and return proposed order intents, without touching the exchange integration directly.
- **FR-004**: System MUST route every proposed order through a risk gate before it can reach the exchange; no order may bypass this gate.
- **FR-005**: Risk gate MUST enforce a per-order size cap, a total open-exposure cap, a per-day realized-loss circuit breaker, a market whitelist, and a kill switch.
- **FR-006**: System MUST default to dry-run (simulated, no real orders) on every fresh start, and MUST require an explicit action to enter live trading.
- **FR-007**: System MUST persist all orders, fills, position snapshots, P&L, and errors to local storage that survives engine restarts.
- **FR-008**: System MUST keep wallet keys and API credentials out of source control and out of logs, reading them only from the environment/config.
- **FR-009**: System MUST provide a dashboard showing positions, P&L, recent orders/fills, engine run state, current mode, and recent logs/errors.
- **FR-010**: Operator MUST be able to start the engine, stop the engine, toggle dry-run/live, and trigger a kill switch (stop + cancel all open orders) from the dashboard.
- **FR-011**: The dashboard MUST read from persisted storage and remain usable when the engine is not running.
- **FR-012**: System MUST respect the exchange order rate limit, retrying failed exchange calls with backoff and recording failures.
- **FR-013**: System MUST ship with at least one bundled example strategy sufficient to demonstrate the full pipeline end to end.
- **FR-014**: Risk limits MUST be configurable via reviewed configuration and MUST NOT be changeable by a strategy at runtime.

### Key Entities *(include if feature involves data)*

- **Market**: A Polymarket market the framework may trade; identified by market/token id; carries current prices/order book; may be on or off the whitelist.
- **Order Intent**: A strategy's proposed action (market, side, size, price) before risk evaluation.
- **Order**: A risk-approved order, real or simulated, with status (pending/placed/cancelled/filled/rejected) and a reason if rejected.
- **Fill**: An execution against an order, with size and price, feeding position and P&L.
- **Position**: Current holding in a market, with size and average cost, used for exposure and P&L.
- **Risk Config**: The set of limits (per-order cap, exposure cap, daily-loss threshold, whitelist) governing the risk gate.
- **Engine State**: Whether the engine is running/stopped and in dry-run/live mode.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator can go from a fresh checkout to a strategy running in dry-run against live market data in under 30 minutes by following the setup steps.
- **SC-002**: 100% of orders that exceed any configured risk limit are rejected before reaching the exchange (zero limit-breaching orders sent).
- **SC-003**: When the daily-loss circuit breaker threshold is reached, the engine stops placing new orders within one tick cycle.
- **SC-004**: The kill switch stops the engine and cancels all open orders, with no open orders remaining afterward.
- **SC-005**: The framework never starts in live mode without an explicit operator action (verified: every fresh start is dry-run).
- **SC-006**: No wallet key or API credential ever appears in the repository or in any log output.
- **SC-007**: The dashboard reflects the latest recorded positions, P&L, orders, and engine state, and stays viewable when the engine is stopped or crashed.

## Assumptions

- The operator supplies a funded Polymarket-compatible wallet and API credentials; obtaining/funding the wallet is out of scope.
- Strategy profitability is out of scope; this feature delivers the framework and a trivial example strategy only. Real edge is validated later, per strategy.
- Starting capital is small and risk limits start conservative; the framework is run by a single operator on their own machine, not multi-tenant.
- The integration targets Polymarket's CLOB (order book), Gamma (market metadata), and Data API (positions); the official Python client (`py-clob-client`, stable line) is assumed as the integration library, with the dashboard built in Streamlit. (Recorded here as the agreed technical direction; requirements above stay capability-focused.)
- One tick cycle is the unit of engine cadence; exact interval is configurable and not fixed by this spec.
- Backtesting/historical simulation is out of scope for this feature; dry-run against live data is the validation mechanism.
