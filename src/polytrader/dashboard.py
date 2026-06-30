"""Streamlit dashboard — monitor and control the engine.

Reads everything from the store and writes commands back to the store; it never
touches the engine or the SDK directly (Constitution V). It stays usable when the
engine process is stopped or crashed (SC-007), because all state lives in the store.

Run:  streamlit run src/polytrader/dashboard.py
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

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


_HEARTBEAT_MAX_AGE_S = 30


def _heartbeat_ok(last_tick_ts: str | None, now: datetime, max_age_s: float) -> bool:
    """True only if the engine ticked within max_age_s — proof a process is actually live."""
    if not last_tick_ts:
        return False
    try:
        t = datetime.fromisoformat(last_tick_ts)
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return (now - t).total_seconds() <= max_age_s


def _render_status(store: Store, _) -> None:
    """Live status banner — re-reads the store so auto-refresh shows the truth.

    'run' is only a command flag; we show green RUNNING only when there's a recent tick
    (heartbeat). run=True with no heartbeat means commanded-on but no engine is ticking.
    """
    state = store.get_engine_state()
    if not state.run:
        badge, status = "🔴", _("stopped")
    elif _heartbeat_ok(state.last_tick_ts, datetime.now(UTC), _HEARTBEAT_MAX_AGE_S):
        badge, status = "🟢", _("running")
    else:
        badge, status = "🟠", _("no_heartbeat")
    warn = "  " + (_("live_warning") if state.mode == "live" else _("dry_run_note"))
    st.subheader(f"{badge} {status} · {_('mode')}: {state.mode}{warn}")
    if state.stopped_reason:
        st.error(_("stopped_reason").format(reason=state.stopped_reason))


def _filter_orders(orders: list[dict], query: str) -> list[dict]:
    """Keep orders where any field contains the (case-insensitive) query substring."""
    q = query.strip().lower()
    if not q:
        return orders
    return [o for o in orders if any(q in str(v).lower() for v in o.values())]


_STATUS_KEY = {"filled": "st_filled", "resting": "st_resting", "rejected": "st_rejected"}


def _display_order(o: dict, _) -> dict:
    """Localize an order row's columns and status for display."""
    return {
        _("ord_time"): o["ts"],
        _("ord_token"): o["token_id"],
        _("ord_side"): o["side"],
        _("ord_size"): o["size"],
        _("ord_price"): o["price"],
        _("ord_status"): _(_STATUS_KEY.get(o["status"], o["status"])),
    }


def _open_trades_dialog(name: str, label: str, _) -> None:
    """Modal popup listing one strategy's orders (filled / resting / rejected), newest
    first, with a search filter. The leaderboard is kept out of auto-refresh so this
    dialog isn't closed by a periodic rerun."""

    @st.dialog(f"{_('order_details')} · {label}", width="large")
    def _dialog() -> None:
        query = st.text_input(_("search"), key="trade_search")
        rows = [_display_order(o, _) for o in reversed(get_paper_store().orders(name))]
        rows = _filter_orders(rows, query)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        else:
            st.caption(_("no_orders"))

    _dialog()


_LB_COLS = ("col_strategy", "col_total_pnl", "col_equity", "col_realized",
            "col_unrealized", "col_fills", "col_positions", "col_win_rate", "col_rejects")
_LB_WIDTHS = [2.2, 1, 1, 1, 1, 0.8, 0.8, 0.8, 0.8]


def _pnl_md(value: float) -> str:
    """Color the P&L: green when up, red when down, plain at zero."""
    if value > 0:
        return f":green[+{value:.2f}]"
    if value < 0:
        return f":red[{value:.2f}]"
    return f"{value:.2f}"


def _render_leaderboard(_, lang: str) -> None:
    """Paper Lab leaderboard. Each strategy name is a link-style button; clicking it
    opens that strategy's trades inline below — no checkbox column, the row is the action."""
    rows = get_paper_store().leaderboard()
    if not rows:
        st.caption(_("no_paper"))
        return
    hint, refresh = st.columns([6, 1], vertical_alignment="center")
    hint.caption(_("click_row_hint"))
    if refresh.button(_("refresh"), key="lb_refresh"):
        st.rerun()

    header = st.columns(_LB_WIDTHS, vertical_alignment="center")
    for col, key in zip(header, _LB_COLS, strict=True):
        col.markdown(f"**{_(key)}**")

    for r in rows:
        cells = st.columns(_LB_WIDTHS, vertical_alignment="center")
        label = i18n.strategy_label(r["name"], lang)
        # No stretch: a tertiary button hugs its label at the column's left edge, so the
        # name lines up under the "strategy" header instead of being centered/indented.
        if cells[0].button(label, key=f"lb_row_{r['name']}", type="tertiary"):
            _open_trades_dialog(r["name"], label, _)
        win = (r["wins"] / r["trades"]) if r["trades"] else 0.0
        cells[1].markdown(_pnl_md(r["total_pnl"]))
        cells[2].write(f"{r['equity']:.2f}")
        cells[3].write(f"{r['realized']:.2f}")
        cells[4].write(f"{r['unrealized']:.2f}")
        cells[5].write(r["fills"])
        cells[6].write(r["positions"])
        cells[7].write(f"{win:.0%}")
        cells[8].write(r["rejects"])


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
    # NOT auto-refreshed: a periodic rerun would close the trades modal. Use the Refresh
    # button to pull the latest snapshot. (The live-engine blocks above still auto-update.)
    st.header(_("leaderboard"))
    st.caption(_("paper_lab_note"))
    _render_leaderboard(_, lang)


def main() -> None:  # pragma: no cover - Streamlit entry
    # Optional: surface configured limits read-only (never secrets).
    try:
        Settings.load("config.yaml", env={})  # validates config exists; secrets omitted
    except Exception:
        pass
    render(get_store())


if __name__ == "__main__":  # pragma: no cover - `streamlit run` executes as __main__
    main()
