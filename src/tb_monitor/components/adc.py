"""ADC monitoring component: calorimeter channel maps and per-channel statistics.

Shows only the calorimeter channels (Scintillation 0–63 and Cherenkov 64–127),
excluding auxiliary/special channels which are in the AuxComponent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import awkward as ak
import hist
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, dcc, html, no_update

from tb_monitor.backend.channel_map import (
    cherenkov_channels,
    scintillation_channels,
)
from tb_monitor.components.base import Component
from tb_monitor.settings import get_settings
from tb_monitor.themes import THEMES


@dataclass
class ADCState:
    """Mutable accumulators for ADC data."""

    adc_2d: hist.Hist
    adc_sum: np.ndarray
    adc_sum_sq: np.ndarray
    n_events: int = 0


@dataclass(frozen=True)
class ADCResults:
    """Immutable results for the ADC tab."""

    adc_2d: hist.Hist
    mean: np.ndarray  # length _N_CHANNELS (all 224)
    std: np.ndarray
    calo_channels: np.ndarray  # indices of calo-only channels
    s_mask: np.ndarray  # bool mask into calo_channels for S
    c_mask: np.ndarray  # bool mask into calo_channels for C


class ADCComponent(Component):
    """ADC channel-map heatmap and per-channel mean/RMS."""

    @property
    def name(self) -> str:
        return "adc"

    @property
    def label(self) -> str:
        return "ADC Channels"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"CERNSPS2025": ["ADCs"]}

    def create_state(self, path: str) -> ADCState:
        s = get_settings()
        n_ch = s.n_adc_channels
        return ADCState(
            adc_2d=hist.Hist(
                hist.axis.Regular(
                    n_ch,
                    -0.5,
                    n_ch - 0.5,
                    name="channel",
                    label="ADC Channel",
                ),
                hist.axis.Integer(s.adc_lo, s.adc_hi, name="adc", label="ADC"),
            ),
            adc_sum=np.zeros(n_ch, dtype=np.float64),
            adc_sum_sq=np.zeros(n_ch, dtype=np.float64),
        )

    def fill_batch(self, state: ADCState, tree_name: str, batch: ak.Array) -> None:
        adcs = np.asarray(batch["ADCs"], dtype=np.float64)
        state.n_events += adcs.shape[0]
        n_ch = adcs.shape[1]
        ch = np.broadcast_to(np.arange(n_ch), adcs.shape).ravel()
        adcs_int = np.asarray(adcs, dtype=np.int64).ravel()
        state.adc_2d.fill(channel=ch, adc=adcs_int)
        state.adc_sum += adcs.sum(axis=0)
        state.adc_sum_sq += (adcs**2).sum(axis=0)

    def finalize(self, state: ADCState) -> ADCResults:
        s = get_settings()
        n_ch = s.n_adc_channels
        n = state.n_events
        if n == 0:
            mean = np.zeros(n_ch)
            std = np.zeros(n_ch)
        else:
            mean = state.adc_sum / n
            var = state.adc_sum_sq / n - mean**2
            np.clip(var, 0.0, None, out=var)
            std = np.sqrt(var)

        s_chs = scintillation_channels()
        c_chs = cherenkov_channels()
        calo_channels = sorted(s_chs + c_chs)
        calo_idx = np.array(calo_channels)
        s_set = set(s_chs)
        c_set = set(c_chs)
        s_mask = np.array([ch in s_set for ch in calo_channels])
        c_mask = np.array([ch in c_set for ch in calo_channels])
        return ADCResults(
            adc_2d=state.adc_2d,
            mean=mean,
            std=std,
            calo_channels=calo_idx,
            s_mask=s_mask,
            c_mask=c_mask,
        )

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        _h = {"margin": "4px 0", "fontSize": "0.95em"}
        _g = {"height": "320px"}
        return html.Div(
            [
                html.H3("Calorimeter ADC Mean per Channel (S & C)", style=_h),
                dcc.Graph(id="adc-mean-plot", style=_g),
                html.H3("ADC 2D Map (Channel vs ADC)", style=_h),
                dcc.Graph(id="adc-2d-plot", style=_g),
            ]
        )

    def register_callbacks(self, app, get_results) -> None:
        @app.callback(
            Output("adc-mean-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_adc_mean(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            r = get_results(path)
            if r is None:
                return no_update
            chs = r.calo_channels
            means = r.mean[chs]
            stds = r.std[chs]
            fig = go.Figure()
            # Scintillation trace
            fig.add_trace(
                go.Scatter(
                    x=chs[r.s_mask],
                    y=means[r.s_mask],
                    error_y=dict(type="data", array=stds[r.s_mask], visible=True),
                    mode="markers",
                    marker=dict(size=4, color="#636EFA"),
                    name="Scintillation",
                )
            )
            # Cherenkov trace
            fig.add_trace(
                go.Scatter(
                    x=chs[r.c_mask],
                    y=means[r.c_mask],
                    error_y=dict(type="data", array=stds[r.c_mask], visible=True),
                    mode="markers",
                    marker=dict(size=4, color="#EF553B"),
                    name="Cherenkov",
                )
            )
            fig.update_layout(
                template=template,
                xaxis_title="ADC Channel",
                yaxis_title="Mean ADC",
                margin=dict(l=50, r=20, t=20, b=40),
                height=310,
            )
            return fig

        @app.callback(
            Output("adc-2d-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_adc_2d(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            h = r.adc_2d
            values, xedges, yedges = h.to_numpy()
            # Restrict to calorimeter channels (0-127 excl. specials)
            s_chs = scintillation_channels()
            c_chs = cherenkov_channels()
            calo_bins = np.array(sorted(s_chs + c_chs))
            xcenters = 0.5 * (xedges[:-1] + xedges[1:])
            # Find bin indices closest to each calo channel
            bin_idx = np.searchsorted(xcenters, calo_bins)
            bin_idx = np.clip(bin_idx, 0, len(xcenters) - 1)
            fig = go.Figure(
                go.Heatmap(
                    z=values[bin_idx].T,
                    x=calo_bins,
                    y=0.5 * (yedges[:-1] + yedges[1:]),
                    colorscale="Viridis",
                )
            )
            fig.update_layout(
                template=template,
                xaxis_title="ADC Channel",
                yaxis_title="ADC Value",
                margin=dict(l=50, r=20, t=20, b=40),
                height=310,
            )
            return fig
