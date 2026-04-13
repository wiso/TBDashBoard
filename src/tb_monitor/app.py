"""Main Dash application entry point."""

from __future__ import annotations

import argparse

from dash import Dash

from tb_monitor.backend.file_scanner import run_options
from tb_monitor.frontend.callbacks import register_callbacks
from tb_monitor.frontend.layout import make_layout

DEFAULT_DATA_DIR = "/home/turra/TB2025_H8/mergedNtuples"


def create_app(data_dir: str = DEFAULT_DATA_DIR) -> Dash:
    """Create and configure the Dash app.

    Parameters
    ----------
    data_dir : str
        Directory to scan for ROOT run files.

    Returns
    -------
    Dash
        The configured Dash application.
    """
    app = Dash(__name__, suppress_callback_exceptions=True)
    options = run_options(data_dir)
    app.layout = make_layout(options)
    register_callbacks(app)
    return app


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="TB2026 Detector Monitor")
    parser.add_argument(
        "--data-dir",
        default=DEFAULT_DATA_DIR,
        help="Directory containing ROOT run files",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8050,
        help="Port for the Dash server (default: 8050)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Dash debug mode",
    )
    args = parser.parse_args()

    app = create_app(data_dir=args.data_dir)
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
