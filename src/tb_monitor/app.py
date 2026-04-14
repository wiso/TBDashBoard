"""Main Dash application entry point."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dash import Dash

from tb_monitor.backend.file_scanner import run_options
from tb_monitor.frontend.callbacks import register_callbacks
from tb_monitor.frontend.layout import make_layout
from tb_monitor.settings import get_settings, load_settings, set_settings


def create_app() -> Dash:
    """Create and configure the Dash app.

    Uses the current application settings (see :func:`get_settings`).

    Returns
    -------
    Dash
        The configured Dash application.
    """
    app = Dash(__name__, suppress_callback_exceptions=True)
    options = run_options(get_settings().data_dir)
    app.layout = make_layout(options)
    register_callbacks(app)
    return app


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="TB2026 Detector Monitor")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to TOML configuration file",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Directory containing ROOT run files (overrides config)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for the Dash server (overrides config)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (overrides config)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Dash debug mode",
    )
    args = parser.parse_args()

    # Load settings: config file → CLI overrides
    config_path = args.config
    if config_path is None:
        # Auto-detect config.toml next to the package or in cwd
        for candidate in [Path("config.toml"), Path(__file__).resolve().parents[2] / "config.toml"]:
            if candidate.exists():
                config_path = str(candidate)
                break

    s = load_settings(config_path)

    overrides: dict[str, object] = {}
    if args.data_dir is not None:
        overrides["data_dir"] = args.data_dir
    if args.port is not None:
        overrides["port"] = args.port
    if args.host is not None:
        overrides["host"] = args.host
    if overrides:
        s = s.replace(**overrides)

    set_settings(s)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    app = create_app()
    app.run(host=s.host, port=s.port, debug=args.debug)


if __name__ == "__main__":
    main()
