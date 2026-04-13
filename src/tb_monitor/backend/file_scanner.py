"""Scan directories for ROOT run files and extract run numbers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# Pattern: merged_sps2025_run990.root → run number 990
_RUN_PATTERN = re.compile(r"run(\d+)\.root$", re.IGNORECASE)


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

    for p in directory.glob("*.root"):
        m = _RUN_PATTERN.search(p.name)
        if m:
            results.append(RunFile(path=p, run_number=int(m.group(1)), filename=p.name))

    results.sort(key=lambda r: r.run_number)
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
