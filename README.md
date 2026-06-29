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

python -m polytrader.engine                 # 2. engine (starts in dry-run)

python -m polytrader.paper.runner           # 3. paper lab (compare strategies, simulated)

streamlit run src/polytrader/dashboard.py   # 4. dashboard (monitor, control, leaderboard)
```

Default risk limits: per-order ≤ $5, total exposure ≤ $50, daily-loss breaker $20.
Switch to **live** only from the dashboard, after validating in dry-run.

### Paper lab (simulate first, fund the winner later)

`python -m polytrader.paper.runner` runs five strategies (market-making, mean-reversion,
momentum, complementary-arb, example) side by side against live market data, each with
its own simulated account and a realistic top-of-book fill model. The dashboard shows a
bilingual leaderboard so you can compare them before risking real funds. Design:
[docs/superpowers/specs/2026-06-29-paper-trading-lab-design.md](docs/superpowers/specs/2026-06-29-paper-trading-lab-design.md).
The fill model is a fair *relative* comparison tool, not a live-fill predictor.

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
