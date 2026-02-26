"""Theme, color definitions, QSS stylesheet, and display formatting utilities."""

from __future__ import annotations

from datetime import UTC, datetime

# ── Color palette — light theme with orange accents ──

COLORS = {
    "primary": "#E67E22",
    "primary_light": "#FFF3E0",
    "success": "#27AE60",
    "provider_claude": "#E67E22",
    "provider_codex": "#2D7FF9",
    "provider_gemini": "#16A085",
    "bg": "#FFFFFF",
    "sidebar_bg": "#F0F0F0",
    "panel_bg": "#FAFAFA",
    "border": "#E0E0E0",
    "text": "#1A1A1A",
    "text_muted": "#999999",
    "user_bg": "#FFF8F0",
    "user_border": "#E67E22",
    "assistant_bg": "#FFFFFF",
    "assistant_border": "#27AE60",
    "error": "#E74C3C",
    "warning": "#F39C12",
}

CHART_COLORS = [
    "#E67E22",
    "#27AE60",
    "#3498DB",
    "#E74C3C",
    "#9B59B6",
    "#1ABC9C",
    "#E91E63",
    "#8BC34A",
    "#FF9800",
    "#00BCD4",
]

# ── Fonts ──

FONT_FAMILY = "-apple-system, 'SF Pro Text', 'Helvetica Neue', 'Segoe UI', Roboto, sans-serif"
MONO_FAMILY = "'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

# ── QSS Stylesheet ──


def build_stylesheet() -> str:
    """Build the application-wide QSS stylesheet."""
    c = COLORS
    return f"""
/* ── Global ── */
QWidget {{
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {c["text"]};
    background-color: {c["bg"]};
}}

/* ── Main window ── */
QMainWindow {{
    background-color: {c["bg"]};
}}

/* ── Status bar ── */
QStatusBar {{
    background-color: {c["panel_bg"]};
    border-top: 1px solid {c["border"]};
    font-size: 12px;
    color: {c["text_muted"]};
    padding: 4px 12px;
}}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {c["border"]};
    width: 1px;
}}
QSplitter::handle:hover {{
    background-color: {c["primary"]};
}}

/* ── Scroll bars ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #D0D0D0;
    min-height: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #B0B0B0;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #D0D0D0;
    min-width: 30px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #B0B0B0;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── List views ── */
QListView {{
    background-color: {c["panel_bg"]};
    border: none;
    outline: none;
}}
QListView::item {{
    padding: 0;
    border: none;
}}
QListView::item:selected {{
    background-color: transparent;
}}
QListView::item:hover:!selected {{
    background-color: transparent;
}}

/* ── Text browser (message content) ── */
QTextBrowser {{
    background-color: {c["bg"]};
    border: none;
    font-size: 13px;
}}

/* ── WebEngine view ── */
QWebEngineView {{
    background-color: {c["bg"]};
    border: none;
}}

/* ── Line edits ── */
QLineEdit {{
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 8px 12px;
    background-color: {c["bg"]};
    font-size: 13px;
}}
QLineEdit:focus {{
    border-color: {c["primary"]};
}}

/* ── Push buttons ── */
QPushButton {{
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 6px 14px;
    background-color: {c["bg"]};
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {c["panel_bg"]};
    border-color: #CCC;
}}
QPushButton:pressed {{
    background-color: {c["border"]};
}}

/* ── Combo box ── */
QComboBox {{
    border: 1px solid {c["border"]};
    border-radius: 6px;
    padding: 5px 10px;
    background-color: {c["bg"]};
    font-size: 13px;
}}
QComboBox:hover {{
    border-color: {c["primary"]};
}}

/* ── Labels ── */
QLabel {{
    background-color: transparent;
}}

/* ── Tab bar ── */
QTabBar::tab {{
    padding: 6px 16px;
    border: none;
    border-bottom: 2px solid transparent;
    color: {c["text_muted"]};
    font-size: 12px;
}}
QTabBar::tab:selected {{
    color: {c["primary"]};
    border-bottom-color: {c["primary"]};
}}
QTabBar::tab:hover:!selected {{
    color: {c["text"]};
}}

/* ── Dialog ── */
QDialog {{
    background-color: {c["bg"]};
}}
"""


# ── Format helpers ──


def _parse_iso_datetime(iso_str: str) -> datetime | None:
    """Parse common ISO datetime formats and normalize to UTC."""
    value = iso_str.strip()
    if not value:
        return None

    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    if " " in value and "T" not in value:
        value = value.replace(" ", "T")

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        try:
            dt = datetime.fromisoformat(value[:19])
        except ValueError:
            return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_datetime(iso_str: str) -> str:
    """Format an ISO datetime string into a human-friendly display.

    Examples: "Today 14:30", "Yesterday 09:15", "Feb 12 16:45", "2025-11-03 10:00"
    """
    if not iso_str:
        return ""
    dt = _parse_iso_datetime(iso_str)
    if dt is None:
        return iso_str[:19] if len(iso_str) >= 19 else iso_str

    now = datetime.now(tz=UTC)
    today = now.date()
    dt_date = dt.date()
    time_part = dt.strftime("%H:%M")

    if dt_date == today:
        return f"Today {time_part}"
    delta = (today - dt_date).days
    if delta == 1:
        return f"Yesterday {time_part}"
    if delta < 7:
        return f"{dt.strftime('%A')} {time_part}"
    if dt.year == now.year:
        return f"{dt.strftime('%b %d')} {time_part}"
    return f"{dt.strftime('%Y-%m-%d')} {time_part}"


def format_relative_time(iso_str: str) -> str:
    """Format an ISO datetime as relative time (e.g. '2h ago', '3d ago')."""
    if not iso_str:
        return ""
    dt = _parse_iso_datetime(iso_str)
    if dt is None:
        return iso_str[:19] if len(iso_str) >= 19 else iso_str

    now = datetime.now(tz=UTC)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds <= 0:
        return "just now"

    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 30:
        return f"{days}d ago"
    months = days // 30
    if months < 12:
        return f"{months}mo ago"
    return f"{days // 365}y ago"


def format_duration_ms(ms: int) -> str:
    """Format milliseconds into a human-friendly duration.

    Examples: "2s", "3m 12s", "1h 5m", "2h 30m", "1d 4h"
    """
    if ms <= 0:
        return ""
    total_seconds = ms // 1000
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    if minutes < 60:
        return f"{minutes}m {seconds}s" if seconds else f"{minutes}m"
    hours = minutes // 60
    remaining_mins = minutes % 60
    if hours < 24:
        return f"{hours}h {remaining_mins}m" if remaining_mins else f"{hours}h"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours}h" if remaining_hours else f"{days}d"


def format_tokens(count: int) -> str:
    """Format a token count with K/M suffixes for readability."""
    if count < 1000:
        return str(count)
    if count < 1_000_000:
        return f"{count / 1000:.1f}K"
    return f"{count / 1_000_000:.1f}M"


def format_cost(amount: float) -> str:
    """Format a dollar amount."""
    if amount < 0.01:
        return f"${amount:.4f}"
    return f"${amount:.2f}"


def provider_label(provider: str) -> str:
    """Map provider ID to display label."""
    normalized = provider.strip().lower()
    match normalized:
        case "codex":
            return "Codex"
        case "gemini":
            return "Gemini"
        case _:
            return "Claude"


def provider_color(provider: str) -> str:
    """Map provider ID to provider color."""
    normalized = provider.strip().lower()
    match normalized:
        case "codex":
            return COLORS["provider_codex"]
        case "gemini":
            return COLORS["provider_gemini"]
        case _:
            return COLORS["provider_claude"]
