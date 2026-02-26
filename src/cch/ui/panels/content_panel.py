"""Content panel — QStackedWidget housing all right-side views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from cch.models.sessions import SessionDetail
from cch.ui.theme import COLORS
from cch.ui.views.history_view import HistoryView
from cch.ui.views.search_view import SearchView
from cch.ui.views.statistics_view import StatisticsView

if TYPE_CHECKING:
    from cch.services.container import ServiceContainer


class EmptyStateView(QWidget):
    """Placeholder view shown when nothing is selected."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text = QLabel("Select a project and session to get started")
        text.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']};")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)

        hint = QLabel("Browse projects on the left, then pick a session")
        hint.setStyleSheet("font-size: 11px; color: #C0C0C0; margin-top: 4px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)


class ContentPanel(QStackedWidget):
    """Right-side content area with multiple views."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._empty_view = EmptyStateView()
        self._history_view = HistoryView()
        self._search_view = SearchView()
        self._statistics_view = StatisticsView()

        self.addWidget(self._empty_view)
        self.addWidget(self._history_view)
        self.addWidget(self._search_view)
        self.addWidget(self._statistics_view)

        # Wire search → session navigation
        self._search_view.session_requested.connect(self._on_search_session_requested)

        self._services: ServiceContainer | None = None
        self.setCurrentWidget(self._empty_view)

    def set_services(self, services: ServiceContainer) -> None:
        self._services = services
        self._search_view.set_services(services)
        self._statistics_view.set_services(services)

    def show_history(self) -> None:
        """Switch to the history/conversation view."""
        self.setCurrentWidget(self._history_view)

    def show_search(self) -> None:
        """Switch to the search view."""
        self.setCurrentWidget(self._search_view)
        self._search_view.focus_input()

    def show_statistics(self) -> None:
        """Switch to the statistics view."""
        self.setCurrentWidget(self._statistics_view)

    def show_session(self, detail: SessionDetail) -> None:
        """Display a session in the history view."""
        self._history_view.show_session(detail)
        self.setCurrentWidget(self._history_view)

    def focus_search(self) -> None:
        """Focus the search input."""
        self.setCurrentWidget(self._search_view)
        self._search_view.focus_input()

    def _on_search_session_requested(self, session_id: str) -> None:
        """Load a session from search results."""
        if not self._services:
            return
        from result import Ok

        from cch.ui.async_bridge import schedule

        services = self._services

        async def _load() -> None:
            result = await services.session_service.get_session_detail(session_id)
            if isinstance(result, Ok):
                self.show_session(result.ok_value)

        schedule(_load())
