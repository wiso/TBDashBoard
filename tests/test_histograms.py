"""Tests for tb_monitor.backend.histograms.process_run().

Uses mock patching to avoid real ROOT file I/O, while verifying the
dispatch logic that sends batches to the right components.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import awkward as ak
import numpy as np
import pytest

from tb_monitor.backend.histograms import process_run
from tb_monitor.components.base import Component


class FakeComponent(Component):
    """Minimal concrete component for testing dispatch logic."""

    def __init__(
        self,
        name: str,
        label: str,
        branches: dict[str, list[str] | None],
    ) -> None:
        self._name = name
        self._label = label
        self._branches = branches
        self.batches_received: list[tuple[str, int]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def label(self) -> str:
        return self._label

    def tree_branches(self) -> dict[str, list[str] | None]:
        return self._branches

    def create_state(self, path: str) -> dict:
        return {"count": 0}

    def fill_batch(self, state: dict, tree_name: str, batch: ak.Array) -> None:
        n = len(batch)
        state["count"] += n
        self.batches_received.append((tree_name, n))

    def finalize(self, state: dict) -> dict:
        return {"total_events": state["count"]}

    def tab_layout(self):
        from dash import html
        return html.Div()

    def register_callbacks(self, app, get_results) -> None:
        pass


@pytest.fixture()
def fake_metadata() -> dict[str, Any]:
    return {"runNumber": 42, "dataFormat": 1}


@pytest.fixture()
def cernsps_batches() -> list[ak.Array]:
    rng = np.random.default_rng(99)
    return [
        ak.Array({"TriggerMask": rng.choice([1, 2], size=50)}),
        ak.Array({"TriggerMask": rng.choice([1, 2], size=30)}),
    ]


@pytest.fixture()
def sipm_batches() -> list[ak.Array]:
    rng = np.random.default_rng(99)
    return [ak.Array({"SiPM_HG": rng.uniform(0, 100, size=(40, 10))})]


class TestProcessRun:
    """Tests for the process_run dispatcher."""

    def test_dispatches_to_single_component(
        self, fake_metadata: dict, cernsps_batches: list[ak.Array]
    ) -> None:
        comp = FakeComponent("test", "Test", {"CERNSPS2025": ["TriggerMask"]})

        with (
            patch("tb_monitor.backend.histograms.load_metadata", return_value=fake_metadata),
            patch("tb_monitor.backend.histograms.iter_tree") as mock_iter,
        ):
            mock_iter.return_value = iter(cernsps_batches)
            results = process_run("/fake.root", components=[comp])

        assert results["test"]["total_events"] == 80
        assert results["_metadata"]["runNumber"] == 42

    def test_dispatches_to_multiple_components_same_tree(
        self, fake_metadata: dict, cernsps_batches: list[ak.Array]
    ) -> None:
        comp_a = FakeComponent("a", "A", {"CERNSPS2025": ["TriggerMask"]})
        comp_b = FakeComponent("b", "B", {"CERNSPS2025": ["TriggerMask"]})

        with (
            patch("tb_monitor.backend.histograms.load_metadata", return_value=fake_metadata),
            patch("tb_monitor.backend.histograms.iter_tree") as mock_iter,
        ):
            mock_iter.return_value = iter(cernsps_batches)
            results = process_run("/fake.root", components=[comp_a, comp_b])

        # Both components should receive the same batches
        assert results["a"]["total_events"] == 80
        assert results["b"]["total_events"] == 80

    def test_dispatches_different_trees(
        self,
        fake_metadata: dict,
        cernsps_batches: list[ak.Array],
        sipm_batches: list[ak.Array],
    ) -> None:
        comp_main = FakeComponent("main", "Main", {"CERNSPS2025": ["TriggerMask"]})
        comp_sipm = FakeComponent("sipm", "SiPM", {"SiPM_rawTree_aligned": ["SiPM_HG"]})

        def fake_iter(path, tree_name, **kwargs):
            if tree_name == "CERNSPS2025":
                return iter(cernsps_batches)
            elif tree_name == "SiPM_rawTree_aligned":
                return iter(sipm_batches)
            return iter([])

        with (
            patch("tb_monitor.backend.histograms.load_metadata", return_value=fake_metadata),
            patch("tb_monitor.backend.histograms.iter_tree", side_effect=fake_iter),
        ):
            results = process_run("/fake.root", components=[comp_main, comp_sipm])

        assert results["main"]["total_events"] == 80
        assert results["sipm"]["total_events"] == 40

    def test_metadata_always_present(self, fake_metadata: dict) -> None:
        comp = FakeComponent("x", "X", {"CERNSPS2025": ["TriggerMask"]})

        with (
            patch("tb_monitor.backend.histograms.load_metadata", return_value=fake_metadata),
            patch("tb_monitor.backend.histograms.iter_tree", return_value=iter([])),
        ):
            results = process_run("/fake.root", components=[comp])

        assert "_metadata" in results
        assert results["_metadata"] == fake_metadata

    def test_branch_merging(self, fake_metadata: dict) -> None:
        """Two components on same tree => branches are merged."""
        comp_a = FakeComponent("a", "A", {"CERNSPS2025": ["TriggerMask"]})
        comp_b = FakeComponent("b", "B", {"CERNSPS2025": ["EventTime"]})

        with (
            patch("tb_monitor.backend.histograms.load_metadata", return_value=fake_metadata),
            patch("tb_monitor.backend.histograms.iter_tree") as mock_iter,
        ):
            mock_iter.return_value = iter([])
            process_run("/fake.root", components=[comp_a, comp_b])

            _, kwargs = mock_iter.call_args
            branches = kwargs.get("branches") or mock_iter.call_args[0][2]
            assert set(branches) == {"EventTime", "TriggerMask"}
