"""Process a run by dispatching batches to registered components.

Iterates each required TTree exactly once, sending batches to every
component that declared an interest in that tree.  Only one batch
of events lives in memory at a time.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from tb_monitor.backend.data_loader import iter_tree, load_metadata
from tb_monitor.components import COMPONENTS
from tb_monitor.components.base import Component


def process_run(
    path: str,
    step_size: int = 50_000,
    components: list[Component] | None = None,
) -> dict[str, Any]:
    """Process a full run, returning results for every component.

    Parameters
    ----------
    path : str
        Path to the ROOT file.
    step_size : int
        Entries per iteration batch.
    components : list[Component] | None
        Components to process.  Defaults to all registered components.

    Returns
    -------
    dict[str, Any]
        Mapping ``{component.name: finalized_results}``.
    """
    if components is None:
        components = COMPONENTS

    metadata = load_metadata(path)

    # ── Create per-component state ──────────────────────────────────
    states: dict[str, Any] = {}
    for comp in components:
        states[comp.name] = comp.create_state(path)

    # ── Group components by tree ────────────────────────────────────
    tree_to_comps: dict[str, list[Component]] = defaultdict(list)
    tree_to_branches: dict[str, set[str] | None] = {}

    for comp in components:
        for tree_name, branches in comp.tree_branches().items():
            tree_to_comps[tree_name].append(comp)
            # Merge branch lists: None (all) wins over any subset.
            if tree_name not in tree_to_branches:
                tree_to_branches[tree_name] = set(branches) if branches else None
            elif tree_to_branches[tree_name] is not None:
                if branches is None:
                    tree_to_branches[tree_name] = None
                else:
                    tree_to_branches[tree_name].update(branches)

    # ── Iterate each tree once, dispatch to components ──────────────
    for tree_name, comps in tree_to_comps.items():
        merged = tree_to_branches[tree_name]
        branch_list = sorted(merged) if merged is not None else None

        for batch in iter_tree(path, tree_name, branches=branch_list,
                               step_size=step_size):
            for comp in comps:
                comp.fill_batch(states[comp.name], tree_name, batch)

    # ── Finalize ────────────────────────────────────────────────────
    results: dict[str, Any] = {}
    for comp in components:
        result = comp.finalize(states[comp.name])
        # Attach metadata to every result that has a metadata attr.
        results[comp.name] = result

    results["_metadata"] = metadata
    return results
