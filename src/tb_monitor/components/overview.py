"""Overview component: trigger mask, event rate, events per spill."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import awkward as ak
import hist
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from tb_monitor.backend.data_loader import iter_tree
from tb_monitor.components.base import Component
from tb_monitor.settings import get_settings
from tb_monitor.themes import THEMES


@dataclass
class OverviewState:
    """Mutable accumulators filled batch-by-batch."""

    trigger_mask: hist.Hist
    event_rate: hist.Hist
    events_per_spill: hist.Hist
    n_events: int = 0


@dataclass(frozen=True)
class OverviewResults:
    """Immutable final results for the overview tab."""

    trigger_mask: hist.Hist
    event_rate: hist.Hist
    events_per_spill: hist.Hist
    n_events: int


class OverviewComponent(Component):
    """Trigger mask distribution, event rate vs time, events per spill."""

    @property
    def name(self) -> str:
        return "overview"

    @property
    def label(self) -> str:
        return "Overview"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"CERNSPS2025": ["TriggerMask", "EventTime", "EventSpill"]}

    def create_state(self, path: str) -> OverviewState:
        # Pre-scan EventTime to determine axis range.
        time_min, time_max = np.inf, -np.inf
        for batch in iter_tree(path, "CERNSPS2025", branches=["EventTime"]):
            t = np.asarray(batch["EventTime"], dtype=np.float64)
            time_min = min(time_min, float(t.min()))
            time_max = max(time_max, float(t.max()))
        if time_min >= time_max:
            time_max = time_min + 1.0

        return OverviewState(
            trigger_mask=hist.Hist(
                hist.axis.IntCategory([], name="mask", label="Trigger Mask", growth=True),
            ),
            event_rate=hist.Hist(
                hist.axis.Regular(
                    get_settings().event_rate_bins,
                    time_min,
                    time_max,
                    name="time",
                    label="Event Time",
                ),
            ),
            events_per_spill=hist.Hist(
                hist.axis.IntCategory([], name="spill", label="Spill Number", growth=True),
            ),
        )

    def fill_batch(self, state: OverviewState, tree_name: str, batch: ak.Array) -> None:
        n = len(batch)
        state.n_events += n
        state.trigger_mask.fill(mask=np.asarray(batch["TriggerMask"]))
        state.event_rate.fill(time=np.asarray(batch["EventTime"], dtype=np.float64))
        state.events_per_spill.fill(spill=np.asarray(batch["EventSpill"]))

    def finalize(self, state: OverviewState) -> OverviewResults:
        return OverviewResults(
            trigger_mask=state.trigger_mask,
            event_rate=state.event_rate,
            events_per_spill=state.events_per_spill,
            n_events=state.n_events,
        )

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        return html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px"},
            children=[
                html.Div([html.H3("Trigger Mask"), dcc.Graph(id="trigger-mask-plot")]),
                html.Div([html.H3("Event Rate vs Time"), dcc.Graph(id="event-rate-plot")]),
                html.Div([html.H3("Events per Spill"), dcc.Graph(id="events-per-spill-plot")]),
            ],
        )

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("trigger-mask-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_trigger_mask(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            h = r.trigger_mask
            labels = [str(v) for v in h.axes[0]]
            values = h.values()
            total = values.sum()
            pct = (values / total * 100) if total > 0 else values
            fig = go.Figure(
                go.Bar(
                    x=labels,
                    y=values,
                    marker_color=["#636EFA", "#EF553B"][: len(labels)],
                    text=[f"{p:.1f}%" for p in pct],
                    textposition="outside",
                )
            )
            fig.update_layout(
                template=template,
                xaxis_title="Trigger Mask",
                yaxis_title="Events",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig

        @app.callback(
            Output("event-rate-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_event_rate(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            h = r.event_rate
            values, edges = h.to_numpy()
            centers = 0.5 * (edges[:-1] + edges[1:])
            fig = go.Figure(go.Scatter(x=centers, y=values, mode="lines", line_shape="hv"))
            fig.update_layout(
                template=template,
                xaxis_title="Event Time",
                yaxis_title="Events / bin",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig

        @app.callback(
            Output("events-per-spill-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_events_per_spill(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            h = r.events_per_spill
            spills = [str(v) for v in h.axes[0]]
            values = h.values()
            fig = go.Figure(go.Bar(x=spills, y=values))
            fig.update_layout(
                template=template,
                xaxis_title="Spill Number",
                yaxis_title="Events",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
