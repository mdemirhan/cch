"""Panel 2: provider-aware projects list with search and provider filters."""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    Qt,
    Signal,
)
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

from cch.models.projects import ProjectSummary
from cch.ui.finder import show_in_file_manager
from cch.ui.theme import COLORS, provider_color, provider_label
from cch.ui.widgets.delegates import ProjectDelegate

_PROVIDERS = ("claude", "codex", "gemini")


class ProjectListModel(QAbstractListModel):
    """Model backing the projects QListView."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._projects: list[ProjectSummary] = []
        self._filtered: list[ProjectSummary] = []
        self._filter_text = ""
        self._provider_filter: set[str] = set(_PROVIDERS)

    def set_projects(self, projects: list[ProjectSummary]) -> None:
        self.beginResetModel()
        self._projects = projects
        self._rebuild_filtered()
        self.endResetModel()

    def set_filters(self, text: str, providers: set[str]) -> None:
        self.beginResetModel()
        self._filter_text = text.strip().lower()
        self._provider_filter = {provider.strip().lower() for provider in providers}
        self._rebuild_filtered()
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
        project = self._filtered[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return project.project_name
        if role == Qt.ItemDataRole.UserRole:
            return project.project_id
        if role == Qt.ItemDataRole.UserRole + 1:
            return project.project_path
        if role == Qt.ItemDataRole.UserRole + 2:
            return project.session_count
        if role == Qt.ItemDataRole.UserRole + 3:
            return project.last_activity
        if role == Qt.ItemDataRole.UserRole + 4:
            return project.provider
        return None

    def _rebuild_filtered(self) -> None:
        projects = self._projects
        if self._provider_filter:
            projects = [p for p in projects if p.provider in self._provider_filter]
        if self._filter_text:
            text = self._filter_text
            projects = [
                p
                for p in projects
                if text in p.project_name.lower() or text in p.project_path.lower()
            ]
        self._filtered = projects


class ListPanel(QWidget):
    """Left panel: provider-filtered list of projects."""

    project_selected = Signal(str)  # project_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_providers: set[str] = set(_PROVIDERS)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Projects")
        header.setStyleSheet(
            f"font-weight: 700; font-size: 14px; padding: 12px 16px; "
            f"background-color: {COLORS['panel_bg']}; "
            f"border-bottom: 1px solid {COLORS['border']}; "
            f"color: {COLORS['text']};"
        )
        layout.addWidget(header)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(10, 8, 10, 8)
        controls_layout.setSpacing(8)

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Filter projects...")
        self._filter_input.setStyleSheet(
            f"border-radius: 8px; padding: 8px 10px; "
            f"border: 1px solid {COLORS['border']}; "
            f"background-color: {COLORS['bg']}; font-size: 13px;"
        )
        self._filter_input.textChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self._filter_input)

        provider_row = QHBoxLayout()
        provider_row.setContentsMargins(0, 0, 0, 0)
        provider_row.setSpacing(6)

        provider_title = QLabel("Providers")
        provider_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        provider_row.addWidget(provider_title)

        self._provider_buttons: dict[str, QPushButton] = {}
        for provider in _PROVIDERS:
            button = QPushButton(provider_label(provider))
            button.setCheckable(True)
            button.setChecked(True)
            button.clicked.connect(
                lambda checked, p=provider: self._on_provider_toggled(p, checked)
            )
            self._provider_buttons[provider] = button
            provider_row.addWidget(button)

        provider_row.addStretch()
        controls_layout.addLayout(provider_row)
        layout.addWidget(controls)

        self._model = ProjectListModel(self)
        self._list = QListView()
        self._list.setModel(self._model)
        self._list.setItemDelegate(ProjectDelegate(self))
        self._list.setMouseTracking(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.clicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list)

        self.setStyleSheet(f"background-color: {COLORS['panel_bg']};")
        self._refresh_provider_button_styles()

    def set_projects(self, projects: list[ProjectSummary]) -> None:
        self._model.set_projects(projects)
        self._apply_model_filters()

    def _on_filter_changed(self, _text: str) -> None:
        self._apply_model_filters()

    def _on_provider_toggled(self, provider: str, checked: bool) -> None:
        if checked:
            self._active_providers.add(provider)
        else:
            self._active_providers.discard(provider)
            if not self._active_providers:
                # Keep at least one provider selected.
                self._active_providers.add(provider)
        self._refresh_provider_button_styles()
        self._apply_model_filters()

    def _apply_model_filters(self) -> None:
        self._model.set_filters(self._filter_input.text(), self._active_providers)

    def _refresh_provider_button_styles(self) -> None:
        for provider, button in self._provider_buttons.items():
            active = provider in self._active_providers
            button.setChecked(active)
            button.setStyleSheet(_provider_chip_style(provider, active))

    def _on_item_clicked(self, index: QModelIndex) -> None:
        project = self._model.project_at(index.row())
        if project:
            self.project_selected.emit(project.project_id)

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self._list.indexAt(pos)
        if not index.isValid():
            return
        project = self._model.project_at(index.row())
        if project is None or not project.project_path:
            return

        menu = QMenu(self)
        show_action = menu.addAction("Show in Finder")
        selected = menu.exec(self._list.viewport().mapToGlobal(pos))
        if selected == show_action:
            show_in_file_manager(project.project_path)


def _provider_chip_style(provider: str, active: bool) -> str:
    color = provider_color(provider)
    if active:
        return (
            "QPushButton { "
            f"background-color: {color}; color: white; "
            "border: none; border-radius: 12px; padding: 4px 12px; "
            "font-size: 11px; font-weight: 600; }"
            "QPushButton:hover { opacity: 0.92; }"
        )
    return (
        "QPushButton { "
        f"background-color: transparent; color: {COLORS['text_muted']}; "
        f"border: 1px solid {COLORS['border']}; border-radius: 12px; "
        "padding: 4px 12px; font-size: 11px; font-weight: 500; }"
        "QPushButton:hover { "
        f"border-color: {color}; color: {color}; }}"
    )
