"""SiPM monitoring component: high-gain per-channel statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import awkward as ak
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from tb_monitor.components.base import Component
from tb_monitor.themes import THEMES

_N_CHANNELS = 1024


@dataclass
class SiPMState:
    """Mutable accumulators for SiPM data."""

    hg_sum: np.ndarray = field(
        default_factory=lambda: np.zeros(_N_CHANNELS, dtype=np.float64)
    )
    hg_sum_sq: np.ndarray = field(
        default_factory=lambda: np.zeros(_N_CHANNELS, dtype=np.float64)
    )
    n_events: int = 0


@dataclass(frozen=True)
class SiPMResults:
    """Immutable results for the SiPM tab."""

    hg_mean: np.ndarray
    hg_std: np.ndarray


class SiPMComponent(Component):
    """SiPM high-gain per-channel mean and RMS."""

    @property
    def name(self) -> str:
        return "sipm"

    @property
    def label(self) -> str:
        return "SiPM"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"SiPM_rawTree_aligned": ["SiPM_HG"]}

    def create_state(self, path: str) -> SiPMState:
        return SiPMState()

    def fill_batch(self, state: SiPMState, tree_name: str, batch: ak.Array) -> None:
        hg = np.asarray(batch["SiPM_HG"], dtype=np.float64)
        state.n_events += hg.shape[0]
        state.hg_sum += hg.sum(axis=0)
        state.hg_sum_sq += (hg**2).sum(axis=0)

    def finalize(self, state: SiPMState) -> SiPMResults:
        n = state.n_events
        if n == 0:
            return SiPMResults(
                hg_mean=np.zeros(_N_CHANNELS), hg_std=np.zeros(_N_CHANNELS)
            )
        mean = state.hg_sum / n
        var = state.hg_sum_sq / n - mean**2
        np.clip(var, 0.0, None, out=var)
        return SiPMResults(hg_mean=mean, hg_std=np.sqrt(var))

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        return html.Div([
            html.H3("SiPM High-Gain Mean per Channel"),
            dcc.Graph(id="sipm-hg-mean-plot"),
        ])

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("sipm-hg-mean-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
        )
        def update_sipm_hg_mean(path: str | None, theme: str) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            r = get_results(path)
            channels = np.arange(len(r.hg_mean))
            fig = go.Figure(go.Scatter(
                x=channels, y=r.hg_mean,
                error_y=dict(type="data", array=r.hg_std, visible=True),
                mode="markers", marker=dict(size=2),
            ))
            fig.update_layout(
                template=template,
                xaxis_title="SiPM Channel", yaxis_title="Mean High-Gain",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
