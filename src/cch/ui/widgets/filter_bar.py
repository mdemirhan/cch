"""Filter bar — toggle filter chips for message categories."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from cch.ui.theme import COLORS

_FILTERS = [
    ("user", "User", COLORS["primary"]),
    ("assistant", "Assistant", COLORS["success"]),
    ("tool_call", "Tool Calls", "#8E44AD"),
    ("thinking", "Thinking", "#9B59B6"),
    ("tool_result", "Results", COLORS["text_muted"]),
    ("system", "System", COLORS["warning"]),
]


class FilterBar(QWidget):
    """Horizontal bar of toggle chips for message filtering."""

    filters_changed = Signal(set)  # set of active filter names

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)

        self._buttons: dict[str, QPushButton] = {}
        self._active: set[str] = {name for name, _, _ in _FILTERS}

        for name, label, color in _FILTERS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setStyleSheet(self._chip_style(color, active=True))
            btn.clicked.connect(lambda _checked, n=name, c=color: self._toggle(n, c))
            layout.addWidget(btn)
            self._buttons[name] = btn

        layout.addStretch()

    @property
    def active_filters(self) -> set[str]:
        return set(self._active)

    def _toggle(self, name: str, color: str) -> None:
        btn = self._buttons[name]
        if name in self._active:
            self._active.discard(name)
            btn.setChecked(False)
            btn.setStyleSheet(self._chip_style(color, active=False))
        else:
            self._active.add(name)
            btn.setChecked(True)
            btn.setStyleSheet(self._chip_style(color, active=True))
        self.filters_changed.emit(self._active)

    @staticmethod
    def _chip_style(color: str, *, active: bool) -> str:
        if active:
            return (
                f"QPushButton {{ "
                f"  background-color: {color}; color: white; "
                f"  border: none; border-radius: 14px; "
                f"  padding: 5px 14px; font-size: 12px; font-weight: 500; "
                f"}} "
                f"QPushButton:hover {{ "
                f"  background-color: {color}; "
                f"}}"
            )
        return (
            f"QPushButton {{ "
            f"  background-color: transparent; color: {COLORS['text_muted']}; "
            f"  border: 1px solid {COLORS['border']}; border-radius: 14px; "
            f"  padding: 5px 14px; font-size: 12px; font-weight: 500; "
            f"}} "
            f"QPushButton:hover {{ "
            f"  background-color: #F0F0F0; "
            f"  color: {COLORS['text']}; "
            f"  border-color: #CCC; "
            f"}}"
        )
