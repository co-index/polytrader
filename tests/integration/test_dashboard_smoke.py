"""Smoke test: the dashboard renders against a populated store without error and
shows engine status — using Streamlit's official AppTest harness.
"""

from datetime import UTC, datetime

import pytest

from polytrader.paper.store import PaperStore
from polytrader.store import Order, Store

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _seed_paper(db_path: str):
    ps = PaperStore(db_path)
    ps.init_schema()
    ps.write_leaderboard([{
        "name": "market_making", "equity": 1002.5, "total_pnl": 2.5, "realized": 1.0,
        "unrealized": 1.5, "fills": 4, "positions": 1, "wins": 1, "trades": 1, "rejects": 0,
    }], ts="t1")
    ps.write_orders("market_making", [
        {"ts": "t1", "token_id": "alpha", "side": "BUY", "size": 5.0,
         "price": 0.40, "status": "filled"},
        {"ts": "t2", "token_id": "beta", "side": "SELL", "size": 5.0,
         "price": 0.55, "status": "filled"},
    ])


def _seed(db_path: str, *, with_heartbeat: bool = True):
    store = Store(db_path)
    store.init_schema()
    store.set_command(run=True, mode="dry_run")
    if with_heartbeat:  # simulate a live engine that just ticked
        store.set_status(last_tick_ts=datetime.now(UTC).isoformat())
    store.record_order(Order(
        ts="2026-06-29T00:00:00", market_id="m1", token_id="t1", side="BUY",
        size=1.0, price=0.4, mode="dry_run", status="placed"))
    store.log_event("info", "engine", "started")


