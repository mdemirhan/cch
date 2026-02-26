"""Panel 2: Projects list with filter tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import QLabel, QLineEdit, QListView, QVBoxLayout, QWidget

from cch.models.projects import ProjectSummary
from cch.ui.theme import COLORS
from cch.ui.widgets.delegates import ProjectDelegate

if TYPE_CHECKING:
    from cch.services.container import ServiceContainer


class ProjectListModel(QAbstractListModel):
    """Model backing the projects QListView."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._projects: list[ProjectSummary] = []
        self._filtered: list[ProjectSummary] = []

    def set_projects(self, projects: list[ProjectSummary]) -> None:
        self.beginResetModel()
        self._projects = projects
        self._filtered = projects
        self.endResetModel()

    def apply_filter(self, text: str) -> None:
        self.beginResetModel()
        if not text:
            self._filtered = self._projects
        else:
            lower = text.lower()
            self._filtered = [p for p in self._projects if lower in p.project_name.lower()]
        self.endResetModel()

    def project_at(self, index: int) -> ProjectSummary | None:
        if 0 <= index < len(self._filtered):
            return self._filtered[index]
        return None

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._filtered)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or index.row() >= len(self._filtered):
            return None
        p = self._filtered[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return p.project_name
        if role == Qt.ItemDataRole.UserRole:
            return p.project_id
        if role == Qt.ItemDataRole.UserRole + 1:
            return p.project_path
        if role == Qt.ItemDataRole.UserRole + 2:
            return p.session_count
        if role == Qt.ItemDataRole.UserRole + 3:
            return p.last_activity
        return None


class ListPanel(QWidget):
    """Left panel: list of projects with a filter input."""

    project_selected = Signal(str)  # project_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services: ServiceContainer | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("Projects")
        header.setStyleSheet(
            f"font-weight: 600; font-size: 13px; padding: 12px 14px; "
            f"background-color: {COLORS['panel_bg']}; "
            f"border-bottom: 1px solid {COLORS['border']}; "
            f"color: {COLORS['text']}; letter-spacing: 0.3px;"
        )
        layout.addWidget(header)

        # Filter input
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter projects...")
        self._filter_input.setStyleSheet(
            f"margin: 8px 10px; border-radius: 6px; padding: 6px 10px; "
            f"border: 1px solid {COLORS['border']}; "
            f"background-color: {COLORS['bg']}; font-size: 12px;"
        )
        self._filter_input.textChanged.connect(self._on_filter_changed)
        layout.addWidget(self._filter_input)

        # List view
        self._model = ProjectListModel(self)
        self._list = QListView()
        self._list.setModel(self._model)
        self._list.setItemDelegate(ProjectDelegate(self))
        self._list.setMouseTracking(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.clicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self.setStyleSheet(f"background-color: {COLORS['panel_bg']};")

    def set_services(self, services: ServiceContainer) -> None:
        self._services = services

    def set_projects(self, projects: list[ProjectSummary]) -> None:
        self._model.set_projects(projects)

    def _on_filter_changed(self, text: str) -> None:
        self._model.apply_filter(text)

    def _on_item_clicked(self, index: QModelIndex) -> None:
        project = self._model.project_at(index.row())
        if project:
            self.project_selected.emit(project.project_id)
