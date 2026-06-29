# Quickstart: Core Trading Framework

Runnable validation that the framework works end to end. Proves SC-001 (fresh checkout
→ dry-run in <30 min), SC-005 (always starts dry-run), and the kill switch (SC-004).

## Prerequisites

- Python 3.11, a virtualenv
- A funded Polymarket-compatible wallet + CLOB API credentials (live mode only;
  dry-run with read-only data needs only the wallet address for market reads)

## Setup

```bash
cd polytrader
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"          # installs polytrader + py-clob-client, streamlit, pytest

cp .env.example .env             # fill WALLET_PRIVATE_KEY, CLOB_API_KEY/SECRET/PASSPHRASE
cp config.yaml.example config.yaml   # set market_whitelist; keep conservative limits
```

`.env` and `config.yaml` are gitignored — never commit them.

## 1. Run the tests first (Constitution IV)

```bash
pytest -q
```

Expected: risk-gate unit tests and the dry-run integration test pass. No test touches
the network.

## 2. Start the engine in dry-run (default)

```bash
python -m polytrader.engine        # starts in dry_run; logs "mode=dry_run"
```

Expected: each tick logs a market fetch, the example strategy proposes an order, the
risk gate approves/rejects it, and a **simulated** order/fill is written to the store.
No on-chain activity. Verify mode is `dry_run` without having set anything (SC-005).

## 3. Open the dashboard

```bash
streamlit run src/polytrader/dashboard.py
```

Expected: positions, P&L, recent orders/fills, engine run-state and mode, and recent
events render from the SQLite store. Stop the engine process — the dashboard still shows
the last recorded state (SC-007).

## 4. Verify controls and kill switch

- Click **Stop** → engine idles, dashboard shows stopped.
- Click **Kill switch** → engine cancels all open orders and stops; no open orders remain
  (SC-004).
- Toggle **dry-run → live** → only now do real orders get placed, within configured limits.

## 5. Verify the circuit breaker (simulated)

With a low `daily_loss_limit_usd`, feed simulated losing fills (see
`tests/integration/test_dry_run_tick.py`) until the day's realized loss crosses the
threshold. Expected: the engine auto-stops within one tick with
`stopped_reason="daily-loss circuit breaker"` (SC-003).

See [contracts/interfaces.md](./contracts/interfaces.md) for the module interfaces and
[data-model.md](./data-model.md) for the entities referenced above.
