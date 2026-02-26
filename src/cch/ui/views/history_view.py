"""History view — full session viewer using WebEngine."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from cch.models.sessions import SessionDetail
from cch.ui.widgets.message_webview import MessageWebView


class HistoryView(QWidget):
    """Full conversation viewer — delegates entirely to MessageWebView."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._webview = MessageWebView()
        layout.addWidget(self._webview)

    def show_session(
        self,
        detail: SessionDetail,
        *,
        focus_message_uuid: str = "",
    ) -> None:
        """Display a full session."""
        self._webview.show_session(detail, focus_message_uuid=focus_message_uuid)

    def dispose(self) -> None:
        """Release webview resources during shutdown."""
        self._webview.dispose()
