"""Scrollable message list — renders all messages as HTML in a QTextBrowser."""

from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from cch.models.sessions import MessageView
from cch.ui.theme import COLORS, MONO_FAMILY
from cch.ui.widgets.message_widget import classify_message, render_message_html


class MessageList(QWidget):
    """Scrollable list of rendered conversation messages."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setReadOnly(True)
        layout.addWidget(self._browser)

        self._messages: list[MessageView] = []
        self._active_filters: set[str] = {
            "user",
            "assistant",
            "tool_call",
            "thinking",
            "tool_result",
            "system",
        }

    def set_messages(self, messages: list[MessageView]) -> None:
        """Set the full message list and render."""
        self._messages = messages
        self._render()

    def set_filters(self, filters: set[str]) -> None:
        """Update active filters and re-render."""
        self._active_filters = filters
        self._render()

    def _render(self) -> None:
        """Render all visible messages as a single HTML document."""
        parts: list[str] = []

        for msg in self._messages:
            categories = classify_message(msg)
            if not categories & self._active_filters:
                continue
            html = render_message_html(msg)
            if html:
                parts.append(html)

        body = "\n".join(parts) if parts else _empty_state()

        document = f"""<!DOCTYPE html>
<html><head><style>
body {{
    font-family: -apple-system, 'SF Pro Text', 'Helvetica Neue', sans-serif;
    font-size: 13px;
    color: {COLORS["text"]};
    line-height: 1.6;
    margin: 12px 16px;
    padding: 0;
}}
code {{
    font-family: {MONO_FAMILY};
    font-size: 12px;
    background-color: #F5F5F5;
    padding: 2px 5px;
    border-radius: 3px;
    border: 1px solid #EAEAEA;
}}
pre {{
    background-color: #F8F8F8;
    padding: 12px 14px;
    border-radius: 6px;
    border: 1px solid #EAEAEA;
    overflow-x: auto;
    font-family: {MONO_FAMILY};
    font-size: 12px;
    line-height: 1.5;
}}
pre code {{ background-color: transparent; padding: 0; border: none; }}
details > summary {{ list-style-type: none; }}
details > summary::-webkit-details-marker {{ display: none; }}
a {{ color: {COLORS["primary"]}; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
table {{ border-collapse: collapse; margin: 8px 0; }}
th, td {{ border: 1px solid {COLORS["border"]}; padding: 6px 10px; }}
th {{ background-color: {COLORS["panel_bg"]}; font-weight: 600; }}
</style></head><body>{body}</body></html>"""

        # Preserve scroll position
        scroll = self._browser.verticalScrollBar()
        pos = scroll.value() if scroll else 0

        self._browser.setHtml(document)

        if scroll and pos > 0:
            scroll.setValue(pos)

    def scroll_to_top(self) -> None:
        """Scroll to the top of the message list."""
        self._browser.verticalScrollBar().setValue(0)

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the message list."""
        scroll = self._browser.verticalScrollBar()
        scroll.setValue(scroll.maximum())


def _empty_state() -> str:
    return (
        f'<div style="text-align: center; padding: 60px 20px; '
        f'color: {COLORS["text_muted"]};">'
        f'<div style="font-size: 14px;">Select a session to view the conversation</div></div>'
    )
