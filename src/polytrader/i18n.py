"""Bilingual UI strings for the dashboard (English / 中文).

A single flat table maps a stable key to one string per language. The dashboard
references keys, never literals, so switching languages never touches layout code.
`t()` degrades gracefully: an unknown language falls back to English, and an unknown
key returns the key itself (visible but non-fatal — a missing translation never
crashes the UI).
"""

from __future__ import annotations

# Display name -> language code. Order is the order shown in the language picker.
LANGUAGES: dict[str, str] = {"English": "en", "中文": "zh"}

_DEFAULT = "en"

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
    "language": {"en": "Language", "zh": "语言"},
}


def t(key: str, lang: str = _DEFAULT) -> str:
    """Look up a UI string by key for the given language code (e.g. "en", "zh")."""
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    return entry.get(lang) or entry.get(_DEFAULT) or key
