"""Reusable rounded toggle chip button used across filters."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget

from cch.ui.theme import COLORS


class FilterChip(QPushButton):
    """A compact toggle chip with active/inactive visual states."""

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

    @property
    def active(self) -> bool:
        return self._active

    def set_count(self, count: int) -> None:
        """Append a count to the chip text."""
        self.setText(f"{self._base_label} ({count})")

    def set_base_label(self) -> None:
        """Reset chip text back to label only."""
        self.setText(self._base_label)

    def _on_toggled(self, checked: bool) -> None:
        self._active = checked
        self._apply_style()

    def _apply_style(self) -> None:
        if self._active:
            self.setStyleSheet(
                "QPushButton { "
                f"background-color: {self._color}; color: white; "
                "border: none; border-radius: 12px; padding: 4px 12px; "
                "font-size: 11px; font-weight: 600; }"
                "QPushButton:hover { opacity: 0.92; }"
            )
            return
        self.setStyleSheet(
            "QPushButton { "
            f"background-color: transparent; color: {COLORS['text_muted']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 12px; "
            "padding: 4px 12px; font-size: 11px; font-weight: 500; }"
            "QPushButton:hover { "
            f"border-color: {self._color}; color: {self._color}; }}"
        )
