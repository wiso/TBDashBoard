"""Muon counter component: ADC distribution for all and pedestal events."""

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
class MuonState:
    """Mutable accumulators for muon counter histograms."""

    all_events: hist.Hist
    pedestal: hist.Hist


@dataclass(frozen=True)
class MuonResults:
    """Immutable results for the muon counter tab."""

    all_events: hist.Hist
    pedestal: hist.Hist


class MuonComponent(Component):
    """Muon counter ADC distribution (all events and pedestal-only)."""

    @property
    def name(self) -> str:
        return "muon"

    @property
    def label(self) -> str:
        return "Muon Counter"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"CERNSPS2025": ["ADCs", "TriggerMask"]}

    def create_state(self, path: str) -> MuonState:
        s = get_settings()
        return MuonState(
            all_events=hist.Hist(
                hist.axis.Integer(s.adc_lo, s.adc_hi, name="adc", label="ADC"),
            ),
            pedestal=hist.Hist(
                hist.axis.Integer(s.adc_lo, s.adc_hi, name="adc", label="ADC"),
            ),
        )

    def fill_batch(self, state: MuonState, tree_name: str, batch: ak.Array) -> None:
        s = get_settings()
        adc = np.asarray(batch["ADCs"], dtype=np.int64)[:, s.muon_channel]
        mask_val = np.asarray(batch["TriggerMask"])

        state.all_events.fill(adc=adc)
        state.pedestal.fill(adc=adc[mask_val == s.pedestal_trigger_mask])

    def finalize(self, state: MuonState) -> MuonResults:
        return MuonResults(all_events=state.all_events, pedestal=state.pedestal)

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        return html.Div([
            html.H3("Muon Counter ADC Distribution"),
            dcc.Graph(id="muon-plot"),
        ])

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("muon-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_muon(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]

            h_all = r.all_events
            v_all, edges = h_all.to_numpy()
            centers = 0.5 * (edges[:-1] + edges[1:])
            bw = edges[1] - edges[0]

            h_ped = r.pedestal
            v_ped, _ = h_ped.to_numpy()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=centers, y=v_all,
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
            fig.update_layout(
                template=template,
                xaxis_title="ADC", yaxis_title="Events",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
