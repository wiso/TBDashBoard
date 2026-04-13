"""Auxiliary channels component: beam counters and leakage detectors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import awkward as ak
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from tb_monitor.backend.channel_map import (
    BEAM_CHANNELS,
    LEAKAGE_CHANNELS,
    SPECIAL_CHANNELS,
)
from tb_monitor.components.base import Component
from tb_monitor.themes import THEMES


@dataclass
class AuxState:
    """Mutable accumulators for auxiliary ADC channels."""

    beam_sum: dict[int, float] = field(default_factory=lambda: {
        ch: 0.0 for ch in BEAM_CHANNELS
    })
    beam_sum_sq: dict[int, float] = field(default_factory=lambda: {
        ch: 0.0 for ch in BEAM_CHANNELS
    })
    leak_sum: np.ndarray = field(
        default_factory=lambda: np.zeros(len(LEAKAGE_CHANNELS), dtype=np.float64)
    )
    leak_sum_sq: np.ndarray = field(
        default_factory=lambda: np.zeros(len(LEAKAGE_CHANNELS), dtype=np.float64)
    )
    n_events: int = 0


@dataclass(frozen=True)
class AuxResults:
    """Immutable results for the auxiliary tab."""

    beam_mean: dict[str, float]
    beam_std: dict[str, float]
    leak_mean: np.ndarray
    leak_std: np.ndarray
    leak_labels: list[str]


class AuxComponent(Component):
    """Beam counters (muon, PS, veto, Cherenkov, tail catcher) and leakage."""

    _beam_chs = sorted(BEAM_CHANNELS.keys())
    _leak_chs = LEAKAGE_CHANNELS

    @property
    def name(self) -> str:
        return "aux"

    @property
    def label(self) -> str:
        return "Auxiliary"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"CERNSPS2025": ["ADCs"]}

    def create_state(self, path: str) -> AuxState:
        return AuxState()

    def fill_batch(self, state: AuxState, tree_name: str, batch: ak.Array) -> None:
        adcs = np.asarray(batch["ADCs"], dtype=np.float64)
        n = adcs.shape[0]
        state.n_events += n

        # Beam counters
        for ch in self._beam_chs:
            col = adcs[:, ch]
            state.beam_sum[ch] += col.sum()
            state.beam_sum_sq[ch] += (col ** 2).sum()

        # Leakage counters
        leak = adcs[:, self._leak_chs]
        state.leak_sum += leak.sum(axis=0)
        state.leak_sum_sq += (leak ** 2).sum(axis=0)

    def finalize(self, state: AuxState) -> AuxResults:
        n = state.n_events
        beam_mean: dict[str, float] = {}
        beam_std: dict[str, float] = {}

        for ch in self._beam_chs:
            label = BEAM_CHANNELS[ch]
            if n == 0:
                beam_mean[label] = 0.0
                beam_std[label] = 0.0
            else:
                m = state.beam_sum[ch] / n
                var = max(0.0, state.beam_sum_sq[ch] / n - m ** 2)
                beam_mean[label] = m
                beam_std[label] = var ** 0.5

        if n == 0:
            leak_mean = np.zeros(len(self._leak_chs))
            leak_std = np.zeros(len(self._leak_chs))
        else:
            leak_mean = state.leak_sum / n
            leak_var = state.leak_sum_sq / n - leak_mean ** 2
            np.clip(leak_var, 0.0, None, out=leak_var)
            leak_std = np.sqrt(leak_var)

        leak_labels = [SPECIAL_CHANNELS[ch] for ch in self._leak_chs]

        return AuxResults(
            beam_mean=beam_mean,
            beam_std=beam_std,
            leak_mean=leak_mean,
            leak_std=leak_std,
            leak_labels=leak_labels,
        )

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        return html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px"},
            children=[
                html.Div([
                    html.H3("Beam Counters (mean ADC)"),
                    dcc.Graph(id="aux-beam-plot"),
                ]),
                html.Div([
                    html.H3("Leakage Counters (mean ADC)"),
                    dcc.Graph(id="aux-leak-plot"),
                ]),
            ],
        )

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("aux-beam-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
        )
        def update_beam(path: str | None, theme: str) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            r = get_results(path)
            labels = list(r.beam_mean.keys())
            means = list(r.beam_mean.values())
            stds = list(r.beam_std.values())
            fig = go.Figure(go.Bar(
                x=labels, y=means,
                error_y=dict(type="data", array=stds, visible=True),
            ))
            fig.update_layout(
                template=template,
                xaxis_title="Counter", yaxis_title="Mean ADC",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig

        @app.callback(
            Output("aux-leak-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
        )
        def update_leakage(path: str | None, theme: str) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            r = get_results(path)
            fig = go.Figure(go.Bar(
                x=r.leak_labels, y=r.leak_mean,
                error_y=dict(type="data", array=r.leak_std, visible=True),
            ))
            fig.update_layout(
                template=template,
                xaxis_title="Leakage Counter", yaxis_title="Mean ADC",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
