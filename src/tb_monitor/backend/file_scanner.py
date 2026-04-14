"""Scan directories for ROOT run files and extract run numbers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from tb_monitor.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunFile:
    """A discovered run file."""

    path: Path
    run_number: int
    filename: str


def scan_directory(directory: str | Path) -> list[RunFile]:
    """Scan a directory for ROOT files and extract run numbers.

    Parameters
    ----------
    directory : str | Path
        Path to scan for .root files.

    Returns
    -------
    list[RunFile]
        List of discovered run files, sorted by run number.
    """
    directory = Path(directory)
    results: list[RunFile] = []
    pattern = re.compile(get_settings().run_file_pattern, re.IGNORECASE)

    for p in directory.glob("*.root"):
        m = pattern.search(p.name)
        if m:
            results.append(RunFile(path=p, run_number=int(m.group(1)), filename=p.name))

    results.sort(key=lambda r: r.run_number)
    logger.info("Found %d run files in %s", len(results), directory)
    return results


def run_options(directory: str | Path) -> list[dict[str, str | int]]:
    """Return a list of dicts suitable for Dash dropdown options.

    Parameters
    ----------
    directory : str | Path
        Path to scan.

    Returns
    -------
    list[dict[str, str | int]]
        Each dict has keys 'label' and 'value'.
    """
    runs = scan_directory(directory)
    return [{"label": f"Run {r.run_number} ({r.filename})", "value": str(r.path)} for r in runs]
