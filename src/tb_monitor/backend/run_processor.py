"""Background run processor with thread-safe intermediate results.

Manages a worker thread that reads a ROOT file batch-by-batch, calling
:func:`~tb_monitor.backend.histograms.iter_process_run`. After each
batch the latest finalized results and progress are stored so that
Dash interval callbacks can poll for live updates.
"""

from __future__ import annotations

import logging
import threading
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from tb_monitor.backend.histograms import iter_process_run
from tb_monitor.settings import get_settings

logger = logging.getLogger(__name__)


class RunStatus(Enum):
    """Processing status of a run."""

    IDLE = auto()
    PROCESSING = auto()
    DONE = auto()
    ERROR = auto()


@dataclass
class RunState:
    """Thread-safe snapshot of a single run's processing state."""

    status: RunStatus = RunStatus.IDLE
    progress: float = 0.0
    entries_so_far: int = 0
    results: dict[str, Any] | None = None
    error: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def snapshot(self) -> tuple[RunStatus, float, int, dict[str, Any] | None, str | None]:
        """Return a consistent snapshot of all fields."""
        with self._lock:
            return self.status, self.progress, self.entries_so_far, self.results, self.error

    def _update(
        self,
        *,
        status: RunStatus | None = None,
        progress: float | None = None,
        entries_so_far: int | None = None,
        results: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if status is not None:
                self.status = status
            if progress is not None:
                self.progress = progress
            if entries_so_far is not None:
                self.entries_so_far = entries_so_far
            if results is not None:
                self.results = results
            if error is not None:
                self.error = error


class RunProcessor:
    """Manages background processing of ROOT files.

    Each run is identified by its file path. Results are cached so that
    already-processed runs are served instantly.

    Typical usage from Dash callbacks::

        processor = get_processor()
        processor.start(path)                     # non-blocking
        status, progress, n, results, err = processor.get_state(path)
    """

    def __init__(self, max_cached: int = 8) -> None:
        self._states: dict[str, RunState] = {}
        self._lock = threading.Lock()
        self._max_cached = max_cached

    def start(self, path: str) -> None:
        """Start processing *path* in a background thread.

        If the run is already processing or done, this is a no-op.
        """
        with self._lock:
            if path in self._states:
                state = self._states[path]
                status, *_ = state.snapshot()
                if status in (RunStatus.PROCESSING, RunStatus.DONE):
                    return
            # Evict oldest entries if at capacity
            if len(self._states) >= self._max_cached:
                # Remove the first non-PROCESSING entry
                for key in list(self._states):
                    s, *_ = self._states[key].snapshot()
                    if s != RunStatus.PROCESSING:
                        del self._states[key]
                        break
            state = RunState(status=RunStatus.PROCESSING)
            self._states[path] = state

        thread = threading.Thread(
            target=self._worker,
            args=(path, state),
            daemon=True,
        )
        thread.start()
        logger.info("Started background processing: %s", path)

    def _worker(self, path: str, state: RunState) -> None:
        """Worker function — runs in a background thread."""
        try:
            step_size = get_settings().step_size
            for progress, entries, results in iter_process_run(
                path,
                step_size=step_size,
            ):
                state._update(
                    progress=progress,
                    entries_so_far=entries,
                    results=results,
                )
            state._update(status=RunStatus.DONE, progress=1.0)
            logger.info("Finished processing: %s (%d entries)", path, entries)
        except Exception:
            tb = traceback.format_exc()
            logger.exception("Error processing %s", path)
            state._update(status=RunStatus.ERROR, error=tb)

    def get_state(
        self,
        path: str,
    ) -> tuple[RunStatus, float, int, dict[str, Any] | None, str | None]:
        """Return the current processing state for *path*.

        Returns
        -------
        tuple
            ``(status, progress, entries_so_far, results, error)``
        """
        with self._lock:
            state = self._states.get(path)
        if state is None:
            return RunStatus.IDLE, 0.0, 0, None, None
        return state.snapshot()

    def get_results(self, path: str) -> dict[str, Any] | None:
        """Return the latest results (intermediate or final), or None."""
        with self._lock:
            state = self._states.get(path)
        if state is None:
            return None
        with state._lock:
            return state.results


# ── Module-level singleton ──────────────────────────────────────────
_processor: RunProcessor | None = None


def get_processor() -> RunProcessor:
    """Return the global RunProcessor (created on first call)."""
    global _processor
    if _processor is None:
        _processor = RunProcessor()
    return _processor
