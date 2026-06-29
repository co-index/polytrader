# Phase 0 Research: Core Trading Framework

All major technology choices were settled during brainstorming; this file records the
decisions, rationale, and alternatives so the plan has no unresolved unknowns.

## D1. Exchange integration library

- **Decision**: Use the official `py-clob-client` (stable line) as the sole exchange
  integration, isolated behind `client.py`.
- **Rationale**: Official, best-documented Python client; supports the full CLOB API
  (market data, order placement/cancel, balances, positions) plus EIP-712 order signing
  via a Polygon proxy wallet. Matches the single-operator Python project.
- **Alternatives considered**: `py-clob-client-v2`/new unified SDK (newer, less
  documented — deferred to a later, separately reviewed migration per Constitution
  "Security & Funds Constraints"); TypeScript `@polymarket/clob-client` (rejected — would
  split the stack and the dashboard is also Python).
- **Open detail (resolved at implementation, not a blocker)**: exact method names/signatures
  (e.g. `create_and_post_order`, `cancel`, `get_orders`, positions endpoint) are confirmed
  against the installed package's README/examples during the client task. The contract in
  `contracts/` defines the *internal* interface `client.py` must expose regardless of SDK
  naming.

## D2. Market data sources

- **Decision**: CLOB for order books/prices and order management; Gamma for market
  metadata (resolving whitelisted market/token ids); Data API for positions/balances.
- **Rationale**: This is Polymarket's documented split; `client.py` wraps all three so
  strategies see one `MarketState`.
- **Alternatives**: Scraping the web UI (rejected — fragile, unsupported).

## D3. Dry-run vs live

- **Decision**: A single `mode` flag (`dry_run` | `live`) on the engine. In `dry_run`,
  the engine performs the identical pipeline (data → strategy → risk gate → record) but
  the placement step writes a simulated order/fill to the store instead of calling the
  client's real placement method. Default is `dry_run` on every fresh start.
- **Rationale**: Same code path exercised in both modes (only the final placement call
  differs), so dry-run genuinely validates the pipeline. Satisfies Constitution III.
- **Alternatives**: Separate simulated vs live engines (rejected — duplicate logic,
  divergence risk); no dry-run (rejected — violates Constitution III).

## D4. Engine ↔ dashboard coupling

- **Decision**: Engine and Streamlit dashboard are separate processes that communicate
  only through the SQLite store. Controls (start/stop, mode toggle, kill switch) are
  written by the dashboard as rows/flags the engine reads each tick.
- **Rationale**: Constitution V (no shared in-memory state) and SC-007 (dashboard usable
  when engine is stopped/crashed). SQLite handles single-writer + reader well at this scale.
- **Alternatives**: In-process Streamlit thread running the engine (rejected — Streamlit's
  rerun model makes long-lived loops fragile, and a crash would take the dashboard down);
  a message queue/REST API (rejected — overkill for one operator, deferred to a future
  FastAPI upgrade).

## D5. Control & kill-switch mechanism

- **Decision**: The engine reads a `command`/state row from the store at the top of each
  tick: `run`/`stop`, `dry_run`/`live`, and a `kill` flag. On `kill`, the engine cancels
  all open orders via the client then stops. The daily-loss circuit breaker sets `stop`
  autonomously.
- **Rationale**: Polling a store flag keeps engine and dashboard decoupled and makes the
  kill switch work even if the dashboard issued it moments before a crash.
- **Alternatives**: OS signals/IPC (rejected — more coupling, harder to test).

## D6. Configuration & secrets

- **Decision**: Secrets (`WALLET_PRIVATE_KEY`, `CLOB_API_KEY/SECRET/PASSPHRASE`) from
  `.env`/environment via `config.py`; non-secret config (risk limits, market whitelist,
  tick interval, default mode) from `config.yaml`. `pydantic` models validate both.
- **Rationale**: Constitution I (secrets out of source) and FR-008. `config.yaml` is
  reviewable; limits can't be changed by strategies (FR-014).
- **Alternatives**: Everything in one file (rejected — risks committing secrets); a
  hosted secrets manager (rejected — overkill for single-operator local use).

## D7. Testing approach for a funds-handling system

- **Decision**: pytest with the client fully mocked; exhaustive unit tests for the risk
  gate (every limit + every rejection path) before live mode is trusted; one integration
  test driving a full dry-run tick with a fake client.
- **Rationale**: Constitution IV; no test may hit the network or a real wallet.
- **Alternatives**: Live testnet trading in CI (rejected — no reliable Polymarket testnet
  for this, and it would risk real funds/keys in CI).
