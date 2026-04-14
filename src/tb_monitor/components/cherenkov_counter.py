"""Cherenkov beam counters component: ADC distributions for Cher1, Cher2, Cher3."""

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


def _cher_channels() -> dict[int, str]:
    """Return {channel: label} for Cherenkov beam counters from settings."""
    s = get_settings()
    return {
        ch: label
        for ch, label in s.special_channels.items()
        if label.startswith("Cher")
    }


@dataclass
class CherCounterState:
    """Mutable accumulators — one histogram per Cherenkov counter."""

    all_events: dict[int, hist.Hist]
    pedestal: dict[int, hist.Hist]


@dataclass(frozen=True)
class CherCounterResults:
    """Immutable results for the Cherenkov counters tab."""

    all_events: dict[int, hist.Hist]
    pedestal: dict[int, hist.Hist]
    labels: dict[int, str]


class CherenkovCounterComponent(Component):
    """ADC distributions for beam-line Cherenkov counters (all + pedestal)."""

    @property
    def name(self) -> str:
        return "cherenkov_counter"

    @property
    def label(self) -> str:
        return "Cherenkov Counters"

    def tree_branches(self) -> dict[str, list[str] | None]:
        return {"CERNSPS2025": ["ADCs", "TriggerMask"]}

    def create_state(self, path: str) -> CherCounterState:
        s = get_settings()
        channels = _cher_channels()
        def _make_hist() -> hist.Hist:
            return hist.Hist(hist.axis.Integer(s.adc_lo, s.adc_hi, name="adc", label="ADC"))
        return CherCounterState(
            all_events={ch: _make_hist() for ch in channels},
            pedestal={ch: _make_hist() for ch in channels},
        )

    def fill_batch(
        self, state: CherCounterState, tree_name: str, batch: ak.Array
    ) -> None:
        s = get_settings()
        adcs = np.asarray(batch["ADCs"], dtype=np.int64)
        mask_val = np.asarray(batch["TriggerMask"])
        ped_sel = mask_val == s.pedestal_trigger_mask

        for ch in state.all_events:
            col = adcs[:, ch]
            state.all_events[ch].fill(adc=col)
            state.pedestal[ch].fill(adc=col[ped_sel])

    def finalize(self, state: CherCounterState) -> CherCounterResults:
        return CherCounterResults(
            all_events=state.all_events,
            pedestal=state.pedestal,
            labels=_cher_channels(),
        )

    # ── frontend ────────────────────────────────────────────────────

    def tab_layout(self) -> html.Div:
        channels = _cher_channels()
        plots = []
        for ch in sorted(channels):
            label = channels[ch]
            plots.append(html.Div([
                html.H3(f"{label} (ch {ch}) ADC Distribution"),
                dcc.Graph(id=f"cher-counter-{ch}-plot"),
            ]))
        return html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "20px"},
            children=plots,
        )

    def register_callbacks(self, app, get_results) -> None:
        channels = _cher_channels()
        for ch in sorted(channels):
            self._register_one(app, get_results, ch)

    def _register_one(self, app, get_results, ch: int) -> None:
        @app.callback(
            Output(f"cher-counter-{ch}-plot", "figure"),
            Input("run-data-loaded", "data"),
            Input("theme-store", "data"),
            Input("batch-counter", "data"),
        )
        def update_cher(path: str | None, theme: str, _batch: int, _ch: int = ch) -> Any:
            if not path:
                return no_update
            r = get_results(path)
            if r is None:
                return no_update
            template = THEMES.get(theme, THEMES["light"])["plotTemplate"]

            h_all = r.all_events[_ch]
            v_all, edges = h_all.to_numpy()
            centers = 0.5 * (edges[:-1] + edges[1:])

            h_ped = r.pedestal[_ch]
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
                name=f"Pedestal (TriggerMask={get_settings().pedestal_trigger_mask})",
                fill="tozeroy", opacity=0.5,
            ))
            fig.update_layout(
                template=template,
                xaxis_title="ADC", yaxis_title="Events",
                margin=dict(l=50, r=30, t=30, b=50),
            )
            return fig
