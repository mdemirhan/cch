"""Panel 3: Sessions list for a selected project."""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QLabel, QListView, QMenu, QVBoxLayout, QWidget

from cch.models.sessions import SessionSummary
from cch.ui.finder import show_in_file_manager
from cch.ui.theme import COLORS
from cch.ui.widgets.delegates import SessionDelegate


class SessionListModel(QAbstractListModel):
    """Model backing the sessions QListView."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sessions: list[SessionSummary] = []

    def set_sessions(self, sessions: list[SessionSummary]) -> None:
        self.beginResetModel()
        self._sessions = sessions
        self.endResetModel()

    def session_at(self, index: int) -> SessionSummary | None:
        if 0 <= index < len(self._sessions):
            return self._sessions[index]
        return None

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
        return len(self._sessions)

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or index.row() >= len(self._sessions):
            return None
        s = self._sessions[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            title = s.summary or s.first_prompt or s.session_id[:12]
            return " ".join(title.split())
        if role == Qt.ItemDataRole.UserRole:
            return s.session_id
        if role == Qt.ItemDataRole.UserRole + 1:
            return s.model
        if role == Qt.ItemDataRole.UserRole + 2:
            return s.total_input_tokens
        if role == Qt.ItemDataRole.UserRole + 3:
            return s.total_output_tokens
        if role == Qt.ItemDataRole.UserRole + 4:
            return s.modified_at
        if role == Qt.ItemDataRole.UserRole + 5:
            return s.message_count
        if role == Qt.ItemDataRole.UserRole + 6:
            return s.provider
        if role == Qt.ItemDataRole.UserRole + 7:
            return s.file_path
        return None


class DetailListPanel(QWidget):
    """Middle panel: list of sessions for the selected project."""

    session_selected = Signal(str)  # session_id

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QLabel("Sessions")
        self._header.setStyleSheet(
            f"font-weight: 700; font-size: 14px; padding: 12px 16px; "
            f"background-color: {COLORS['panel_bg']}; "
            f"border-bottom: 1px solid {COLORS['border']}; "
            f"color: {COLORS['text']};"
        )
        layout.addWidget(self._header)

        # List view
        self._model = SessionListModel(self)
        self._list = QListView()
        self._list.setModel(self._model)
        self._list.setItemDelegate(SessionDelegate(self))
        self._list.setMouseTracking(True)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.clicked.connect(self._on_item_clicked)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list)

        self.setStyleSheet(f"background-color: {COLORS['panel_bg']};")

    def set_sessions(self, sessions: list[SessionSummary]) -> None:
        self._model.set_sessions(sessions)
        self._header.setText(f"Sessions ({len(sessions)})")

    def _on_item_clicked(self, index: QModelIndex) -> None:
        session = self._model.session_at(index.row())
        if session:
            self.session_selected.emit(session.session_id)

    def _on_context_menu(self, pos: QPoint) -> None:
        index = self._list.indexAt(pos)
        if not index.isValid():
            return
        session = self._model.session_at(index.row())
        if session is None or not session.file_path:
            return

        menu = QMenu(self)
        show_action = menu.addAction("Show in Finder")
        selected = menu.exec(self._list.viewport().mapToGlobal(pos))
        if selected == show_action:
            show_in_file_manager(session.file_path, parent_dir=True)
