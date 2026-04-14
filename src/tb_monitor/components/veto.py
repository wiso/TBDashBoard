"""Veto counter component: ADC distribution with adjustable threshold."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import awkward as ak
import hist
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from tb_monitor.components.base import Component
from tb_monitor.settings import get_settings
from tb_monitor.themes import THEMES


@dataclass
class VetoState:
    """Mutable accumulators for veto counter histogram."""

    all_events: hist.Hist
    pedestal: hist.Hist


@dataclass(frozen=True)
class VetoResults:
    """Immutable results for the veto counter tab."""

    all_events: hist.Hist
    pedestal: hist.Hist


class VetoComponent(Component):
    """Veto counter ADC distribution with threshold-based event fraction."""

    @property
    def name(self) -> str:
        return "veto"

    @property
    def label(self) -> str:
        return "Veto"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"CERNSPS2025": ["ADCs", "TriggerMask"]}

    def create_state(self, path: str) -> VetoState:
        s = get_settings()
        return VetoState(
            all_events=hist.Hist(
                hist.axis.Integer(s.adc_lo, s.adc_hi, name="adc", label="ADC"),
            ),
            pedestal=hist.Hist(
                hist.axis.Integer(s.adc_lo, s.adc_hi, name="adc", label="ADC"),
            ),
        )

    def fill_batch(self, state: VetoState, tree_name: str, batch: ak.Array) -> None:
        s = get_settings()
        adc = np.asarray(batch["ADCs"], dtype=np.int64)[:, s.veto_channel]
        mask_val = np.asarray(batch["TriggerMask"])

        state.all_events.fill(adc=adc)
        state.pedestal.fill(adc=adc[mask_val == s.pedestal_trigger_mask])

    def finalize(self, state: VetoState) -> VetoResults:
        return VetoResults(all_events=state.all_events, pedestal=state.pedestal)

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        s = get_settings()
        return html.Div([
            html.H3("Veto Counter ADC Distribution"),
            dcc.Graph(id="veto-plot"),
            html.Div(
                [
                    html.Label(
                        "Threshold:",
                        style={"fontWeight": "bold", "marginRight": "10px"},
                    ),
                    dcc.Slider(
                        id="veto-threshold",
                        min=s.adc_lo,
                        max=s.adc_hi,
                        step=1,
                        value=400,
                        marks={
                            s.adc_lo: str(s.adc_lo),
                            s.adc_hi // 4: str(s.adc_hi // 4),
                            s.adc_hi // 2: str(s.adc_hi // 2),
                            3 * s.adc_hi // 4: str(3 * s.adc_hi // 4),
                            s.adc_hi - 1: str(s.adc_hi - 1),
                        },
                        tooltip={"placement": "bottom", "always_visible": True},
                    ),
                ],
                style={"margin": "20px 50px"},
            ),
            html.Div(
                id="veto-fraction-text",
                style={
                    "textAlign": "center",
                    "fontSize": "1.2em",
                    "margin": "10px 0",
                },
            ),
        ])

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("veto-plot", "figure"),
            Output("veto-fraction-text", "children"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("veto-threshold", "value"),
            Input("batch-counter", "data"),
        )
        def update_veto(
            path: str | None, theme: str, threshold: int, _batch: int
        ) -> tuple[Any, Any]:
            if not path:
                return no_update, no_update
            r = get_results(path)
            if r is None:
                return no_update, no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]

            h = r.all_events
            values, edges = h.to_numpy()
            centers = 0.5 * (edges[:-1] + edges[1:])

            total = values.sum()
            if total > 0:
                above_mask = centers >= threshold
                above = values[above_mask].sum()
                fraction = above / total
            else:
                fraction = 0.0

            h_ped = r.pedestal
            v_ped, _ = h_ped.to_numpy()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=centers, y=values,
                mode="lines", line_shape="hvh",
                name="All events",
                fill="tozeroy", opacity=0.5,
            ))
            fig.add_trace(go.Scatter(
                x=centers, y=v_ped,
                mode="lines", line_shape="hvh",
                name="Pedestal (TriggerMask=2)",
                fill="tozeroy", opacity=0.5,
            ))
            fig.add_vline(
                x=threshold,
                line_dash="dash",
                line_color="red",
                annotation_text=f"Threshold = {threshold}",
                annotation_position="top right",
            )
            fig.update_layout(
                template=template,
                xaxis_title="ADC",
                yaxis_title="Events",
                margin=dict(l=50, r=30, t=30, b=50),
            )

            text = f"Fraction above threshold: {fraction:.4f} ({above:.0f} / {total:.0f})"
            return fig, text
