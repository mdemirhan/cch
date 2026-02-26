"""Matplotlib embedded chart widget for PySide6."""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from cch.ui.theme import CHART_COLORS, COLORS

if TYPE_CHECKING:
    from cch.models.analytics import CostBreakdown, HeatmapData, ToolUsageEntry


class ChartCanvas(FigureCanvasQTAgg):
    """Base class for an embedded matplotlib chart."""

    def __init__(self, width: float = 6, height: float = 4, dpi: int = 100) -> None:
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor=COLORS["bg"])
        super().__init__(self.fig)
        self.ax = self.fig.add_subplot(111)
        self._style_axes()

    def _style_axes(self) -> None:
        self.ax.set_facecolor(COLORS["bg"])
        self.ax.tick_params(colors=COLORS["text_muted"], labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_color(COLORS["border"])


class CostChart(ChartCanvas):
    """Stacked bar chart of costs over time."""

    def set_data(self, data: list[CostBreakdown]) -> None:
        self.ax.clear()
        self._style_axes()

        if not data:
            self.ax.text(
                0.5,
                0.5,
                "No cost data",
                ha="center",
                va="center",
                color=COLORS["text_muted"],
                fontsize=12,
                transform=self.ax.transAxes,
            )
            self.draw()
            return

        dates = sorted(set(d.date for d in data))
        models = sorted(set(d.model for d in data))

        bottom = [0.0] * len(dates)
        for i, model in enumerate(models):
            model_data = {d.date: d.total_cost for d in data if d.model == model}
            values = [model_data.get(d, 0) for d in dates]
            color = CHART_COLORS[i % len(CHART_COLORS)]
            self.ax.bar(
                range(len(dates)),
                values,
                bottom=bottom,
                label=model,
                color=color,
                width=0.7,
            )
            bottom = [b + v for b, v in zip(bottom, values, strict=True)]

        # X-axis labels (show abbreviated dates)
        labels = [d[-5:] if len(d) >= 5 else d for d in dates]
        step = max(1, len(labels) // 10)
        self.ax.set_xticks(range(0, len(labels), step))
        self.ax.set_xticklabels([labels[i] for i in range(0, len(labels), step)], rotation=45)

        self.ax.set_ylabel("Cost (USD)", fontsize=10, color=COLORS["text_muted"])
        self.ax.legend(fontsize=8, framealpha=0.8)
        self.fig.tight_layout()
        self.draw()


class ModelPieChart(ChartCanvas):
    """Pie chart of model usage by session count."""

    def set_data(self, data: list[dict[str, object]]) -> None:
        self.ax.clear()
        self._style_axes()

        if not data:
            self.ax.text(
                0.5,
                0.5,
                "No model data",
                ha="center",
                va="center",
                color=COLORS["text_muted"],
                fontsize=12,
                transform=self.ax.transAxes,
            )
            self.draw()
            return

        labels = [str(d.get("model", "unknown")) for d in data]
        values = [int(d.get("session_count", 0)) for d in data]  # type: ignore[arg-type]
        colors = CHART_COLORS[: len(data)]

        result = self.ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct="%1.0f%%",
            pctdistance=0.8,
            wedgeprops={"width": 0.5},
            textprops={"fontsize": 9, "color": COLORS["text"]},
        )
        if len(result) >= 3:
            for at in result[2]:
                at.set_fontsize(8)
                at.set_color(COLORS["text_muted"])

        self.fig.tight_layout()
        self.draw()


class ToolBarChart(ChartCanvas):
    """Horizontal bar chart of tool usage."""

    def set_data(self, data: list[ToolUsageEntry]) -> None:
        self.ax.clear()
        self._style_axes()

        if not data:
            self.ax.text(
                0.5,
                0.5,
                "No tool data",
                ha="center",
                va="center",
                color=COLORS["text_muted"],
                fontsize=12,
                transform=self.ax.transAxes,
            )
            self.draw()
            return

        top = data[:15]
        names = [t.tool_name for t in reversed(top)]
        counts = [t.call_count for t in reversed(top)]

        self.ax.barh(names, counts, color=CHART_COLORS[0], height=0.6)
        self.ax.set_xlabel("Call Count", fontsize=10, color=COLORS["text_muted"])
        self.fig.tight_layout()
        self.draw()


class HeatmapChart(ChartCanvas):
    """Hour-of-day x day-of-week activity heatmap."""

    def set_data(self, data: HeatmapData) -> None:
        self.ax.clear()
        self._style_axes()

        if not data.values:
            self.ax.text(
                0.5,
                0.5,
                "No activity data",
                ha="center",
                va="center",
                color=COLORS["text_muted"],
                fontsize=12,
                transform=self.ax.transAxes,
            )
            self.draw()
            return

        import numpy as np

        values = np.array(data.values)
        im = self.ax.imshow(values, cmap="YlOrRd", aspect="auto")

        self.ax.set_xticks(range(len(data.hours)))
        self.ax.set_xticklabels([f"{h:02d}" for h in data.hours], fontsize=7)
        self.ax.set_yticks(range(len(data.days)))
        self.ax.set_yticklabels(data.days, fontsize=9)

        self.fig.colorbar(im, ax=self.ax, shrink=0.6, pad=0.02)
        self.fig.tight_layout()
        self.draw()
