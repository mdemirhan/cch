"""Statistics view — charts + stat cards."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from result import Ok

from cch.ui.async_bridge import async_slot
from cch.ui.theme import COLORS, format_cost, format_tokens
from cch.ui.widgets.chart_widget import CostChart, HeatmapChart, ModelPieChart, ToolBarChart

if TYPE_CHECKING:
    from cch.services.container import ServiceContainer


class StatCard(QWidget):
    """Small stat card with label + value."""

    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet("font-size: 22px; font-weight: bold;")
        layout.addWidget(val_lbl)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        layout.addWidget(name_lbl)

        self.setStyleSheet(
            f"background-color: {COLORS['bg']}; border: 1px solid #EAEAEA; border-radius: 8px;"
        )

        self._val_lbl = val_lbl

    def set_value(self, value: str) -> None:
        self._val_lbl.setText(value)


class StatisticsView(QWidget):
    """Overview statistics with charts and stat cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._services: ServiceContainer | None = None

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(16, 12, 16, 16)
        self._layout.setSpacing(16)

        # Header
        header_layout = QHBoxLayout()
        header = QLabel("Statistics")
        header.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_layout.addWidget(header)

        header_layout.addStretch()

        # Period selector
        self._period_combo = QComboBox()
        self._period_combo.addItems(["Daily", "Weekly", "Monthly"])
        self._period_combo.currentTextChanged.connect(self._on_period_changed)
        header_layout.addWidget(QLabel("Period:"))
        header_layout.addWidget(self._period_combo)

        self._layout.addLayout(header_layout)

        # Stat cards row
        self._cards_widget = QWidget()
        cards_layout = QHBoxLayout(self._cards_widget)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(12)

        self._card_sessions = StatCard("Total Sessions", "—")
        self._card_messages = StatCard("Total Messages", "—")
        self._card_tokens = StatCard("Total Tokens", "—")
        self._card_cost = StatCard("Est. Cost", "—")
        cards_layout.addWidget(self._card_sessions)
        cards_layout.addWidget(self._card_messages)
        cards_layout.addWidget(self._card_tokens)
        cards_layout.addWidget(self._card_cost)

        self._layout.addWidget(self._cards_widget)

        # Charts grid
        charts_grid = QGridLayout()
        charts_grid.setSpacing(16)

        # Cost chart
        cost_group, cost_layout = self._chart_group("Cost Over Time")
        self._cost_chart = CostChart(width=7, height=3)
        cost_layout.addWidget(self._cost_chart)
        charts_grid.addWidget(cost_group, 0, 0)

        # Heatmap
        heatmap_group, heatmap_layout = self._chart_group("Activity Heatmap")
        self._heatmap_chart = HeatmapChart(width=7, height=3)
        heatmap_layout.addWidget(self._heatmap_chart)
        charts_grid.addWidget(heatmap_group, 1, 0)

        # Model pie
        model_group, model_layout = self._chart_group("Model Usage")
        self._model_chart = ModelPieChart(width=4, height=3)
        model_layout.addWidget(self._model_chart)
        charts_grid.addWidget(model_group, 0, 1)

        # Tool bar chart
        tool_group, tool_layout = self._chart_group("Tool Usage")
        self._tool_chart = ToolBarChart(width=4, height=3)
        tool_layout.addWidget(self._tool_chart)
        charts_grid.addWidget(tool_group, 1, 1)

        charts_grid.setColumnStretch(0, 3)
        charts_grid.setColumnStretch(1, 2)

        self._layout.addLayout(charts_grid)
        self._layout.addStretch()

        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _chart_group(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        """Create a titled group widget for a chart."""
        group = QWidget()
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(4)

        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {COLORS['text']};")
        group_layout.addWidget(lbl)

        return group, group_layout

    def set_services(self, services: ServiceContainer) -> None:
        self._services = services
        self._load_data()

    @async_slot
    async def _load_data(self) -> None:
        if not self._services:
            return

        # Load stats
        stats_result = await self._services.session_service.get_stats()
        if isinstance(stats_result, Ok):
            stats = stats_result.ok_value
            self._card_sessions.set_value(str(stats.get("total_sessions", 0)))
            self._card_messages.set_value(str(stats.get("total_messages", 0)))
            total_tokens = stats.get("total_input_tokens", 0) + stats.get("total_output_tokens", 0)
            self._card_tokens.set_value(format_tokens(total_tokens))

            # Estimate total cost
            from cch.services.cost import estimate_cost

            cost = estimate_cost(
                "",
                stats.get("total_input_tokens", 0),
                stats.get("total_output_tokens", 0),
                stats.get("total_cache_read_tokens", 0),
                stats.get("total_cache_creation_tokens", 0),
            )
            self._card_cost.set_value(format_cost(cost["total_cost"]))

        # Load cost chart
        period = self._period_combo.currentText().lower()
        cost_result = await self._services.analytics_service.get_cost_breakdown(period)
        if isinstance(cost_result, Ok):
            self._cost_chart.set_data(cost_result.ok_value)

        # Load heatmap
        heatmap_result = await self._services.analytics_service.get_heatmap_data()
        if isinstance(heatmap_result, Ok):
            self._heatmap_chart.set_data(heatmap_result.ok_value)

        # Load model usage
        model_result = await self._services.analytics_service.get_model_usage()
        if isinstance(model_result, Ok):
            self._model_chart.set_data(model_result.ok_value)

        # Load tool usage
        tool_result = await self._services.analytics_service.get_tool_usage()
        if isinstance(tool_result, Ok):
            self._tool_chart.set_data(tool_result.ok_value)

    def _on_period_changed(self, text: str) -> None:
        self._reload_cost_chart()

    @async_slot
    async def _reload_cost_chart(self) -> None:
        if not self._services:
            return
        period = self._period_combo.currentText().lower()
        cost_result = await self._services.analytics_service.get_cost_breakdown(period)
        if isinstance(cost_result, Ok):
            self._cost_chart.set_data(cost_result.ok_value)
