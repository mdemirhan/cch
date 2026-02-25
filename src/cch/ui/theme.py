"""Theme, color definitions, and display formatting utilities."""

from __future__ import annotations

from datetime import UTC, datetime

# Color palette — professional dark theme with blue accents
COLORS = {
    "primary": "#3B82F6",  # Blue 500
    "secondary": "#10B981",  # Emerald 500
    "accent": "#F59E0B",  # Amber 500
    "success": "#10B981",  # Emerald 500
    "warning": "#F59E0B",  # Amber 500
    "error": "#EF4444",  # Red 500
    "bg": "#0F172A",  # Slate 900
    "surface": "#1E293B",  # Slate 800
    "surface_light": "#334155",  # Slate 700
    "text": "#F1F5F9",  # Slate 100
    "text_muted": "#94A3B8",  # Slate 400
    "border": "#475569",  # Slate 600
}

# Chart color palette
CHART_COLORS = [
    "#3B82F6",  # Blue
    "#10B981",  # Emerald
    "#F59E0B",  # Amber
    "#EF4444",  # Red
    "#8B5CF6",  # Violet
    "#06B6D4",  # Cyan
    "#EC4899",  # Pink
    "#84CC16",  # Lime
    "#F97316",  # Orange
    "#14B8A6",  # Teal
]


def format_datetime(iso_str: str) -> str:
    """Format an ISO datetime string into a human-friendly display.

    Examples: "Today 14:30", "Yesterday 09:15", "Feb 12 16:45", "2025-11-03 10:00"
    """
    if not iso_str:
        return ""
    try:
        # Parse ISO format (handles both "T" separator and space)
        cleaned = iso_str.replace("T", " ")[:19]
        dt = datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return iso_str[:19] if len(iso_str) >= 19 else iso_str

    now = datetime.now(tz=UTC).replace(tzinfo=None)
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
