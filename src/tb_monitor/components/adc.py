"""ADC monitoring component: calorimeter channel maps and per-channel statistics.

Shows only the calorimeter channels (Scintillation 0–63 and Cherenkov 64–127),
excluding auxiliary/special channels which are in the AuxComponent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import awkward as ak
import hist
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from tb_monitor.backend.channel_map import (
    CHERENKOV_CHANNELS,
    SCINTILLATION_CHANNELS,
)
from tb_monitor.components.base import Component
from tb_monitor.themes import THEMES

_N_CHANNELS = 224
_ADC_BINS, _ADC_LO, _ADC_HI = 512, 0.0, 4096.0
_CALO_CHANNELS = sorted(SCINTILLATION_CHANNELS + CHERENKOV_CHANNELS)
_CALO_IDX = np.array(_CALO_CHANNELS)
_S_SET = frozenset(SCINTILLATION_CHANNELS)
_C_SET = frozenset(CHERENKOV_CHANNELS)


@dataclass
class ADCState:
    """Mutable accumulators for ADC data."""

    adc_2d: hist.Hist
    adc_sum: np.ndarray = field(
        default_factory=lambda: np.zeros(_N_CHANNELS, dtype=np.float64)
    )
    adc_sum_sq: np.ndarray = field(
        default_factory=lambda: np.zeros(_N_CHANNELS, dtype=np.float64)
    )
    n_events: int = 0


@dataclass(frozen=True)
class ADCResults:
    """Immutable results for the ADC tab."""

    adc_2d: hist.Hist
    mean: np.ndarray       # length _N_CHANNELS (all 224)
    std: np.ndarray
    calo_channels: np.ndarray   # indices of calo-only channels
    s_mask: np.ndarray          # bool mask into calo_channels for S
    c_mask: np.ndarray          # bool mask into calo_channels for C


class ADCComponent(Component):
    """ADC channel-map heatmap and per-channel mean/RMS."""

    _channels = np.arange(_N_CHANNELS)

    @property
    def name(self) -> str:
        return "adc"

    @property
    def label(self) -> str:
        return "ADC Channels"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"CERNSPS2025": ["ADCs"]}

    def create_state(self, path: str) -> ADCState:
        return ADCState(
            adc_2d=hist.Hist(
                hist.axis.Regular(
                    _N_CHANNELS, -0.5, _N_CHANNELS - 0.5,
                    name="channel", label="ADC Channel",
                ),
                hist.axis.Regular(_ADC_BINS, _ADC_LO, _ADC_HI, name="adc", label="ADC"),
            ),
        )

    def fill_batch(self, state: ADCState, tree_name: str, batch: ak.Array) -> None:
        adcs = np.asarray(batch["ADCs"], dtype=np.float64)
        state.n_events += adcs.shape[0]
        ch = np.broadcast_to(self._channels, adcs.shape).ravel()
        state.adc_2d.fill(channel=ch, adc=adcs.ravel())
        state.adc_sum += adcs.sum(axis=0)
        state.adc_sum_sq += (adcs**2).sum(axis=0)

    def finalize(self, state: ADCState) -> ADCResults:
        n = state.n_events
        if n == 0:
            mean = np.zeros(_N_CHANNELS)
            std = np.zeros(_N_CHANNELS)
        else:
            mean = state.adc_sum / n
            var = state.adc_sum_sq / n - mean**2
            np.clip(var, 0.0, None, out=var)
            std = np.sqrt(var)

        s_mask = np.array([ch in _S_SET for ch in _CALO_CHANNELS])
        c_mask = np.array([ch in _C_SET for ch in _CALO_CHANNELS])
        return ADCResults(
            adc_2d=state.adc_2d, mean=mean, std=std,
            calo_channels=_CALO_IDX, s_mask=s_mask, c_mask=c_mask,
        )

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        return html.Div([
            html.H3("Calorimeter ADC Mean per Channel (S & C)"),
            dcc.Graph(id="adc-mean-plot"),
            html.H3("ADC 2D Map (Channel vs ADC)"),
            dcc.Graph(id="adc-2d-plot"),
        ])

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("adc-mean-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
        )
        def update_adc_mean(path: str | None, theme: str) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            r = get_results(path)
            chs = r.calo_channels
            means = r.mean[chs]
            stds = r.std[chs]
            fig = go.Figure()
            # Scintillation trace
            fig.add_trace(go.Scatter(
                x=chs[r.s_mask], y=means[r.s_mask],
                error_y=dict(type="data", array=stds[r.s_mask], visible=True),
                mode="markers", marker=dict(size=4, color="#636EFA"),
                name="Scintillation",
            ))
            # Cherenkov trace
            fig.add_trace(go.Scatter(
                x=chs[r.c_mask], y=means[r.c_mask],
                error_y=dict(type="data", array=stds[r.c_mask], visible=True),
                mode="markers", marker=dict(size=4, color="#EF553B"),
                name="Cherenkov",
            ))
            fig.update_layout(
                template=template,
                xaxis_title="ADC Channel", yaxis_title="Mean ADC",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig

        @app.callback(
            Output("adc-2d-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
        )
        def update_adc_2d(path: str | None, theme: str) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            h = get_results(path).adc_2d
            values, xedges, yedges = h.to_numpy()
            # Restrict to calorimeter channels (0-127 excl. specials)
            calo_bins = _CALO_IDX
            xcenters = 0.5 * (xedges[:-1] + xedges[1:])
            # Find bin indices closest to each calo channel
            bin_idx = np.searchsorted(xcenters, calo_bins)
            bin_idx = np.clip(bin_idx, 0, len(xcenters) - 1)
            fig = go.Figure(go.Heatmap(
                z=values[bin_idx].T,
                x=calo_bins,
                y=0.5 * (yedges[:-1] + yedges[1:]),
                colorscale="Viridis",
            ))
            fig.update_layout(
                template=template,
                xaxis_title="ADC Channel", yaxis_title="ADC Value",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
