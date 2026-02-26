"""Search view — search input + filter chips + results list + detail navigation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from result import Ok

from cch.models.categories import CATEGORY_FILTERS, DEFAULT_ACTIVE_CATEGORY_KEYS
from cch.models.search import SearchResult
from cch.ui.async_bridge import async_slot, schedule
from cch.ui.theme import COLORS, provider_label
from cch.ui.widgets.delegates import SearchResultDelegate

if TYPE_CHECKING:
    from cch.services.container import ServiceContainer

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


class SearchView(QWidget):
    """Search input + filter chips + results list."""

    session_requested = Signal(str, str)  # session_id, message_uuid

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services: ServiceContainer | None = None
        self._project_menu_loaded = False
        self._project_actions: dict[str, QAction] = {}
        self._all_projects_action: QAction | None = None
        self._updating_project_menu = False

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

        self._project_filter_btn = QPushButton("Projects: All")
        self._project_filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._project_filter_btn.setStyleSheet(
            "QPushButton { "
            f"background-color: transparent; color: {COLORS['text_muted']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 14px; "
            "padding: 5px 14px; font-size: 12px; font-weight: 500; }"
            "QPushButton:hover { "
            f"border-color: {COLORS['primary']}; color: {COLORS['primary']}; }}"
        )
        self._project_filter_btn.clicked.connect(self._show_project_filter_menu)
        self._project_filter_menu = QMenu(self)
        chips_layout.addWidget(self._project_filter_btn)

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
        self._list.activated.connect(self._on_result_activated)
        layout.addWidget(self._list, stretch=1)

    def set_services(self, services: ServiceContainer) -> None:
        self._services = services
        schedule(self._ensure_project_filter_menu())

    def focus_input(self) -> None:
        """Focus the search input field."""
        self._input.setFocus()
        self._input.selectAll()

    def _get_active_roles(self) -> list[str] | None:
        """Return active category filters, or None if all are active."""
        active = [chip.key for chip in self._chips if chip.active]
        if len(active) == len(self._chips):
            return None  # all active = no filtering
        return active

    def _on_filter_changed(self) -> None:
        """Re-run search when filters change."""
        if self._input.text().strip():
            self._do_search()

    async def _ensure_project_filter_menu(self) -> None:
        if self._project_menu_loaded or not self._services:
            return
        result = await self._services.project_service.list_projects()
        if not isinstance(result, Ok):
            return

        self._project_filter_menu.clear()
        self._project_actions.clear()

        self._all_projects_action = QAction("All Projects", self._project_filter_menu)
        self._all_projects_action.setCheckable(True)
        self._all_projects_action.setChecked(True)
        self._all_projects_action.toggled.connect(self._on_all_projects_toggled)
        self._project_filter_menu.addAction(self._all_projects_action)
        self._project_filter_menu.addSeparator()

        for project in result.ok_value:
            label = f"{project.project_name} ({provider_label(project.provider)})"
            action = QAction(label, self._project_filter_menu)
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(self._on_project_selection_changed)
            self._project_filter_menu.addAction(action)
            self._project_actions[project.project_id] = action

        self._project_menu_loaded = True
        self._update_project_filter_label()

    def _show_project_filter_menu(self) -> None:
        if not self._project_menu_loaded:
            if self._services:
                schedule(self._ensure_project_filter_menu())
            return
        pos = self._project_filter_btn.mapToGlobal(self._project_filter_btn.rect().bottomLeft())
        self._project_filter_menu.exec(pos)

    def _on_all_projects_toggled(self, checked: bool) -> None:
        if self._updating_project_menu:
            return
        self._updating_project_menu = True
        for action in self._project_actions.values():
            action.setChecked(checked)
        self._updating_project_menu = False
        self._update_project_filter_label()
        if self._input.text().strip():
            self._do_search()

    def _on_project_selection_changed(self, _checked: bool) -> None:
        if self._updating_project_menu:
            return
        selected = [action for action in self._project_actions.values() if action.isChecked()]
        if not selected:
            self._updating_project_menu = True
            for action in self._project_actions.values():
                action.setChecked(True)
            selected = list(self._project_actions.values())
            self._updating_project_menu = False

        all_selected = len(selected) == len(self._project_actions)
        if self._all_projects_action is not None:
            self._updating_project_menu = True
            self._all_projects_action.setChecked(all_selected)
            self._updating_project_menu = False
        self._update_project_filter_label()
        if self._input.text().strip():
            self._do_search()

    def _selected_project_ids(self) -> list[str] | None:
        if not self._project_actions:
            return None
        selected = [pid for pid, action in self._project_actions.items() if action.isChecked()]
        if not selected or len(selected) == len(self._project_actions):
            return None
        return selected

    def _update_project_filter_label(self) -> None:
        selected_ids = self._selected_project_ids()
        if selected_ids is None:
            self._project_filter_btn.setText("Projects: All")
        elif len(selected_ids) == 1:
            self._project_filter_btn.setText("Projects: 1")
        else:
            self._project_filter_btn.setText(f"Projects: {len(selected_ids)}")

    @async_slot
    async def _do_search(self) -> None:
        query = self._input.text().strip()
        if not query or not self._services:
            return
        if not self._project_menu_loaded:
            await self._ensure_project_filter_menu()

        self._status.setText("Searching...")
        self._search_btn.setEnabled(False)

        try:
            roles = self._get_active_roles()
            project_ids = self._selected_project_ids()
            result = await self._services.search_service.search(
                query=query, roles=roles, project_ids=project_ids, limit=100
            )
            if isinstance(result, Ok):
                sr = result.ok_value
                self._model.set_results(sr.results)
                self._status.setText(f'{sr.total_count} results for "{query}"')
            else:
                self._status.setText(f"Error: {result.err_value}")
        finally:
            self._search_btn.setEnabled(True)

    def _on_result_activated(self, index: QModelIndex) -> None:
        result = self._model.result_at(index.row())
        if result:
            self.session_requested.emit(result.session_id, result.message_uuid)
