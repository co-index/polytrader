"""Streamlit dashboard — monitor and control the engine.

Reads everything from the store and writes commands back to the store; it never
touches the engine or the SDK directly (Constitution V). It stays usable when the
engine process is stopped or crashed (SC-007), because all state lives in the store.

Run:  streamlit run src/polytrader/dashboard.py
"""

from __future__ import annotations

import os

import streamlit as st

from polytrader import i18n
from polytrader.config import Settings
from polytrader.paper.store import PaperStore
from polytrader.store import Store


def get_store() -> Store:
    db_path = os.environ.get("POLYTRADER_DB", "data/polytrader.db")
    store = Store(db_path)
    store.init_schema()
    return store


def get_paper_store() -> PaperStore:
    db_path = os.environ.get("POLYTRADER_PAPER_DB", "data/paper.db")
    paper = PaperStore(db_path)
    paper.init_schema()
    return paper


def _leaderboard_row(r: dict, _, lang: str) -> dict:
    """Map a PaperStore row to a display row with translated, sorted-friendly columns."""
    win_rate = (r["wins"] / r["trades"]) if r["trades"] else 0.0
    return {
        _("col_strategy"): i18n.strategy_label(r["name"], lang),
        _("col_equity"): round(r["equity"], 2),
        _("col_total_pnl"): round(r["total_pnl"], 2),
        _("col_realized"): round(r["realized"], 2),
        _("col_unrealized"): round(r["unrealized"], 2),
        _("col_fills"): r["fills"],
        _("col_positions"): r["positions"],
        _("col_win_rate"): f"{win_rate:.0%}",
        _("col_rejects"): r["rejects"],
    }


def _render_status(store: Store, _) -> None:
    """Live status banner — re-reads the store so auto-refresh shows the truth."""
    state = store.get_engine_state()
    running = _("running") if state.run else _("stopped")
    badge = "🟢" if state.run else "🔴"
    warn = "  " + (_("live_warning") if state.mode == "live" else _("dry_run_note"))
    st.subheader(f"{badge} {running} · {_('mode')}: {state.mode}{warn}")
    if state.stopped_reason:
        st.error(_("stopped_reason").format(reason=state.stopped_reason))


def _render_leaderboard(_, lang: str) -> None:
    """Paper Lab leaderboard — always simulated, reads the paper store."""
    rows = get_paper_store().leaderboard()
    if rows:
        st.dataframe([_leaderboard_row(r, _, lang) for r in rows], width="stretch")
    else:
        st.caption(_("no_paper"))


def _render_order_details(_, lang: str) -> None:
    """Drill into one strategy's paper order log, with a free-text search filter."""
    paper = get_paper_store()
    names = [r["name"] for r in paper.leaderboard()]
    if not names:
        return
    st.markdown(f"#### {_('order_details')}")
    selected = st.selectbox(
        _("select_strategy"), names,
        format_func=lambda n: i18n.strategy_label(n, lang), key="order_strategy",
    )
    query = st.text_input(_("search"), key="order_search").strip().lower()
    orders = paper.orders(selected)
    if query:
        orders = [o for o in orders if any(query in str(v).lower() for v in o.values())]
    if orders:
        st.dataframe(orders, width="stretch")
    else:
        st.caption(_("no_orders"))


def _render_live_data(store: Store, _) -> None:
    """Live engine data (P&L, positions, orders, events) — reads the live store."""
    pnl = store.pnl_today()
    st.metric(_("pnl_today"), f"{pnl.realized_usd:.2f}")

    st.markdown(f"### {_('positions')}")
    positions = store.positions()
    if positions:
        st.dataframe([p.__dict__ for p in positions], width="stretch")
    else:
        st.caption(_("no_positions"))

    st.markdown(f"### {_('recent_orders')}")
    orders = store.recent_orders(50)
    if orders:
        st.dataframe([o.__dict__ for o in orders], width="stretch")
    else:
        st.caption(_("no_orders"))

    st.markdown(f"### {_('recent_events')}")
    events = store.recent_events(50)
    if events:
        st.dataframe([e.__dict__ for e in events], width="stretch")
    else:
        st.caption(_("no_events"))


def render(store: Store) -> None:
    st.set_page_config(page_title="polytrader", layout="wide")
    st.title("polytrader")

    # ---- language picker (bilingual label avoids a chicken-and-egg on first paint) ----
    lang_name = st.sidebar.selectbox("🌐 Language / 语言", list(i18n.LANGUAGES), key="lang")
    lang = i18n.LANGUAGES[lang_name]

    def _(key: str) -> str:
        return i18n.t(key, lang)

    # ---- auto-refresh: re-run the live blocks on an interval without a manual reload ----
    auto = st.sidebar.checkbox(_("auto_refresh"), value=True, key="auto_refresh")
    every = 3 if auto else None

    state = store.get_engine_state()

    # ===== Live engine: the single configured strategy, real or dry-run =====
    st.header(_("live_engine"))
    st.fragment(run_every=every)(lambda: _render_status(store, _))()

    # ---- controls (write commands to the live store) ----
    c1, c2, c3 = st.columns(3)
    # One button toggles run/stop: it shows the action it will perform.
    if c1.button(_("stop") if state.run else _("start"), key="run_toggle"):
        store.set_command(run=not state.run)
        if not state.run:  # we were stopped and are now starting
            store.set_status(stopped_reason=None)
        st.rerun()
    if c2.button(_("toggle_mode")):
        store.set_command(mode="dry_run" if state.mode == "live" else "live")
        st.rerun()
    if c3.button(_("kill")):
        store.set_command(kill=True)
        st.rerun()

    st.fragment(run_every=every)(lambda: _render_live_data(store, _))()

    # ===== Paper Lab: all strategies, always simulated =====
    st.header(_("leaderboard"))
    st.caption(_("paper_lab_note"))
    st.fragment(run_every=every)(lambda: _render_leaderboard(_, lang))()
    _render_order_details(_, lang)


def main() -> None:  # pragma: no cover - Streamlit entry
    # Optional: surface configured limits read-only (never secrets).
    try:
        Settings.load("config.yaml", env={})  # validates config exists; secrets omitted
    except Exception:
        pass
    render(get_store())


if __name__ == "__main__":  # pragma: no cover - `streamlit run` executes as __main__
    main()
