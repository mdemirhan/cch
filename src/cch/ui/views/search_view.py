"""Search view — search input + filter chips + results list + detail navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from result import Ok

from cch.models.search import SearchResult
from cch.ui.async_bridge import async_slot
from cch.ui.theme import COLORS
from cch.ui.widgets.delegates import SearchResultDelegate

if TYPE_CHECKING:
    from cch.services.container import ServiceContainer

# Filter definitions: (key, label, color)
_SEARCH_FILTERS = [
    ("user", "User", "#E67E22"),
    ("assistant", "Assistant", "#27AE60"),
    ("system", "System", "#F39C12"),
]


class SearchResultModel(QAbstractListModel):
    """Model for search results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[SearchResult] = []

    def set_results(self, results: list[SearchResult]) -> None:
        self.beginResetModel()
        self._results = results
        self.endResetModel()

    def result_at(self, index: int) -> SearchResult | None:
        if 0 <= index < len(self._results):
            return self._results[index]
        return None

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._results)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or index.row() >= len(self._results):
            return None
        r = self._results[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return r.snippet
        if role == Qt.ItemDataRole.UserRole:
            return r.session_id
        if role == Qt.ItemDataRole.UserRole + 1:
            return r.role
        if role == Qt.ItemDataRole.UserRole + 2:
            return r.project_name
        if role == Qt.ItemDataRole.UserRole + 3:
            return r.timestamp
        return None


class _FilterChip(QPushButton):
    """A toggleable filter chip button."""

    def __init__(self, key: str, label: str, color: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.key = key
        self._color = color
        self._active = True
        self.setCheckable(True)
        self.setChecked(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._on_toggled)
        self._apply_style()

    def _on_toggled(self, checked: bool) -> None:
        self._active = checked
        self._apply_style()

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                f"QPushButton {{ "
                f"  background-color: {self._color}; color: white; "
                f"  border: none; border-radius: 12px; padding: 4px 12px; "
                f"  font-size: 12px; font-weight: 600; "
                f"}} "
                f"QPushButton:hover {{ opacity: 0.9; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ "
                f"  background-color: transparent; color: {COLORS['text_muted']}; "
                f"  border: 1px solid {COLORS['border']}; border-radius: 12px; "
                f"  padding: 4px 12px; font-size: 12px; "
                f"}} "
                f"QPushButton:hover {{ "
                f"  border-color: {self._color}; color: {self._color}; "
                f"}}"
            )

    @property
    def active(self) -> bool:
        return self._active


class SearchView(QWidget):
    """Search input + filter chips + results list."""

    session_requested = Signal(str)  # session_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services: ServiceContainer | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("\U0001f50d Search")
        header.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(header)

        # Search bar
        bar_layout = QHBoxLayout()
        bar_layout.setSpacing(8)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search messages...")
        self._input.returnPressed.connect(self._do_search)
        bar_layout.addWidget(self._input, stretch=1)

        self._search_btn = QPushButton("Search")
        self._search_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color: {COLORS['primary']}; color: white; "
            f"  border: none; border-radius: 6px; padding: 6px 16px; "
            f"  font-weight: bold; "
            f"}} "
            f"QPushButton:hover {{ background-color: #D35400; }}"
        )
        self._search_btn.clicked.connect(self._do_search)
        bar_layout.addWidget(self._search_btn)

        layout.addLayout(bar_layout)

        # Filter chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        chips_layout.setContentsMargins(0, 2, 0, 2)

        filter_label = QLabel("Filter:")
        filter_label.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        chips_layout.addWidget(filter_label)

        self._chips: list[_FilterChip] = []
        for key, label, color in _SEARCH_FILTERS:
            chip = _FilterChip(key, label, color, self)
            chip.toggled.connect(lambda _checked: self._on_filter_changed())
            self._chips.append(chip)
            chips_layout.addWidget(chip)

        chips_layout.addStretch()
        layout.addLayout(chips_layout)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self._status)

        # Results list
        self._model = SearchResultModel(self)
        self._list = QListView()
        self._list.setModel(self._model)
        self._list.setItemDelegate(SearchResultDelegate(self))
        self._list.setMouseTracking(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.clicked.connect(self._on_result_clicked)
        layout.addWidget(self._list, stretch=1)

    def set_services(self, services: ServiceContainer) -> None:
        self._services = services

    def focus_input(self) -> None:
        """Focus the search input field."""
        self._input.setFocus()
        self._input.selectAll()

    def _get_active_roles(self) -> list[str] | None:
        """Return the list of active filter roles, or None if all are active."""
        active = [chip.key for chip in self._chips if chip.active]
        if len(active) == len(self._chips):
            return None  # all active = no filtering
        return active

    def _on_filter_changed(self) -> None:
        """Re-run search when filters change."""
        if self._input.text().strip():
            self._do_search()

    @async_slot
    async def _do_search(self) -> None:
        query = self._input.text().strip()
        if not query or not self._services:
            return

        self._status.setText("Searching...")
        self._search_btn.setEnabled(False)

        try:
            roles = self._get_active_roles()
            result = await self._services.search_service.search(
                query=query, roles=roles, limit=100
            )
            if isinstance(result, Ok):
                sr = result.ok_value
                self._model.set_results(sr.results)
                self._status.setText(f'{sr.total_count} results for "{query}"')
            else:
                self._status.setText(f"Error: {result.err_value}")
        finally:
            self._search_btn.setEnabled(True)

    def _on_result_clicked(self, index: QModelIndex) -> None:
        result = self._model.result_at(index.row())
        if result:
            self.session_requested.emit(result.session_id)
