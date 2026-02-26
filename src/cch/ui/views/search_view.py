"""Search view — search input + filters + results list + detail navigation."""

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

from cch.models.categories import CATEGORY_FILTERS, DEFAULT_ACTIVE_CATEGORY_KEYS
from cch.models.search import SearchResult
from cch.ui.async_bridge import async_slot
from cch.ui.theme import COLORS, provider_color, provider_label
from cch.ui.widgets.delegates import SearchResultDelegate

if TYPE_CHECKING:
    from cch.services.container import ServiceContainer

_PROVIDERS = ("claude", "codex", "gemini")


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
            return r.message_type
        if role == Qt.ItemDataRole.UserRole + 2:
            return r.project_name
        if role == Qt.ItemDataRole.UserRole + 3:
            return r.timestamp
        if role == Qt.ItemDataRole.UserRole + 4:
            return r.provider
        return None


class _FilterChip(QPushButton):
    """A toggleable filter chip button."""

    def __init__(
        self,
        key: str,
        label: str,
        color: str,
        *,
        active: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(label, parent)
        self.key = key
        self._base_label = label
        self._color = color
        self._active = active
        self.setCheckable(True)
        self.setChecked(active)
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
                f"  border: none; border-radius: 14px; padding: 5px 14px; "
                f"  font-size: 12px; font-weight: 600; "
                f"}} "
                f"QPushButton:hover {{ opacity: 0.9; }}"
            )
        else:
            self.setStyleSheet(
                f"QPushButton {{ "
                f"  background-color: transparent; color: {COLORS['text_muted']}; "
                f"  border: 1px solid {COLORS['border']}; border-radius: 14px; "
                f"  padding: 5px 14px; font-size: 12px; "
                f"}} "
                f"QPushButton:hover {{ "
                f"  border-color: {self._color}; color: {self._color}; "
                f"}}"
            )

    @property
    def active(self) -> bool:
        return self._active

    def set_count(self, count: int) -> None:
        self.setText(f"{self._base_label} ({count})")


class SearchView(QWidget):
    """Search input + filters + results list."""

    session_requested = Signal(str, str)  # session_id, message_uuid

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services: ServiceContainer | None = None
        self._active_providers: set[str] = set(_PROVIDERS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 0)
        layout.setSpacing(8)

        header = QLabel("\U0001f50d Search")
        header.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(header)

        # Search bar (message query)
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

        # Project/provider filters
        project_layout = QHBoxLayout()
        project_layout.setSpacing(6)
        project_layout.setContentsMargins(0, 2, 0, 2)

        project_label = QLabel("Projects:")
        project_label.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        project_layout.addWidget(project_label)

        self._project_input = QLineEdit()
        self._project_input.setPlaceholderText("Filter projects by name/path...")
        self._project_input.setStyleSheet(
            f"border-radius: 8px; padding: 6px 10px; "
            f"border: 1px solid {COLORS['border']}; "
            f"background-color: {COLORS['bg']}; font-size: 12px;"
        )
        self._project_input.returnPressed.connect(self._do_search)
        self._project_input.textChanged.connect(self._on_provider_or_project_changed)
        project_layout.addWidget(self._project_input, stretch=1)

        providers_label = QLabel("Providers:")
        providers_label.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        project_layout.addWidget(providers_label)

        self._provider_chips: dict[str, _FilterChip] = {}
        for provider in _PROVIDERS:
            chip = _FilterChip(
                provider,
                provider_label(provider),
                provider_color(provider),
                active=True,
                parent=self,
            )
            chip.toggled.connect(
                lambda checked, p=provider: self._on_provider_toggled(p, checked)
            )
            self._provider_chips[provider] = chip
            project_layout.addWidget(chip)

        layout.addLayout(project_layout)

        # Message-type filter chips
        chips_layout = QHBoxLayout()
        chips_layout.setSpacing(6)
        chips_layout.setContentsMargins(0, 2, 0, 2)

        filter_label = QLabel("Types:")
        filter_label.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        chips_layout.addWidget(filter_label)

        self._chips: list[_FilterChip] = []
        default_active = set(DEFAULT_ACTIVE_CATEGORY_KEYS)
        for spec in CATEGORY_FILTERS:
            chip = _FilterChip(
                spec.key,
                spec.label,
                spec.color,
                active=spec.key in default_active,
                parent=self,
            )
            chip.toggled.connect(lambda _checked: self._on_filter_changed())
            self._chips.append(chip)
            chips_layout.addWidget(chip)

        chips_layout.addStretch()
        layout.addLayout(chips_layout)

        self._status = QLabel("")
        self._status.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self._status)

        self._model = SearchResultModel(self)
        self._list = QListView()
        self._list.setModel(self._model)
        self._list.setItemDelegate(SearchResultDelegate(self))
        self._list.setMouseTracking(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.activated.connect(self._on_result_activated)
        layout.addWidget(self._list, stretch=1)

    def set_services(self, services: ServiceContainer) -> None:
        self._services = services

    def focus_input(self) -> None:
        """Focus the search input field."""
        self._input.setFocus()
        self._input.selectAll()

    def _get_active_roles(self) -> list[str] | None:
        """Return active category filters, or None if all are active."""
        active = [chip.key for chip in self._chips if chip.active]
        if len(active) == len(self._chips):
            return None
        return active

    def _selected_providers(self) -> list[str] | None:
        if len(self._active_providers) == len(_PROVIDERS):
            return None
        return sorted(self._active_providers)

    def _on_provider_toggled(self, provider: str, checked: bool) -> None:
        if checked:
            self._active_providers.add(provider)
        else:
            self._active_providers.discard(provider)
            if not self._active_providers:
                self._active_providers.add(provider)

        for key, chip in self._provider_chips.items():
            chip.blockSignals(True)
            chip.setChecked(key in self._active_providers)
            chip.blockSignals(False)
        self._on_provider_or_project_changed()

    def _on_provider_or_project_changed(self) -> None:
        if self._input.text().strip():
            self._do_search()

    def _on_filter_changed(self) -> None:
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
            result = await self._services.search_service.search(
                query=query,
                roles=self._get_active_roles(),
                providers=self._selected_providers(),
                project_query=self._project_input.text().strip(),
                limit=100,
            )
            if isinstance(result, Ok):
                sr = result.ok_value
                self._model.set_results(sr.results)
                self._update_type_chip_counts(sr.type_counts)
                self._status.setText(f'{sr.total_count} results for "{query}"')
            else:
                self._status.setText(f"Error: {result.err_value}")
        finally:
            self._search_btn.setEnabled(True)

    def _update_type_chip_counts(self, counts: dict[str, int]) -> None:
        for chip in self._chips:
            chip.set_count(int(counts.get(chip.key, 0)))

    def _on_result_activated(self, index: QModelIndex) -> None:
        result = self._model.result_at(index.row())
        if result:
            self.session_requested.emit(result.session_id, result.message_uuid)
