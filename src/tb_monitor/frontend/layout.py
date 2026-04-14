"""Dash layout — generated dynamically from registered components."""

from __future__ import annotations

from dash import dcc, html

from tb_monitor.components import COMPONENTS


def make_layout(run_options: list[dict]) -> html.Div:
    """Create the main dashboard layout.

    Tabs are generated automatically from :data:`COMPONENTS`.

    Parameters
    ----------
    run_options : list[dict]
        Dropdown options from file_scanner.run_options().

    Returns
    -------
    html.Div
        The top-level Dash layout.
    """
    tabs = [dcc.Tab(label=comp.label, value=f"tab-{comp.name}") for comp in COMPONENTS]
    default_tab = f"tab-{COMPONENTS[0].name}" if COMPONENTS else ""

    return html.Div(
        id="app-container",
        style={"fontFamily": "Arial, sans-serif", "margin": "20px"},
        children=[
            # Hidden store for theme state
            dcc.Store(id="theme-store", data="light"),
            # Header row with title + theme toggle
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "alignItems": "center",
                    "position": "relative",
                    "marginBottom": "6px",
                },
                children=[
                    html.H1(
                        "TB2026 Detector Monitor",
                        style={"textAlign": "center", "margin": "0"},
                    ),
                    html.Button(
                        "🌙",
                        id="theme-toggle",
                        n_clicks=0,
                        style={
                            "position": "absolute",
                            "right": "0",
                            "fontSize": "24px",
                            "background": "none",
                            "border": "1px solid #ccc",
                            "borderRadius": "6px",
                            "cursor": "pointer",
                            "padding": "4px 10px",
                        },
                    ),
                ],
            ),
            # Run selector
            html.Div(
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "gap": "12px",
                    "marginBottom": "20px",
                },
                children=[
                    html.Label("Run:", style={"fontWeight": "bold"}),
                    dcc.Dropdown(
                        id="run-selector",
                        options=run_options,
                        value=run_options[-1]["value"] if run_options else None,
                        placeholder="No run files found" if not run_options else "Select a run…",
                        style={"width": "500px"},
                        clearable=False,
                    ),
                    html.Div(id="run-metadata", style={"color": "#666"}),
                ],
            ),
            dcc.Store(id="run-data-loaded", data=None),
            # Batch counter — incremented after each batch; components
            # listen to this to re-render with intermediate results.
            dcc.Store(id="batch-counter", data=0),
            # Interval timer — enabled during processing, polls for updates.
            dcc.Interval(
                id="progress-interval",
                interval=500,  # ms
                disabled=True,
            ),
            # Error banner — hidden by default, shown on processing failures
            html.Div(
                id="run-error",
                style={
                    "display": "none",
                    "backgroundColor": "#f8d7da",
                    "color": "#721c24",
                    "border": "1px solid #f5c6cb",
                    "borderRadius": "6px",
                    "padding": "12px 16px",
                    "marginBottom": "12px",
                    "whiteSpace": "pre-wrap",
                },
            ),
            # Progress bar — shown during file processing
            html.Div(
                id="progress-container",
                style={"display": "none", "marginBottom": "12px"},
                children=[
                    html.Div(
                        style={
                            "display": "flex",
                            "alignItems": "center",
                            "gap": "12px",
                        },
                        children=[
                            html.Div(
                                style={
                                    "flex": "1",
                                    "height": "20px",
                                    "backgroundColor": "#e9ecef",
                                    "borderRadius": "4px",
                                    "overflow": "hidden",
                                },
                                children=[
                                    html.Div(
                                        id="progress-bar",
                                        style={
                                            "width": "0%",
                                            "height": "100%",
                                            "backgroundColor": "#636EFA",
                                            "borderRadius": "4px",
                                            "transition": "width 0.3s ease",
                                        },
                                    ),
                                ],
                            ),
                            html.Span(
                                id="progress-text",
                                style={"fontSize": "0.9em", "minWidth": "180px"},
                            ),
                        ],
                    ),
                ],
            ),
            dcc.Tabs(id="tabs", value=default_tab, children=tabs),
            html.Div(id="tab-content", style={"marginTop": "20px"}),
        ],
    )
