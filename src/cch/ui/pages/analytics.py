"""Analytics page — cost and token charts."""

from __future__ import annotations

from nicegui import ui
from result import Err

from cch.ui.components.cost_chart import render_cost_chart
from cch.ui.components.model_chart import render_model_chart
from cch.ui.deps import get_services
from cch.ui.layout import error_banner, page_layout
from cch.ui.theme import COLORS


def setup() -> None:
    """Register the analytics page."""

    @ui.page("/analytics")
    async def analytics_page() -> None:
        svc = get_services()

        with page_layout("Analytics"):
            ui.label("Cost & Token Analytics").classes("text-2xl font-bold mb-4")

            # Period selector
            period = ui.select(
                {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"},
                value="daily",
                label="Period",
            ).classes("min-w-32 mb-4")

            chart_container = ui.column().classes("w-full gap-4")

            async def load_charts() -> None:
                chart_container.clear()
                with chart_container:
                    # Cost breakdown
                    with (
                        ui.card()
                        .classes("w-full p-4")
                        .style(f"background-color: {COLORS['surface']}")
                    ):
                        cost_result = await svc.analytics_service.get_cost_breakdown(
                            period=period.value or "daily"
                        )
                        if isinstance(cost_result, Err):
                            error_banner(cost_result.err_value)
                        else:
                            render_cost_chart(cost_result.ok_value, "Cost Breakdown")

                    with ui.row().classes("w-full gap-4"):
                        # Model usage
                        with (
                            ui.card()
                            .classes("flex-1 p-4")
                            .style(f"background-color: {COLORS['surface']}")
                        ):
                            model_result = await svc.analytics_service.get_model_usage()
                            if isinstance(model_result, Err):
                                ui.label("No data").classes("opacity-60")
                            else:
                                render_model_chart(model_result.ok_value, "Sessions by Model")

                        # Token usage summary
                        with (
                            ui.card()
                            .classes("flex-1 p-4")
                            .style(f"background-color: {COLORS['surface']}")
                        ):
                            ui.label("Token Usage by Model").classes("font-bold mb-2")
                            model_result2 = await svc.analytics_service.get_model_usage()
                            if isinstance(model_result2, Err):
                                ui.label("No data").classes("opacity-60")
                            else:
                                for md in model_result2.ok_value:
                                    tokens = md.get("total_output_tokens", 0)
                                    assert isinstance(tokens, int)
                                    model_name = str(md.get("model", "unknown"))
                                    with ui.row().classes("items-center gap-2"):
                                        ui.label(model_name).classes("text-sm")
                                        ui.label(f"{tokens:,} output tokens").classes(
                                            "text-xs"
                                        ).style(f"color: {COLORS['text_muted']}")

            period.on_value_change(load_charts)
            await load_charts()
