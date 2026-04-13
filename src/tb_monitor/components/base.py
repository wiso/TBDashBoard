"""Abstract base class for monitoring components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import awkward as ak
from dash import Dash, html


class Component(ABC):
    """A self-contained monitoring component.

    Each component declares which TTree branches it needs, how to
    accumulate statistics from batches, and how to display the results
    in the Dash frontend.  Adding a new component is as simple as:

    1. Subclass ``Component``.
    2. Register it in ``tb_monitor.components.COMPONENTS``.
    """

    # ── identity ────────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Short unique identifier (used as dict key, no spaces)."""

    @property
    @abstractmethod
    def label(self) -> str:
        """Human-readable tab label."""

    # ── backend: data requirements ──────────────────────────────────

    @abstractmethod
    def tree_branches(self) -> dict[str, list[str] | None]:
        """Declare which branches are needed from each TTree.

        Returns a mapping ``{tree_name: branch_list}``.
        Use ``None`` as the branch list to read all branches.

        Example::

            {"CERNSPS2025": ["TriggerMask", "EventTime", "EventSpill"]}
        """

    # ── backend: accumulation ───────────────────────────────────────

    @abstractmethod
    def create_state(self, path: str) -> Any:
        """Create empty accumulators for a new run.

        Parameters
        ----------
        path : str
            Path to the ROOT file (available for lightweight pre-scans
            if needed, e.g. to determine axis ranges).
        """

    @abstractmethod
    def fill_batch(self, state: Any, tree_name: str, batch: ak.Array) -> None:
        """Accumulate one batch of data into *state* (mutate in-place).

        Parameters
        ----------
        state : Any
            The object returned by :meth:`create_state`.
        tree_name : str
            Which TTree this batch came from.
        batch : ak.Array
            One batch of events.
        """

    @abstractmethod
    def finalize(self, state: Any) -> Any:
        """Convert accumulators into final results for plotting.

        Parameters
        ----------
        state : Any
            The accumulated state after all batches.

        Returns
        -------
        Any
            A results object (dataclass, dict, …) used by callbacks.
        """

    # ── frontend ────────────────────────────────────────────────────

    @abstractmethod
    def tab_layout(self) -> html.Div:
        """Return the Dash layout for this component's tab."""

    @abstractmethod
    def register_callbacks(
        self,
        app: Dash,
        get_results: callable,
    ) -> None:
        """Register Dash callbacks for this component.

        Parameters
        ----------
        app : Dash
            The Dash application.
        get_results : callable
            ``get_results(path) -> result`` returns this component's
            finalized results for the given file path.
        """
