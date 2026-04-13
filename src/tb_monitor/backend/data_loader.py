"""Load data from ROOT files using uproot with batch iteration.

All data is read via ``uproot.iterate`` so that only one batch lives in
memory at a time.  The metadata tree (single entry) is always small and
is loaded in full.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import awkward as ak
import uproot


def load_metadata(path: str) -> dict[str, Any]:
    """Load the RunMetaData tree (single entry, always small).

    Parameters
    ----------
    path : str
        Path to the ROOT file.

    Returns
    -------
    dict[str, Any]
        Metadata key-value pairs.
    """
    f = uproot.open(path)
    meta_tree = f["RunMetaData"]
    metadata: dict[str, Any] = {}
    for branch_name in meta_tree.keys():
        val = meta_tree[branch_name].array()
        metadata[branch_name] = val[0] if len(val) > 0 else None
    return metadata


def iter_tree(
    path: str,
    tree_name: str,
    branches: list[str] | None = None,
    step_size: int = 50_000,
) -> Iterator[ak.Array]:
    """Yield batches from a TTree without loading the full file.

    Parameters
    ----------
    path : str
        Path to the ROOT file.
    tree_name : str
        Name of the TTree to iterate over.
    branches : list[str] | None
        Subset of branches to read.  ``None`` reads all.
    step_size : int
        Number of entries per batch.

    Yields
    ------
    ak.Array
        One batch of data.
    """
    yield from uproot.iterate(
        f"{path}:{tree_name}",
        filter_name=branches,
        step_size=step_size,
    )


def tree_num_entries(path: str, tree_name: str) -> int:
    """Return the number of entries in a TTree without reading data.

    Parameters
    ----------
    path : str
        Path to the ROOT file.
    tree_name : str
        Name of the TTree.

    Returns
    -------
    int
        Number of entries.
    """
    f = uproot.open(path)
    return f[tree_name].num_entries
