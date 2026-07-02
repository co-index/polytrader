# polytrader

A single-operator Python framework for running **automated trading strategies on
Polymarket** with real funds — built safety-first. Strategies are pluggable; the
framework handles market data, a mandatory risk gate, dry-run/live execution,
persistence, and a Streamlit dashboard for monitoring and control.

> ⚠️ **Real money.** Trading is risky and strategy profitability is **not** provided by
> this framework — it ships only the plumbing and a trivial example strategy. Validate
> in dry-run, start tiny, and read the [constitution](.specify/memory/constitution.md).

## Architecture

Six single-purpose modules, decoupled through a SQLite store so the dashboard survives
an engine crash:

```
markets ─▶ engine ─▶ strategy ─▶ risk gate ─▶ simulate (dry-run) / place (live) ─▶ store
                                                                                      ▲
                                                              Streamlit dashboard ────┘
```

| Module | Role |
|---|---|
| `config.py` | Settings + RiskConfig; secrets from env only |
| `client.py` | **Sole** `py-clob-client` chokepoint (market data, orders, account) |
| `risk.py` | Risk gate — per-order / exposure / whitelist caps + daily-loss breaker |
| `strategy/` | Pluggable `Strategy` interface + bundled `ExampleStrategy` |
| `engine.py` | Tick loop: data → strategy → risk → execute → record |
| `store.py` | SQLite persistence + engine⇄dashboard command channel |
| `dashboard.py` | Streamlit monitor + controls (start/stop, mode, kill switch) |
| `basket.py` | `BasketStore` — snapshot + opportunity log for the basket scanner |
| `basket_scanner.py` | **Read-only** negRisk basket-arb scanner + paper sim (`basket_arb`) |

## Safety guarantees (binding — see the constitution)

- **Secrets never in git or logs** — wallet key & API creds live only in `.env`.
- **No order bypasses the risk gate** — every intent passes `RiskManager.check()`.
- **Fresh start is always dry-run** — live is an explicit, deliberate switch.
- **Risk gate is exhaustively unit-tested** before any live trust.
- **Kill switch** cancels all open orders and stops the engine.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env              # fill wallet key + CLOB API creds (gitignored)
cp config.yaml.example config.yaml  # set markets + market_whitelist; keep limits small
```

## Run

```bash
pytest -q                                   # 1. tests must pass first

polytrader-scanner                          # 2. paper lab: read-only basket-arb scanner
                                            #    (or: python -m polytrader.basket_scanner)

streamlit run src/polytrader/dashboard.py   # 3. dashboard (monitor, leaderboard)

python -m polytrader.engine                 # 4. (optional) live engine — starts in dry-run
```

Default risk limits: per-order ≤ $5, total exposure ≤ $50, daily-loss breaker $20.
Switch to **live** only from the dashboard, after validating in dry-run.

### Paper lab (simulate first, fund the winner later)

The Paper Lab runs the **basket-arb scanner** (`polytrader-scanner`): a **read-only**
sweep of Polymarket's negRisk multi-outcome events that logs structural mispricings
(Σask < 1 to buy a basket, Σbid > 1 to mint & sell one) and paper-executes them under
honest depth constraints as the `basket_arb` strategy. It never places orders and needs
no wallet. The dashboard shows a bilingual leaderboard + the live opportunity feed.

> **The six directional/market-making strategies are retired.** Empirically they never
> profit on real books (moves < spread; arb sums > 1), so `python -m polytrader.paper.runner`
> is now a no-op stub. The strategy classes remain importable for experiments/tests, but
> only `basket_arb` is run. See the design note:
> [docs/superpowers/specs/2026-06-29-paper-trading-lab-design.md](docs/superpowers/specs/2026-06-29-paper-trading-lab-design.md).

> **Runtime data is per-machine, not in git.** The SQLite DBs (`data/*.db`) are
> `.gitignore`d, so a fresh clone starts with an **empty** leaderboard — it fills once
> *this machine* runs `polytrader-scanner`. A different leaderboard on another computer
> means a different local DB / a different process was launched, not a code mismatch.

### Deploy the scanner to a server

`deploy/install.sh` sets up the read-only scanner + dashboard as systemd services on a
Debian/Ubuntu VPS (≈270 MB RAM, ~1 GB/day). See [deploy/README.md](deploy/README.md).

See [specs/001-core-framework/quickstart.md](specs/001-core-framework/quickstart.md) for
the full validation walkthrough, and [tasks.md](specs/001-core-framework/tasks.md) for
build status.

## Development

Spec-driven via [Spec Kit](https://github.com/github/spec-kit) (`/speckit-*`,
docs under `specs/`); implementation via test-driven development. Every change is
test-first; the risk gate and the SDK-chokepoint isolation have dedicated tests.

## Known limitations (MVP)

- Realized-P&L-from-live-fills matching is a follow-up; the daily-loss breaker reads a
  P&L ledger that is currently fed explicitly.
- One active strategy at a time; backtesting is out of scope (dry-run validates instead).
- `py-clob-client` (stable) is the integration; v2 migration is a separate, reviewed step.
