"""Muon counter component: ADC distribution for all and pedestal events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import awkward as ak
import hist
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from tb_monitor.backend.channel_map import SPECIAL_CHANNELS
from tb_monitor.components.base import Component
from tb_monitor.themes import THEMES

_MUON_CH = 161
_ADC_BINS, _ADC_LO, _ADC_HI = 512, 0.0, 4096.0
_PEDESTAL_MASK = 2


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
        return MuonState(
            all_events=hist.Hist(
                hist.axis.Regular(_ADC_BINS, _ADC_LO, _ADC_HI, name="adc", label="ADC"),
            ),
            pedestal=hist.Hist(
                hist.axis.Regular(_ADC_BINS, _ADC_LO, _ADC_HI, name="adc", label="ADC"),
            ),
        )

    def fill_batch(self, state: MuonState, tree_name: str, batch: ak.Array) -> None:
        adc = np.asarray(batch["ADCs"], dtype=np.float64)[:, _MUON_CH]
        mask_val = np.asarray(batch["TriggerMask"])

        state.all_events.fill(adc=adc)
        state.pedestal.fill(adc=adc[mask_val == _PEDESTAL_MASK])

    def finalize(self, state: MuonState) -> MuonResults:
        return MuonResults(all_events=state.all_events, pedestal=state.pedestal)

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        return html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px"},
            children=[
                html.Div([
                    html.H3("Muon Counter ADC — All Events"),
                    dcc.Graph(id="muon-all-plot"),
                ]),
                html.Div([
                    html.H3("Muon Counter ADC — Pedestal (TriggerMask=2)"),
                    dcc.Graph(id="muon-ped-plot"),
                ]),
            ],
        )

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("muon-all-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
        )
        def update_muon_all(path: str | None, theme: str) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            h = get_results(path).all_events
            values, edges = h.to_numpy()
            centers = 0.5 * (edges[:-1] + edges[1:])
            fig = go.Figure(go.Bar(x=centers, y=values, width=edges[1] - edges[0]))
            fig.update_layout(
                template=template,
                xaxis_title="ADC", yaxis_title="Events",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig

        @app.callback(
            Output("muon-ped-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
        )
        def update_muon_ped(path: str | None, theme: str) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            h = get_results(path).pedestal
            values, edges = h.to_numpy()
            centers = 0.5 * (edges[:-1] + edges[1:])
            fig = go.Figure(go.Bar(x=centers, y=values, width=edges[1] - edges[0]))
            fig.update_layout(
                template=template,
                xaxis_title="ADC", yaxis_title="Events",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
