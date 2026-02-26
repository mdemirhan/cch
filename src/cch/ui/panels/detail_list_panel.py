"""Panel 3: Sessions list for a selected project."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import QLabel, QListView, QVBoxLayout, QWidget

from cch.models.sessions import SessionSummary
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
            return s.summary or s.first_prompt or s.session_id[:12]
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
            f"font-weight: 600; font-size: 13px; padding: 12px 14px; "
            f"background-color: {COLORS['panel_bg']}; "
            f"border-bottom: 1px solid {COLORS['border']}; "
            f"color: {COLORS['text']}; letter-spacing: 0.3px;"
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
        layout.addWidget(self._list)

        self.setStyleSheet(f"background-color: {COLORS['panel_bg']};")

    def set_sessions(self, sessions: list[SessionSummary]) -> None:
        self._model.set_sessions(sessions)
        self._header.setText(f"Sessions ({len(sessions)})")

    def _on_item_clicked(self, index: QModelIndex) -> None:
        session = self._model.session_at(index.row())
        if session:
            self.session_selected.emit(session.session_id)
