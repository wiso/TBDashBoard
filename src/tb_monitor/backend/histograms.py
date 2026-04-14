"""Process a run by dispatching batches to registered components.

Iterates each required TTree exactly once, sending batches to every
component that declared an interest in that tree.  Only one batch
of events lives in memory at a time.

Two entry points:

* :func:`process_run` — blocking, returns final results.
* :func:`iter_process_run` — generator, yields ``(progress, results)``
  after every batch so the UI can update live.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Iterator
from typing import Any

from tb_monitor.backend.data_loader import iter_tree, load_metadata, tree_num_entries
from tb_monitor.components import get_components
from tb_monitor.components.base import Component

logger = logging.getLogger(__name__)


def _prepare_run(
    path: str,
    components: list[Component] | None = None,
) -> tuple[
    list[Component],
    dict[str, Any],
    dict[str, Any],
    dict[str, list[Component]],
    dict[str, list[str] | None],
    int,
]:
    """Shared setup for process_run / iter_process_run.

    Returns (components, metadata, states, tree_to_comps,
             tree_to_branches, total_entries).
    """
    if components is None:
        components = get_components()

    metadata = load_metadata(path)

    # Per-component state
    states: dict[str, Any] = {}
    for comp in components:
        states[comp.name] = comp.create_state(path)

    # Group components by tree
    tree_to_comps: dict[str, list[Component]] = defaultdict(list)
    tree_to_branches: dict[str, set[str] | None] = {}

    for comp in components:
        for tree_name, branches in comp.tree_branches().items():
            tree_to_comps[tree_name].append(comp)
            if tree_name not in tree_to_branches:
                tree_to_branches[tree_name] = set(branches) if branches else None
            elif tree_to_branches[tree_name] is not None:
                if branches is None:
                    tree_to_branches[tree_name] = None
                else:
                    tree_to_branches[tree_name].update(branches)

    # Count total entries across all trees for progress tracking
    total_entries = 0
    for tree_name in tree_to_comps:
        try:
            total_entries += tree_num_entries(path, tree_name)
        except Exception:
            logger.debug("Could not count entries for %s", tree_name)

    resolved: dict[str, list[str] | None] = {}
    for tree_name, merged in tree_to_branches.items():
        resolved[tree_name] = sorted(merged) if merged is not None else None

    return components, metadata, states, tree_to_comps, resolved, total_entries


def _finalize_all(
    components: list[Component],
    states: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Run finalize() on every component and attach metadata."""
    results: dict[str, Any] = {}
    for comp in components:
        results[comp.name] = comp.finalize(states[comp.name])
    results["_metadata"] = metadata
    return results


def iter_process_run(
    path: str,
    step_size: int = 50_000,
    components: list[Component] | None = None,
) -> Iterator[tuple[float, int, dict[str, Any]]]:
    """Process a run, yielding intermediate results after each batch.

    Yields
    ------
    tuple[float, int, dict[str, Any]]
        ``(progress, entries_so_far, results)`` where *progress* is
        a fraction in ``[0, 1]``, *entries_so_far* is the running
        count of processed entries, and *results* contains the
        intermediate finalized output for every component.
    """
    (
        components,
        metadata,
        states,
        tree_to_comps,
        tree_to_branches,
        total_entries,
    ) = _prepare_run(path, components)

    t0 = time.perf_counter()
    logger.info("Processing run %s with %d components", path, len(components))

    entries_so_far = 0
    yielded = False
    for tree_name, comps in tree_to_comps.items():
        branch_list = tree_to_branches[tree_name]
        n_batches = 0
        n_entries = 0
        for batch in iter_tree(path, tree_name, branches=branch_list, step_size=step_size):
            n_batches += 1
            batch_len = len(batch)
            n_entries += batch_len
            entries_so_far += batch_len
            for comp in comps:
                comp.fill_batch(states[comp.name], tree_name, batch)

            progress = entries_so_far / total_entries if total_entries > 0 else 1.0
            yielded = True
            yield progress, entries_so_far, _finalize_all(components, states, metadata)

        logger.info(
            "Tree %s: %d batches, %d entries → %d components",
            tree_name,
            n_batches,
            n_entries,
            len(comps),
        )

    # Always yield at least once (handles empty trees / zero entries).
    if not yielded:
        yield 1.0, 0, _finalize_all(components, states, metadata)

    elapsed = time.perf_counter() - t0
    logger.info("Run processed in %.2fs", elapsed)


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
    results: dict[str, Any] = {}
    for _progress, _entries, results in iter_process_run(
        path,
        step_size=step_size,
        components=components,
    ):
        pass
    return results
