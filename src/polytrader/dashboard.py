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


def render(store: Store) -> None:
    st.set_page_config(page_title="polytrader", layout="wide")
    st.title("polytrader")

    # ---- language picker (bilingual label avoids a chicken-and-egg on first paint) ----
    lang_name = st.sidebar.selectbox("🌐 Language / 语言", list(i18n.LANGUAGES), key="lang")
    lang = i18n.LANGUAGES[lang_name]

    def _(key: str) -> str:
        return i18n.t(key, lang)

    state = store.get_engine_state()

    # ---- status + mode banner ----
    mode = state.mode
    running = _("running") if state.run else _("stopped")
    badge = "🟢" if state.run else "🔴"
    warn = "  " + (_("live_warning") if mode == "live" else _("dry_run_note"))
    st.subheader(f"{badge} {running} · {_('mode')}: {mode}{warn}")
    if state.stopped_reason:
        st.error(_("stopped_reason").format(reason=state.stopped_reason))

    # ---- controls (write commands to the store) ----
    c1, c2, c3, c4 = st.columns(4)
    if c1.button(_("start")):
        store.set_command(run=True)
        store.set_status(stopped_reason=None)
        st.rerun()
    if c2.button(_("stop")):
        store.set_command(run=False)
        st.rerun()
    if c3.button(_("toggle_mode")):
        store.set_command(mode="dry_run" if mode == "live" else "live")
        st.rerun()
    if c4.button(_("kill")):
        store.set_command(kill=True)
        st.rerun()

    # ---- strategy leaderboard (paper trading) ----
    st.markdown(f"### {_('leaderboard')}")
    rows = get_paper_store().leaderboard()
    if rows:
        st.dataframe([_leaderboard_row(r, _, lang) for r in rows], width="stretch")
    else:
        st.caption(_("no_paper"))

    # ---- P&L ----
    pnl = store.pnl_today()
    st.metric(_("pnl_today"), f"{pnl.realized_usd:.2f}")

    # ---- positions ----
    st.markdown(f"### {_('positions')}")
    positions = store.positions()
    if positions:
        st.dataframe([p.__dict__ for p in positions], width="stretch")
    else:
        st.caption(_("no_positions"))

    # ---- recent orders ----
    st.markdown(f"### {_('recent_orders')}")
    orders = store.recent_orders(50)
    if orders:
        st.dataframe([o.__dict__ for o in orders], width="stretch")
    else:
        st.caption(_("no_orders"))

    # ---- recent events ----
    st.markdown(f"### {_('recent_events')}")
    events = store.recent_events(50)
    if events:
        st.dataframe([e.__dict__ for e in events], width="stretch")
    else:
        st.caption(_("no_events"))


def main() -> None:  # pragma: no cover - Streamlit entry
    # Optional: surface configured limits read-only (never secrets).
    try:
        Settings.load("config.yaml", env={})  # validates config exists; secrets omitted
    except Exception:
        pass
    render(get_store())


if __name__ == "__main__":  # pragma: no cover - `streamlit run` executes as __main__
    main()
