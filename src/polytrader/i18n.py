"""Bilingual UI strings for the dashboard (English / 中文).

A single flat table maps a stable key to one string per language. The dashboard
references keys, never literals, so switching languages never touches layout code.
`t()` degrades gracefully: an unknown language falls back to English, and an unknown
key returns the key itself (visible but non-fatal — a missing translation never
crashes the UI).
"""

from __future__ import annotations

# Display name -> language code. Order is the order shown in the language picker; the
# first entry is the default, so 中文 leads.
LANGUAGES: dict[str, str] = {"中文": "zh", "English": "en"}

_DEFAULT = "zh"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "running": {"en": "RUNNING", "zh": "运行中"},
    "stopped": {"en": "STOPPED", "zh": "已停止"},
    "no_heartbeat": {"en": "ENABLED · no heartbeat (engine not ticking)",
                     "zh": "已启用 · 无心跳(引擎未在运行)"},
    "mode": {"en": "mode", "zh": "模式"},
    "live_warning": {"en": "⚠️ LIVE — real funds", "zh": "⚠️ 实盘 — 真实资金"},
    "dry_run_note": {"en": "🧪 dry-run (simulated)", "zh": "🧪 模拟盘（仿真）"},
    "stopped_reason": {"en": "Stopped: {reason}", "zh": "已停止：{reason}"},
    "start": {"en": "▶ Start", "zh": "▶ 启动"},
    "stop": {"en": "■ Stop", "zh": "■ 停止"},
    "toggle_mode": {"en": "live ⇄ dry-run", "zh": "实盘 ⇄ 模拟盘"},
    "kill": {"en": "🛑 KILL (cancel all + stop)", "zh": "🛑 急停（撤单并停止）"},
    "pnl_today": {"en": "Realized P&L today (USD)", "zh": "今日已实现盈亏（美元）"},
    "positions": {"en": "Positions", "zh": "持仓"},
    "no_positions": {"en": "No open positions.", "zh": "暂无持仓。"},
    "recent_orders": {"en": "Recent orders", "zh": "近期订单"},
    "no_orders": {"en": "No orders yet.", "zh": "暂无订单。"},
    "recent_events": {"en": "Recent events", "zh": "近期事件"},
    "no_events": {"en": "No events yet.", "zh": "暂无事件。"},
    "leaderboard": {"en": "Strategy leaderboard (paper)", "zh": "策略排行榜（模拟）"},
    "no_paper": {"en": "No paper results yet.", "zh": "暂无模拟结果。"},
    "col_strategy": {"en": "strategy", "zh": "策略"},
    "col_equity": {"en": "equity", "zh": "权益"},
    "col_total_pnl": {"en": "total P&L", "zh": "总盈亏"},
    "col_realized": {"en": "realized", "zh": "已实现"},
    "col_unrealized": {"en": "unrealized", "zh": "未实现"},
    "col_fills": {"en": "fills", "zh": "成交"},
    "col_positions": {"en": "positions", "zh": "持仓"},
    "col_win_rate": {"en": "win rate", "zh": "胜率"},
    "col_rejects": {"en": "rejects", "zh": "拒单"},
    "auto_refresh": {"en": "Auto-refresh", "zh": "自动刷新"},
    "live_engine": {"en": "Live engine", "zh": "实盘引擎"},
    "paper_running": {"en": "🟢 Paper Lab running", "zh": "🟢 Paper Lab 运行中"},
    "paper_idle": {"en": "🔴 Paper Lab idle (no runner)", "zh": "🔴 Paper Lab 未运行（无 runner）"},
    "src_replay": {"en": "🟣 REPLAY — synthetic prices (not real market data)",
                   "zh": "🟣 回放模拟 — 合成行情(非真实市场数据)"},
    "src_live": {"en": "📡 live market data", "zh": "📡 真实行情"},
    "updated_ago": {"en": "updated {s}s ago", "zh": "更新于 {s} 秒前"},
    "order_details": {"en": "Order details", "zh": "订单详情"},
    "click_row_hint": {
        "en": "Click a row to see that strategy's trades.",
        "zh": "点击某一行查看该策略的全部交易。",
    },
    "close": {"en": "✕ Close", "zh": "✕ 关闭"},
    "refresh": {"en": "🔄 Refresh", "zh": "🔄 刷新"},
    "search": {"en": "Search (token / side / status …)", "zh": "搜索（token / 方向 / 状态 …）"},
    "ord_time": {"en": "time", "zh": "时间"},
    "ord_token": {"en": "token", "zh": "token"},
    "ord_side": {"en": "side", "zh": "方向"},
    "ord_size": {"en": "size", "zh": "数量"},
    "ord_price": {"en": "price", "zh": "价格"},
    "ord_status": {"en": "status", "zh": "状态"},
    "ord_pnl": {"en": "P&L", "zh": "盈亏"},
    "st_filled": {"en": "filled", "zh": "成交"},
    "st_resting": {"en": "resting", "zh": "挂单"},
    "st_rejected": {"en": "rejected", "zh": "拒单"},
    "paper_lab_note": {
        "en": "Always simulated, independent of the engine's live/dry-run mode. "
              "Real trades appear under Live engine above.",
        "zh": "始终是模拟数据，与引擎的实盘/模拟模式无关。实盘成交见上方「实盘引擎」。",
    },
    "language": {"en": "Language", "zh": "语言"},
    "basket_title": {"en": "Basket-arb scanner (read-only)",
                     "zh": "篮子套利扫描（只读）"},
    "basket_note": {
        # NB: "\\$" — a bare "$…$" pair would be rendered as LaTeX by st.caption.
        "en": "A basket = one YES share of every outcome in a multi-outcome event; "
              "it always pays \\$1 at resolution. Σask < 1 → buying the basket locks "
              "a profit; Σbid > 1 → minting a set for \\$1 and selling every leg "
              "does. Scans real Polymarket books every 5 min; never places orders.",
        "zh": "篮子 = 买齐一个多结果事件的全部结果各一份，结算时必定赔付 \\$1。"
              "Σask < 1 → 买入篮子锁定利润；Σbid > 1 → 花 \\$1 铸一套后全部卖出锁定利润。"
              "每 5 分钟扫描真实 Polymarket 订单簿，只读、从不下单。",
    },
    "basket_running": {"en": "🟢 Scanner running", "zh": "🟢 扫描器运行中"},
    "basket_idle": {"en": "🔴 Scanner idle (no recent cycle)",
                    "zh": "🔴 扫描器未运行（无最近扫描）"},
    "basket_last_scan": {"en": "latest cycle: {n} events priced",
                         "zh": "最新一轮：完整定价 {n} 个事件"},
    "basket_opps_title": {"en": "Opportunity log (edge ≥ 0.5c)",
                          "zh": "机会流水（边际 ≥ 0.5 美分）"},
    "basket_no_opps": {"en": "No opportunities logged yet.", "zh": "暂无套利机会记录。"},
    "basket_latest_title": {"en": "Latest full scan (cheapest basket first)",
                            "zh": "最新一轮全景（Σask 低者在前）"},
    "basket_no_data": {"en": "No scan data yet.", "zh": "暂无扫描数据。"},
    "bk_event": {"en": "event", "zh": "事件"},
    "bk_legs": {"en": "outcomes", "zh": "结果数"},
    "bk_sum_ask": {"en": "Σask (buy cost)", "zh": "Σask（买入成本）"},
    "bk_sum_bid": {"en": "Σbid (sell value)", "zh": "Σbid（卖出所得）"},
    "bk_buy_depth": {"en": "buy depth", "zh": "可买深度"},
    "bk_sell_depth": {"en": "sell depth", "zh": "可卖深度"},
    "bk_vol24": {"en": "24h volume", "zh": "24h 成交量"},
    "bk_link": {"en": "link", "zh": "链接"},
    "bk_time": {"en": "time", "zh": "时间"},
    "bk_side": {"en": "direction", "zh": "方向"},
    "bk_edge": {"en": "edge / $1", "zh": "边际 / $1"},
    "bk_depth": {"en": "depth (sets)", "zh": "深度（套）"},
    "bk_cap": {"en": "profit cap ($)", "zh": "利润上限（$）"},
    "bk_buy": {"en": "buy basket", "zh": "买入篮子"},
    "bk_sell": {"en": "mint & sell", "zh": "铸套卖出"},
}


# Human-readable strategy names for the leaderboard, keyed by each strategy's `name`.
STRATEGY_LABELS: dict[str, dict[str, str]] = {
    "market_making": {"en": "Market making", "zh": "做市/价差捕获"},
    "mean_reversion": {"en": "Mean reversion", "zh": "均值回归"},
    "momentum": {"en": "Momentum", "zh": "动量/趋势"},
    "follow": {"en": "Copy-follow", "zh": "跟单"},
    "complementary_arb": {"en": "Complementary arb", "zh": "互补结果套利"},
    "example": {"en": "Example (baseline)", "zh": "示例（基准）"},
}


def t(key: str, lang: str = _DEFAULT) -> str:
    """Look up a UI string by key for the given language code (e.g. "en", "zh")."""
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry.get(_DEFAULT) or key


def strategy_label(name: str, lang: str = _DEFAULT) -> str:
    """Semantic, localized display name for a strategy; falls back to the raw name."""
    entry = STRATEGY_LABELS.get(name)
    if entry is None:
        return name
    return entry.get(lang) or entry.get(_DEFAULT) or name
