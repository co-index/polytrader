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
    "st_filled": {"en": "filled", "zh": "成交"},
    "st_resting": {"en": "resting", "zh": "挂单"},
    "st_rejected": {"en": "rejected", "zh": "拒单"},
    "paper_lab_note": {
        "en": "Always simulated, independent of the engine's live/dry-run mode. "
              "Real trades appear under Live engine above.",
        "zh": "始终是模拟数据，与引擎的实盘/模拟模式无关。实盘成交见上方「实盘引擎」。",
    },
    "language": {"en": "Language", "zh": "语言"},
}


# Human-readable strategy names for the leaderboard, keyed by each strategy's `name`.
STRATEGY_LABELS: dict[str, dict[str, str]] = {
    "market_making": {"en": "Market making", "zh": "做市/价差捕获"},
    "mean_reversion": {"en": "Mean reversion", "zh": "均值回归"},
    "momentum": {"en": "Momentum", "zh": "动量/趋势"},
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
