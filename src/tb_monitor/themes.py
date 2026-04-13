"""Theme definitions for the dashboard."""

THEMES: dict[str, dict] = {
    "light": {
        "background": "#ffffff",
        "color": "#111111",
        "cardBg": "#f8f9fa",
        "metaColor": "#666666",
        "plotTemplate": "plotly",
    },
    "dark": {
        "background": "#1e1e2f",
        "color": "#e0e0e0",
        "cardBg": "#2a2a3d",
        "metaColor": "#aaaaaa",
        "plotTemplate": "plotly_dark",
    },
}