def test_run_flag_without_heartbeat_is_not_shown_as_running(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    _seed(db, with_heartbeat=False)  # commanded on, but no engine ticking
    monkeypatch.setenv("POLYTRADER_DB", db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    assert not at.exception
    # Must NOT claim 运行中; shows the no-heartbeat state instead.
    assert any("无心跳" in s.value for s in at.subheader)
    assert not any("· 运行中 ·" in s.value for s in at.subheader)


def test_dashboard_renders_and_shows_status(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    _seed(db)
    monkeypatch.setenv("POLYTRADER_DB", db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()

    assert not at.exception
    titles = [t.value for t in at.title]
    assert "polytrader" in titles
    # Default language is Chinese: the running/mode banner is a subheader.
    assert any("运行中" in s.value for s in at.subheader)


def test_run_toggle_button_flips_run_state(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    _seed(db)  # seeds run=True
    monkeypatch.setenv("POLYTRADER_DB", db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    btn = at.button(key="run_toggle")
    assert "停止" in btn.label  # running -> single button offers Stop
    btn.click().run()
    assert not at.exception
    assert Store(db).get_engine_state().run is False  # one button toggled it off


def test_dashboard_switches_to_english(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    _seed(db)
    monkeypatch.setenv("POLYTRADER_DB", db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    # Default is Chinese.
    assert any("运行中" in s.value for s in at.subheader)
    assert any("持仓" in m.value for m in at.markdown)

    # Switching to English flips the whole page back.
    at.selectbox(key="lang").set_value("English").run()
    assert not at.exception
    assert any("RUNNING" in s.value for s in at.subheader)


def test_paper_lab_heartbeat_reflects_runner(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    paper_db = str(tmp_path / "paper.db")
    _seed(db)
    monkeypatch.setenv("POLYTRADER_DB", db)
    monkeypatch.setenv("POLYTRADER_PAPER_DB", paper_db)

    # Fresh snapshot -> Paper Lab shown as running.
    ps = PaperStore(paper_db)
    ps.init_schema()
    ps.write_leaderboard([{
        "name": "momentum", "equity": 1000.0, "total_pnl": 0.0, "realized": 0.0,
        "unrealized": 0.0, "fills": 0, "positions": 0, "wins": 0, "trades": 0, "rejects": 0,
    }], ts=datetime.now(UTC).isoformat())

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert any("运行中" in m.value for m in at.markdown)

    # Stale snapshot -> Paper Lab shown as idle.
    ps.write_leaderboard([{
        "name": "momentum", "equity": 1000.0, "total_pnl": 0.0, "realized": 0.0,
        "unrealized": 0.0, "fills": 0, "positions": 0, "wins": 0, "trades": 0, "rejects": 0,
    }], ts="2026-06-30T00:00:00")
    at.run()
    assert any("未运行" in m.value for m in at.markdown)


def test_dashboard_shows_paper_leaderboard_with_semantic_names(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    paper_db = str(tmp_path / "paper.db")
    _seed(db)
    _seed_paper(paper_db)
    monkeypatch.setenv("POLYTRADER_DB", db)
    monkeypatch.setenv("POLYTRADER_PAPER_DB", paper_db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    assert not at.exception
    # Chinese leaderboard section header present, plus the paper-only note.
    headings = [h.value for h in at.header] + [m.value for m in at.markdown]
    assert any("排行榜" in h for h in headings)
    assert any("模拟数据" in c.value for c in at.caption)
    # The strategy name is a clickable (link-style) button, not a raw identifier.
    labels = [b.label for b in at.button]
    assert "做市/价差捕获" in labels
    assert "market_making" not in labels


def test_clicking_a_strategy_row_pops_up_its_trades_with_search(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    paper_db = str(tmp_path / "paper.db")
    _seed(db)
    _seed_paper(paper_db)  # market_making has two fills: alpha BUY, beta SELL
    monkeypatch.setenv("POLYTRADER_DB", db)
    monkeypatch.setenv("POLYTRADER_PAPER_DB", paper_db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    assert not at.exception
    # Click the strategy row -> its trades open in a modal popup with a search box.
    # (In-modal search is covered by the _filter_orders unit test; AppTest can't drive a
    # second interaction inside an st.dialog.)
    at.button(key="lb_row_market_making").click().run()
    assert not at.exception
    trades = " ".join(str(d.value.to_dict(orient="list")) for d in at.dataframe)
    assert "alpha" in trades and "beta" in trades
    assert at.text_input(key="trade_search") is not None


def _seed_basket(db_path: str, *, fresh: bool = True):
    from polytrader.basket import BasketStore
    bs = BasketStore(db_path)
    bs.init_schema()
    ts = datetime.now(UTC).isoformat() if fresh else "2026-06-30T00:00:00+00:00"
    bs.write_cycle(ts, [
        {"title": "Where will talks be held?", "slug": "talks-loc", "n_legs": 19,
         "sum_ask": 0.978, "sum_bid": 0.85, "buy_depth": 5.0, "sell_depth": 3.0,
         "vol24": 108690.0},
        {"title": "Portugal vs. Croatia", "slug": "por-cro", "n_legs": 3,
         "sum_ask": 1.015, "sum_bid": 1.0075, "buy_depth": 16317.0,
         "sell_depth": 900.0, "vol24": 5000000.0},
    ])
    bs.append_opps([
        {"ts": ts, "side": "buy", "edge": 0.022, "depth": 5.0, "profit_cap": 0.11,
         "title": "Where will talks be held?", "slug": "talks-loc",
         "sum_ask": 0.978, "sum_bid": 0.85},
    ])


def test_basket_scanner_section_shows_snapshot_and_opps(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    basket_db = str(tmp_path / "basket.db")
    _seed(db)
    _seed_basket(basket_db)
    monkeypatch.setenv("POLYTRADER_DB", db)
    monkeypatch.setenv("POLYTRADER_PAPER_DB", str(tmp_path / "paper.db"))
    monkeypatch.setenv("POLYTRADER_BASKET_DB", basket_db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    assert not at.exception
    headings = [h.value for h in at.header]
    assert any("篮子" in h for h in headings)
    # Fresh cycle -> scanner shown as running.
    assert any("扫描器运行中" in m.value for m in at.markdown)
    # Snapshot table carries the events and polymarket links; opp log has the buy opp.
    tables = " ".join(str(d.value.to_dict(orient="list")) for d in at.dataframe)
    assert "Portugal vs. Croatia" in tables
    assert "polymarket.com/event/talks-loc" in tables
    assert "0.978" in tables


def test_basket_scanner_idle_without_fresh_cycle(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    basket_db = str(tmp_path / "basket.db")
    _seed(db)
    _seed_basket(basket_db, fresh=False)
    monkeypatch.setenv("POLYTRADER_DB", db)
    monkeypatch.setenv("POLYTRADER_PAPER_DB", str(tmp_path / "paper.db"))
    monkeypatch.setenv("POLYTRADER_BASKET_DB", basket_db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    assert not at.exception
    assert any("扫描器未运行" in m.value for m in at.markdown)
