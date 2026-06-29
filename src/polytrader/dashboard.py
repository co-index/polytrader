"""Streamlit dashboard — monitor and control the engine.

Reads everything from the store and writes commands back to the store; it never
touches the engine or the SDK directly (Constitution V). It stays usable when the
engine process is stopped or crashed (SC-007), because all state lives in the store.

Run:  streamlit run src/polytrader/dashboard.py
"""

from __future__ import annotations

import os

import streamlit as st

from polytrader.config import Settings
from polytrader.store import Store


def get_store() -> Store:
    db_path = os.environ.get("POLYTRADER_DB", "data/polytrader.db")
    store = Store(db_path)
    store.init_schema()
    return store


def render(store: Store) -> None:
    st.set_page_config(page_title="polytrader", layout="wide")
    st.title("polytrader")

    state = store.get_engine_state()

    # ---- status + mode banner ----
    mode = state.mode
    running = "RUNNING" if state.run else "STOPPED"
    badge = "🟢" if state.run else "🔴"
    warn = "  ⚠️ LIVE — real funds" if mode == "live" else "  🧪 dry-run (simulated)"
    st.subheader(f"{badge} {running} · mode: {mode}{warn}")
    if state.stopped_reason:
        st.error(f"Stopped: {state.stopped_reason}")

    # ---- controls (write commands to the store) ----
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("▶ Start"):
        store.set_command(run=True)
        store.set_status(stopped_reason=None)
        st.rerun()
    if c2.button("■ Stop"):
        store.set_command(run=False)
        st.rerun()
    if c3.button("live ⇄ dry-run"):
        store.set_command(mode="dry_run" if mode == "live" else "live")
        st.rerun()
    if c4.button("🛑 KILL (cancel all + stop)"):
        store.set_command(kill=True)
        st.rerun()

    # ---- P&L ----
    pnl = store.pnl_today()
    st.metric("Realized P&L today (USD)", f"{pnl.realized_usd:.2f}")

    # ---- positions ----
    st.markdown("### Positions")
    positions = store.positions()
    if positions:
        st.dataframe([p.__dict__ for p in positions], use_container_width=True)
    else:
        st.caption("No open positions.")

    # ---- recent orders ----
    st.markdown("### Recent orders")
    orders = store.recent_orders(50)
    if orders:
        st.dataframe([o.__dict__ for o in orders], use_container_width=True)
    else:
        st.caption("No orders yet.")

    # ---- recent events ----
    st.markdown("### Recent events")
    events = store.recent_events(50)
    if events:
        st.dataframe([e.__dict__ for e in events], use_container_width=True)
    else:
        st.caption("No events yet.")


def main() -> None:  # pragma: no cover - Streamlit entry
    # Optional: surface configured limits read-only (never secrets).
    try:
        Settings.load("config.yaml", env={})  # validates config exists; secrets omitted
    except Exception:
        pass
    render(get_store())


if __name__ == "__main__":  # pragma: no cover - `streamlit run` executes as __main__
    main()
