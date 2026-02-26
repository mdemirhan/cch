"""Export dialog — file dialog-based session export."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from result import Ok

from cch.ui.async_bridge import async_slot
from cch.ui.theme import COLORS

if TYPE_CHECKING:
    from cch.services.container import ServiceContainer


class ExportDialog(QDialog):
    """Dialog for exporting a session to Markdown/JSON/CSV."""

    def __init__(self, services: ServiceContainer, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services = services
        self._sessions: list[tuple[str, str]] = []  # (session_id, display_name)

        self.setWindowTitle("Export Session")
        self.setMinimumWidth(450)
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header
        header = QLabel("Export Session")
        header.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(header)

        # Session selector
        layout.addWidget(QLabel("Session:"))
        self._session_combo = QComboBox()
        self._session_combo.setMinimumWidth(400)
        layout.addWidget(self._session_combo)

        # Format selector
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Format:"))
        self._format_combo = QComboBox()
        self._format_combo.addItems(["Markdown", "JSON", "CSV"])
        fmt_layout.addWidget(self._format_combo)
        fmt_layout.addStretch()
        layout.addLayout(fmt_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        export_btn = QPushButton("Export...")
        export_btn.setStyleSheet(
            f"QPushButton {{ "
            f"  background-color: {COLORS['primary']}; color: white; "
            f"  border: none; border-radius: 6px; padding: 8px 20px; "
            f"  font-weight: bold; "
            f"}} "
            f"QPushButton:hover {{ background-color: #D35400; }}"
        )
        export_btn.clicked.connect(self._do_export)
        btn_layout.addWidget(export_btn)

        layout.addLayout(btn_layout)

        # Load sessions
        asyncio.ensure_future(self._load_sessions())

    async def _load_sessions(self) -> None:
        result = await self._services.session_service.list_sessions(limit=500)
        if isinstance(result, Ok):
            sessions, _total = result.ok_value
            self._sessions = [
                (
                    s.session_id,
                    f"{s.summary or s.first_prompt or s.session_id[:12]} ({s.project_name})",
                )
                for s in sessions
            ]
            for _sid, display in self._sessions:
                self._session_combo.addItem(display)

    @async_slot
    async def _do_export(self) -> None:
        idx = self._session_combo.currentIndex()
        if idx < 0 or idx >= len(self._sessions):
            return

        session_id = self._sessions[idx][0]
        fmt = self._format_combo.currentText().lower()

        # File extension
        ext_map = {"markdown": ".md", "json": ".json", "csv": ".csv"}
        ext = ext_map.get(fmt, ".txt")
        filter_map = {
            "markdown": "Markdown files (*.md)",
            "json": "JSON files (*.json)",
            "csv": "CSV files (*.csv)",
        }

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Session",
            f"session{ext}",
            filter_map.get(fmt, "All files (*)"),
        )

        if not file_path:
            return

        # Export
        if fmt == "markdown":
            result = await self._services.export_service.export_session_markdown(session_id)
        elif fmt == "json":
            result = await self._services.export_service.export_session_json(session_id)
        else:
            result = await self._services.export_service.export_session_csv(session_id)

        if isinstance(result, Ok):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(result.ok_value)
            QMessageBox.information(self, "Export Complete", f"Session exported to:\n{file_path}")
            self.accept()
        else:
            QMessageBox.warning(self, "Export Error", f"Failed to export:\n{result.err_value}")
