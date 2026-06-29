"""Smoke test: the dashboard renders against a populated store without error and
shows engine status — using Streamlit's official AppTest harness.
"""

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


def _seed(db_path: str):
    store = Store(db_path)
    store.init_schema()
    store.set_command(run=True, mode="dry_run")
    store.record_order(Order(
        ts="2026-06-29T00:00:00", market_id="m1", token_id="t1", side="BUY",
        size=1.0, price=0.4, mode="dry_run", status="placed"))
    store.log_event("info", "engine", "started")


def test_dashboard_renders_and_shows_status(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    _seed(db)
    monkeypatch.setenv("POLYTRADER_DB", db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()

    assert not at.exception
    titles = [t.value for t in at.title]
    assert "polytrader" in titles
    # Default language is English: the running/mode banner is a subheader.
    assert any("RUNNING" in s.value for s in at.subheader)


def test_dashboard_switches_to_chinese(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    _seed(db)
    monkeypatch.setenv("POLYTRADER_DB", db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    at.selectbox(key="lang").set_value("中文").run()

    assert not at.exception
    # The status banner and a section header are now Chinese.
    assert any("运行中" in s.value for s in at.subheader)
    assert any("持仓" in m.value for m in at.markdown)


def test_dashboard_shows_paper_leaderboard(tmp_path, monkeypatch):
    db = str(tmp_path / "dash.db")
    paper_db = str(tmp_path / "paper.db")
    _seed(db)
    _seed_paper(paper_db)
    monkeypatch.setenv("POLYTRADER_DB", db)
    monkeypatch.setenv("POLYTRADER_PAPER_DB", paper_db)

    at = AppTest.from_file("src/polytrader/dashboard.py", default_timeout=30)
    at.run()
    assert not at.exception
    # English leaderboard header present by default.
    assert any("leaderboard" in m.value.lower() for m in at.markdown)

    # Switch to Chinese: the leaderboard header is translated.
    at.selectbox(key="lang").set_value("中文").run()
    assert any("排行榜" in m.value for m in at.markdown)
