"""SiPM monitoring component: per-channel statistics for HG and LG."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)


@dataclass
class SiPMState:
    """Mutable accumulators for SiPM data — uses hist Mean() storage."""

    profile_hg: hist.Hist  # Mean of HG when ADC != 0
    profile_lg: hist.Hist  # Mean of LG when ADC != 0
    zero_counts: np.ndarray  # Number of events with HG == 0
    total_counts: int


@dataclass(frozen=True)
class SiPMResults:
    """Immutable results for the SiPM tab."""

    hg_mean: np.ndarray
    hg_std: np.ndarray
    hg_n: np.ndarray
    lg_mean: np.ndarray
    lg_std: np.ndarray
    lg_n: np.ndarray
    zero_fraction: np.ndarray


def _make_profile(n_ch: int) -> hist.Hist:
    return hist.Hist(
        hist.axis.Integer(0, n_ch, name="ch"),
        storage=hist.storage.Mean(),
    )


def _extract_mean_std(profile: hist.Hist) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract population mean, std, and counts from a Mean-storage hist."""
    view = profile.view()
    counts = view.count
    mean = np.where(counts > 0, view.value, 0.0)
    sample_var = np.where(counts > 0, view.variance, 0.0)
    with np.errstate(invalid="ignore"):
        pop_var = np.where(counts > 1, sample_var * (counts - 1) / counts, 0.0)
    np.clip(pop_var, 0.0, None, out=pop_var)
    return mean, np.sqrt(pop_var), counts


class SiPMComponent(Component):
    """SiPM high-gain and low-gain per-channel mean (ADC != 0 only)."""

    @property
    def name(self) -> str:
        return "sipm"

    @property
    def label(self) -> str:
        return "SiPM"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"SiPM_rawTree_aligned": ["SiPM_HG", "SiPM_LG"]}

    def create_state(self, path: str) -> SiPMState:
        n_ch = get_settings().n_sipm_channels
        return SiPMState(
            profile_hg=_make_profile(n_ch),
            profile_lg=_make_profile(n_ch),
            zero_counts=np.zeros(n_ch, dtype=np.int64),
            total_counts=0,
        )

    def fill_batch(self, state: SiPMState, tree_name: str, batch: ak.Array) -> None:
        hg = np.asarray(batch["SiPM_HG"], dtype=np.float64)
        lg = np.asarray(batch["SiPM_LG"], dtype=np.float64)
        n_events, n_ch = hg.shape
        state.total_counts += n_events
        state.zero_counts += (hg == 0).sum(axis=0)

        # Vectorised fill: build (channel, value) pairs for all nonzero entries
        channels = np.broadcast_to(np.arange(n_ch), hg.shape)

        hg_mask = hg != 0
        if hg_mask.any():
            state.profile_hg.fill(ch=channels[hg_mask], sample=hg[hg_mask])

        lg_mask = lg != 0
        if lg_mask.any():
            state.profile_lg.fill(ch=channels[lg_mask], sample=lg[lg_mask])

    def finalize(self, state: SiPMState) -> SiPMResults:
        hg_mean, hg_std, hg_n = _extract_mean_std(state.profile_hg)
        lg_mean, lg_std, lg_n = _extract_mean_std(state.profile_lg)

        with np.errstate(invalid="ignore"):
            zero_frac = np.where(
                state.total_counts > 0,
                state.zero_counts / state.total_counts,
                0.0,
            )

        logger.info(
            "SiPM finalize: %d channels, %d total events, "
            "HG mean range [%.2f, %.2f], LG mean range [%.2f, %.2f]",
            len(hg_mean),
            state.total_counts,
            hg_mean.min(),
            hg_mean.max(),
            lg_mean.min(),
            lg_mean.max(),
        )

        return SiPMResults(
            hg_mean=hg_mean,
            hg_std=hg_std,
            hg_n=hg_n,
            lg_mean=lg_mean,
            lg_std=lg_std,
            lg_n=lg_n,
            zero_fraction=zero_frac,
        )

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        return html.Div(
            [
                html.Div(
                    style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px"},
                    children=[
                        html.Div(
                            [
                                html.H3("SiPM High-Gain Mean (ADC ≠ 0)"),
                                dcc.Graph(id="sipm-hg-mean-plot"),
                            ]
                        ),
                        html.Div(
                            [
                                html.H3("SiPM Low-Gain Mean (ADC ≠ 0)"),
                                dcc.Graph(id="sipm-lg-mean-plot"),
                            ]
                        ),
                    ],
                ),
                html.H3("SiPM Zero-ADC Fraction per Channel (HG)"),
                dcc.Graph(id="sipm-zero-fraction-plot"),
            ]
        )

    def register_callbacks(self, app, get_results) -> None:
        def _mean_bar(r_mean, r_std, r_n, template, color, ylabel):
            channels = np.arange(len(r_mean))
            with np.errstate(invalid="ignore", divide="ignore"):
                sem = np.where(r_n > 0, r_std / np.sqrt(r_n), 0.0)
            fig = go.Figure(
                go.Bar(
                    x=channels,
                    y=r_mean,
                    error_y=dict(
                        type="data",
                        array=sem,
                        visible=True,
                        thickness=1,
                        width=0,
                        color="rgba(0,0,0,0.4)",
                    ),
                    marker=dict(color=color),
                )
            )
            fig.update_layout(
                template=template,
                xaxis_title="SiPM Channel",
                yaxis_title=ylabel,
                margin=dict(l=50, r=30, t=30, b=50),
                bargap=0,
            )
            return fig

        @app.callback(
            Output("sipm-hg-mean-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_sipm_hg_mean(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            return _mean_bar(r.hg_mean, r.hg_std, r.hg_n, template, "#636EFA", "Mean High-Gain")

        @app.callback(
            Output("sipm-lg-mean-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_sipm_lg_mean(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            return _mean_bar(r.lg_mean, r.lg_std, r.lg_n, template, "#00CC96", "Mean Low-Gain")

        @app.callback(
            Output("sipm-zero-fraction-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_sipm_zero_fraction(path: str | None, theme: str, _batch: int) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]
            channels = np.arange(len(r.zero_fraction))
            fig = go.Figure(
                go.Scatter(
                    x=channels,
                    y=r.zero_fraction,
                    mode="lines",
                    line_shape="hv",
                    line=dict(color="#EF553B"),
                )
            )
            fig.update_layout(
                template=template,
                xaxis_title="SiPM Channel",
                yaxis_title="Fraction (ADC = 0)",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
