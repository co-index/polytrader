"""PaperBroker: one strategy's isolated simulated account."""

from polytrader.config import RiskConfig
from polytrader.paper.broker import PaperBroker
from polytrader.risk import RiskManager
from polytrader.store import PnL, Position
from polytrader.strategy.base import MarketState, OrderIntent


def _mkt(best_bid=0.40, best_ask=0.40, mid=None) -> MarketState:
    return MarketState("m1", "t1", "Q?", best_bid=best_bid, best_ask=best_ask,
                       midpoint=mid if mid is not None else (best_bid + best_ask) / 2,
                       timestamp="2026-06-29T00:00:00")


def _buy(price, size=10.0):
    return OrderIntent(market_id="m1", token_id="t1", side="BUY", size=size, price=price)


def _sell(price, size=10.0):
    return OrderIntent(market_id="m1", token_id="t1", side="SELL", size=size, price=price)


def test_buy_opens_position_and_reduces_cash():
    b = PaperBroker("s", bankroll=1000.0)
    b.execute(_buy(0.40), _mkt(best_ask=0.40))
    pos = {p.token_id: p for p in b.positions()}
    assert pos["t1"].size == 10.0
    assert pos["t1"].avg_cost == 0.40
    assert b.cash == 1000.0 - 4.0


def test_second_buy_averages_cost():
    b = PaperBroker("s", bankroll=1000.0)
    b.execute(_buy(0.40), _mkt(best_ask=0.40))
    b.execute(_buy(0.50), _mkt(best_ask=0.50))
    pos = {p.token_id: p for p in b.positions()}
    assert pos["t1"].size == 20.0
    assert abs(pos["t1"].avg_cost - 0.45) < 1e-9


def test_sell_closes_and_books_realized_pnl():
    b = PaperBroker("s", bankroll=1000.0)
    b.execute(_buy(0.40), _mkt(best_ask=0.40))
    b.execute(_sell(0.50), _mkt(best_bid=0.50))
    assert abs(b.pnl_today().realized_usd - 1.0) < 1e-9  # (0.50-0.40)*10
    assert b.positions() == []  # flat
    s = b.summary()
    assert s["wins"] == 1 and s["trades"] == 1


def test_mark_to_market_sets_unrealized():
    b = PaperBroker("s", bankroll=1000.0)
    b.execute(_buy(0.40), _mkt(best_ask=0.40))
    b.mark_to_market([_mkt(best_bid=0.44, best_ask=0.46, mid=0.45)])
    assert abs(b.pnl_today().unrealized_usd - 0.5) < 1e-9  # (0.45-0.40)*10


def test_equity_is_cash_plus_marked_positions():
    b = PaperBroker("s", bankroll=1000.0)
    b.execute(_buy(0.40), _mkt(best_ask=0.40))
    b.mark_to_market([_mkt(mid=0.45)])
    s = b.summary()
    assert abs(s["equity"] - (996.0 + 10 * 0.45)) < 1e-9
    assert abs(s["total_pnl"] - 0.5) < 1e-9


def test_exposes_store_shaped_reads():
    b = PaperBroker("s")
    b.execute(_buy(0.40), _mkt(best_ask=0.40))
    assert all(isinstance(p, Position) for p in b.positions())
    assert isinstance(b.pnl_today(), PnL)


def test_risk_manager_accepts_the_broker():
    b = PaperBroker("s", bankroll=1000.0)
    b.execute(_buy(0.40), _mkt(best_ask=0.40))  # exposure 4.0
    risk = RiskManager(
        RiskConfig(per_order_max_usd=5, total_exposure_max_usd=50,
                   daily_loss_limit_usd=20, market_whitelist=["m1"]),
        b,
    )
    assert risk.check(_buy(0.40, size=1.0)).approved
    assert not risk.check(_buy(0.40, size=100.0)).approved  # per-order cap


def test_summary_has_all_leaderboard_keys():
    s = PaperBroker("s").summary()
    for k in ("name", "equity", "total_pnl", "realized", "unrealized",
              "fills", "positions", "wins", "trades", "rejects"):
        assert k in s


def test_records_a_filled_order_in_the_log():
    b = PaperBroker("s", bankroll=1000.0)
    b.execute(_buy(0.40), _mkt(best_ask=0.40), ts="2026-06-29T01:00:00")
    log = b.orders()
    assert len(log) == 1
    o = log[0]
    assert o["ts"] == "2026-06-29T01:00:00"
    assert o["token_id"] == "t1" and o["side"] == "BUY"
    assert o["size"] == 10.0 and o["price"] == 0.40
    assert o["status"] == "filled"


def test_logs_an_unfilled_order_as_resting():
    b = PaperBroker("s", bankroll=1000.0)
    # BUY below the ask is placed but not marketable -> logged as a resting order.
    b.execute(_buy(0.39), _mkt(best_ask=0.42))
    log = b.orders()
    assert len(log) == 1
    assert log[0]["status"] == "resting"
    assert log[0]["price"] == 0.39
    # ...and it did not move cash or positions.
    assert b.cash == 1000.0 and b.positions() == []


def test_logs_a_rejected_order_and_counts_it():
    b = PaperBroker("s", bankroll=1000.0)
    b.record_rejected(_buy(0.39), ts="2026-06-29T02:00:00", reason="cap")
    log = b.orders()
    assert len(log) == 1
    assert log[0]["status"] == "rejected"
    assert b.summary()["rejects"] == 1
