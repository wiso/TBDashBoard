"""Dash callbacks — generic wiring that delegates to components."""

from __future__ import annotations

import logging
import traceback
from functools import lru_cache
from typing import Any

from dash import Dash, Input, Output, no_update

from tb_monitor.backend.histograms import process_run
from tb_monitor.components import COMPONENTS
from tb_monitor.settings import get_settings
from tb_monitor.themes import THEMES

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _get_all_results(path: str) -> dict[str, Any]:
    """Return results for a run, caching up to 8 recent runs.

    Multiple users requesting different runs get correct results
    from their own cache entry.
    """
    logger.info("Processing run (cache miss): %s", path)
    return process_run(path, step_size=get_settings().step_size)


def register_callbacks(app: Dash) -> None:
    """Register all Dash callbacks (generic + per-component)."""

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

    # ── Generic: load run + render tab ──────────────────────────────

    @app.callback(
        Output("run-metadata", "children"),
        Output("run-data-loaded", "data"),
        Output("loading-trigger", "children"),
        Output("run-error", "children"),
        Output("run-error", "style"),
        Input("run-selector", "value"),
    )
    def load_run(path: str | None):
        hidden = {"display": "none"}
        visible = {
            "display": "block",
            "backgroundColor": "#f8d7da",
            "color": "#721c24",
            "border": "1px solid #f5c6cb",
            "borderRadius": "6px",
            "padding": "12px 16px",
            "marginBottom": "12px",
            "whiteSpace": "pre-wrap",
        }
        if not path:
            return "", no_update, no_update, "", hidden
        try:
            results = _get_all_results(path)
        except Exception:
            logger.exception("Failed to process run %s", path)
            msg = f"Error loading {path}:\n{traceback.format_exc()}"
            return "", no_update, "", msg, visible
        meta = results.get("_metadata", {})
        overview = results.get("overview")
        n_events = getattr(overview, "n_events", "?")
        info = f"Run {meta.get('runNumber', '?')} — {n_events} events"
        return info, path, "", "", hidden

    _tab_map = {f"tab-{comp.name}": comp for comp in COMPONENTS}

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
    for comp in COMPONENTS:

        def _make_getter(component_name: str):
            """Closure to capture the component name."""
            def get_results(path: str):
                return _get_all_results(path)[component_name]
            return get_results

        comp.register_callbacks(app, _make_getter(comp.name))
