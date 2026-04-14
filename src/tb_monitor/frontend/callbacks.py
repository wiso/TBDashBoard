"""Dash callbacks — generic wiring that delegates to components.

Processing happens in a background thread managed by
:class:`~tb_monitor.backend.run_processor.RunProcessor`.  A
``dcc.Interval`` polls for progress and triggers component callbacks
to re-render with intermediate results after each batch.
"""

from __future__ import annotations

import logging
from typing import Any

from dash import Dash, Input, Output, State, no_update

from tb_monitor.backend.run_processor import RunStatus, get_processor
from tb_monitor.components import get_components
from tb_monitor.themes import THEMES

logger = logging.getLogger(__name__)

_ERROR_STYLE_HIDDEN: dict[str, str] = {"display": "none"}
_ERROR_STYLE_VISIBLE: dict[str, str] = {
    "display": "block",
    "backgroundColor": "#f8d7da",
    "color": "#721c24",
    "border": "1px solid #f5c6cb",
    "borderRadius": "6px",
    "padding": "12px 16px",
    "marginBottom": "12px",
    "whiteSpace": "pre-wrap",
}


def register_callbacks(app: Dash) -> None:
    """Register all Dash callbacks (generic + per-component)."""

    processor = get_processor()

    # ── Theme toggle ────────────────────────────────────────────────

    @app.callback(
        Output("theme-store", "data"),
        Output("theme-toggle", "children"),
        Input("theme-toggle", "n_clicks"),
    )
    def toggle_theme(n_clicks: int):
        theme = "dark" if n_clicks % 2 == 1 else "light"
        icon = "☀️" if theme == "dark" else "🌙"
        return theme, icon

    @app.callback(
        Output("app-container", "style"),
        Input("theme-store", "data"),
    )
    def apply_theme(theme: str):
        t = THEMES.get(theme, THEMES["light"])
        return {
            "fontFamily": "Arial, sans-serif",
            "margin": "20px",
            "minHeight": "100vh",
            "backgroundColor": t["background"],
            "color": t["color"],
        }

    # ── Run selection: start background processing ──────────────────

    @app.callback(
        Output("run-data-loaded", "data"),
        Output("batch-counter", "data", allow_duplicate=True),
        Output("progress-interval", "disabled"),
        Output("progress-container", "style"),
        Output("run-error", "children"),
        Output("run-error", "style"),
        Input("run-selector", "value"),
        prevent_initial_call="initial_duplicate",
    )
    def load_run(path: str | None):
        if not path:
            return (
                no_update,
                no_update,
                True,
                {"display": "none"},
                "",
                _ERROR_STYLE_HIDDEN,
            )
        # If already done, skip straight to results
        status, *_ = processor.get_state(path)
        if status == RunStatus.DONE:
            return (
                path,
                0,
                True,
                {"display": "none"},
                "",
                _ERROR_STYLE_HIDDEN,
            )
        # Start background processing, enable polling
        processor.start(path)
        return (
            path,
            0,
            False,
            {"display": "block", "marginBottom": "12px"},
            "",
            _ERROR_STYLE_HIDDEN,
        )

    # ── Interval: poll progress + update batch counter ──────────────

    @app.callback(
        Output("progress-bar", "style"),
        Output("progress-text", "children"),
        Output("progress-container", "style", allow_duplicate=True),
        Output("progress-interval", "disabled", allow_duplicate=True),
        Output("batch-counter", "data"),
        Output("run-metadata", "children"),
        Output("run-error", "children", allow_duplicate=True),
        Output("run-error", "style", allow_duplicate=True),
        Input("progress-interval", "n_intervals"),
        State("run-data-loaded", "data"),
        State("batch-counter", "data"),
        prevent_initial_call=True,
    )
    def poll_progress(n_intervals: int, path: str | None, current_batch: int):
        if not path:
            return (
                no_update,
                no_update,
                {"display": "none"},
                True,
                no_update,
                no_update,
                no_update,
                no_update,
            )

        status, progress, entries, results, error = processor.get_state(path)

        pct = min(progress * 100, 100)
        bar_style = {
            "width": f"{pct:.0f}%",
            "height": "100%",
            "backgroundColor": "#636EFA",
            "borderRadius": "4px",
            "transition": "width 0.3s ease",
        }
        progress_text = f"Processing… {pct:.0f}% ({entries:,} entries)"

        # Increment batch counter to trigger component re-renders
        new_batch = current_batch + 1

        if status == RunStatus.ERROR:
            msg = f"Error loading {path}:\n{error}"
            return (
                bar_style,
                progress_text,
                {"display": "none"},
                True,
                new_batch,
                "",
                msg,
                _ERROR_STYLE_VISIBLE,
            )

        if status == RunStatus.DONE:
            # Build metadata line
            meta = results.get("_metadata", {}) if results else {}
            overview = results.get("overview") if results else None
            n_events = getattr(overview, "n_events", "?")
            info = f"Run {meta.get('runNumber', '?')} — {n_events} events"
            return (
                bar_style,
                f"Done — {entries:,} entries",
                {"display": "none"},
                True,
                new_batch,
                info,
                "",
                _ERROR_STYLE_HIDDEN,
            )

        # Still processing
        return (
            bar_style,
            progress_text,
            {"display": "block", "marginBottom": "12px"},
            False,
            new_batch,
            "",
            "",
            _ERROR_STYLE_HIDDEN,
        )

    # ── Tab rendering ───────────────────────────────────────────────

    components = get_components()
    _tab_map = {f"tab-{comp.name}": comp for comp in components}

    @app.callback(
        Output("tab-content", "children"),
        Input("tabs", "value"),
    )
    def render_tab(tab: str):
        comp = _tab_map.get(tab)
        if comp is None:
            return "Unknown tab"
        return comp.tab_layout()

    # ── Per-component callbacks ─────────────────────────────────────
    for comp in components:

        def _make_getter(component_name: str):
            """Closure to capture the component name."""

            def get_results(path: str) -> Any:
                results = processor.get_results(path)
                if results is None:
                    return None
                return results.get(component_name)

            return get_results

        comp.register_callbacks(app, _make_getter(comp.name))
