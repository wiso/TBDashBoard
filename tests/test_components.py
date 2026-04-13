"""Tests for individual component accumulation logic.

Tests use synthetic awkward arrays, not real ROOT files.
"""

from __future__ import annotations

import awkward as ak
import hist
import numpy as np
import pytest

from tb_monitor.backend.channel_map import (
    AUX_CHANNEL_SET,
    CHERENKOV_CHANNELS,
    SCINTILLATION_CHANNELS,
)
from tb_monitor.components.adc import ADCComponent, ADCResults, ADCState
from tb_monitor.components.aux import AuxComponent, AuxResults
from tb_monitor.components.muon import MuonComponent, MuonResults
from tb_monitor.components.overview import (
    OverviewComponent,
    OverviewResults,
    OverviewState,
)
from tb_monitor.components.sipm import SiPMComponent, SiPMResults, SiPMState


# ── Overview Component ──────────────────────────────────────────────


class TestOverviewComponent:
    """Tests for OverviewComponent batch accumulation and finalize."""

    @pytest.fixture()
    def comp(self) -> OverviewComponent:
        return OverviewComponent()

    @pytest.fixture()
    def state(self) -> OverviewState:
        """Manually create a state (bypasses create_state file pre-scan)."""
        return OverviewState(
            trigger_mask=hist.Hist(
                hist.axis.IntCategory([], name="mask", growth=True),
            ),
            event_rate=hist.Hist(
                hist.axis.Regular(50, 1000.0, 2000.0, name="time"),
            ),
            events_per_spill=hist.Hist(
                hist.axis.IntCategory([], name="spill", growth=True),
            ),
        )

    def test_name_and_label(self, comp: OverviewComponent) -> None:
        assert comp.name == "overview"
        assert comp.label == "Overview"

    def test_tree_branches(self, comp: OverviewComponent) -> None:
        tb = comp.tree_branches()
        assert "CERNSPS2025" in tb
        assert "TriggerMask" in tb["CERNSPS2025"]
        assert "EventTime" in tb["CERNSPS2025"]
        assert "EventSpill" in tb["CERNSPS2025"]

    def test_fill_and_finalize(
        self,
        comp: OverviewComponent,
        state: OverviewState,
        cernsps_batch: ak.Array,
    ) -> None:
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert isinstance(result, OverviewResults)
        assert result.n_events == 100
        assert result.trigger_mask.sum() == 100
        assert result.events_per_spill.sum() == 100

    def test_multiple_batches_accumulate(
        self,
        comp: OverviewComponent,
        state: OverviewState,
        cernsps_batch: ak.Array,
    ) -> None:
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert result.n_events == 200
        assert result.trigger_mask.sum() == 200

    def test_empty_finalize(
        self,
        comp: OverviewComponent,
        state: OverviewState,
    ) -> None:
        result = comp.finalize(state)
        assert result.n_events == 0
        assert result.trigger_mask.sum() == 0


# ── ADC Component ───────────────────────────────────────────────────


class TestADCComponent:
    """Tests for ADCComponent batch accumulation and finalize."""

    @pytest.fixture()
    def comp(self) -> ADCComponent:
        return ADCComponent()

    def test_name_and_label(self, comp: ADCComponent) -> None:
        assert comp.name == "adc"
        assert comp.label == "ADC Channels"

    def test_tree_branches(self, comp: ADCComponent) -> None:
        assert comp.tree_branches() == {"CERNSPS2025": ["ADCs"]}

    def test_fill_and_finalize(
        self, comp: ADCComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert isinstance(result, ADCResults)
        assert result.mean.shape == (224,)
        assert result.std.shape == (224,)
        # Mean should be roughly in the middle of 0-4096
        assert 1500 < result.mean.mean() < 2500

    def test_calo_channels_exclude_aux(
        self, comp: ADCComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        # calo_channels should only contain S and C channels
        calo_set = set(result.calo_channels.tolist())
        assert calo_set == set(SCINTILLATION_CHANNELS + CHERENKOV_CHANNELS)
        assert calo_set.isdisjoint(AUX_CHANNEL_SET)
        # s_mask and c_mask should partition calo_channels
        assert result.s_mask.sum() == len(SCINTILLATION_CHANNELS)
        assert result.c_mask.sum() == len(CHERENKOV_CHANNELS)
        assert (result.s_mask | result.c_mask).all()

    def test_online_mean_matches_direct(
        self, comp: ADCComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        adcs = np.asarray(cernsps_batch["ADCs"], dtype=np.float64)
        np.testing.assert_allclose(result.mean, adcs.mean(axis=0), atol=1e-10)
        np.testing.assert_allclose(result.std, adcs.std(axis=0), atol=1e-10)

    def test_2d_histogram_shape(
        self, comp: ADCComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        val, xedges, yedges = result.adc_2d.to_numpy()
        assert val.shape == (224, 512)
        # Total entries should equal n_events × n_channels
        assert result.adc_2d.sum() == 100 * 224

    def test_empty_finalize(self, comp: ADCComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        np.testing.assert_array_equal(result.mean, np.zeros(224))
        np.testing.assert_array_equal(result.std, np.zeros(224))

    def test_two_batch_accumulation(
        self, comp: ADCComponent, rng: np.random.Generator
    ) -> None:
        """Verify that two-batch online stats match full-array computation."""
        n_ch = 224
        a1 = rng.integers(0, 4096, size=(60, n_ch)).astype(np.float64)
        a2 = rng.integers(0, 4096, size=(40, n_ch)).astype(np.float64)

        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", ak.Array({"ADCs": a1}))
        comp.fill_batch(state, "CERNSPS2025", ak.Array({"ADCs": a2}))
        result = comp.finalize(state)

        combined = np.concatenate([a1, a2], axis=0)
        np.testing.assert_allclose(result.mean, combined.mean(axis=0), atol=1e-10)
        np.testing.assert_allclose(result.std, combined.std(axis=0), atol=1e-10)


# ── Aux Component ───────────────────────────────────────────────────


class TestAuxComponent:
    """Tests for AuxComponent batch accumulation and finalize."""

    @pytest.fixture()
    def comp(self) -> AuxComponent:
        return AuxComponent()

    def test_name_and_label(self, comp: AuxComponent) -> None:
        assert comp.name == "aux"
        assert comp.label == "Auxiliary"

    def test_tree_branches(self, comp: AuxComponent) -> None:
        assert comp.tree_branches() == {"CERNSPS2025": ["ADCs"]}

    def test_fill_and_finalize(
        self, comp: AuxComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert isinstance(result, AuxResults)
        # Beam counters: PS, Veto, Tail Catcher, Muon, Cher1-3
        assert "Muon" in result.beam_mean
        assert "PS" in result.beam_mean
        assert len(result.beam_mean) == 7
        # Leakage counters: L1-L16
        assert len(result.leak_labels) == 16
        assert result.leak_mean.shape == (16,)
        assert result.leak_std.shape == (16,)

    def test_beam_mean_matches_direct(
        self, comp: AuxComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        adcs = np.asarray(cernsps_batch["ADCs"], dtype=np.float64)
        # Check muon counter (channel 161)
        expected_mean = adcs[:, 161].mean()
        np.testing.assert_allclose(result.beam_mean["Muon"], expected_mean, atol=1e-10)

    def test_leakage_mean_matches_direct(
        self, comp: AuxComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        adcs = np.asarray(cernsps_batch["ADCs"], dtype=np.float64)
        expected = adcs[:, 128:144].mean(axis=0)
        np.testing.assert_allclose(result.leak_mean, expected, atol=1e-10)

    def test_empty_finalize(self, comp: AuxComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        assert all(v == 0.0 for v in result.beam_mean.values())
        np.testing.assert_array_equal(result.leak_mean, np.zeros(16))


# ── SiPM Component ─────────────────────────────────────────────────


class TestSiPMComponent:
    """Tests for SiPMComponent batch accumulation and finalize."""

    @pytest.fixture()
    def comp(self) -> SiPMComponent:
        return SiPMComponent()

    def test_name_and_label(self, comp: SiPMComponent) -> None:
        assert comp.name == "sipm"
        assert comp.label == "SiPM"

    def test_tree_branches(self, comp: SiPMComponent) -> None:
        assert comp.tree_branches() == {"SiPM_rawTree_aligned": ["SiPM_HG"]}

    def test_fill_and_finalize(
        self, comp: SiPMComponent, sipm_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "SiPM_rawTree_aligned", sipm_batch)
        result = comp.finalize(state)

        assert isinstance(result, SiPMResults)
        assert result.hg_mean.shape == (1024,)
        assert result.hg_std.shape == (1024,)

    def test_online_mean_matches_direct(
        self, comp: SiPMComponent, sipm_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "SiPM_rawTree_aligned", sipm_batch)
        result = comp.finalize(state)

        hg = np.asarray(sipm_batch["SiPM_HG"], dtype=np.float64)
        np.testing.assert_allclose(result.hg_mean, hg.mean(axis=0), atol=1e-10)
        np.testing.assert_allclose(result.hg_std, hg.std(axis=0), atol=1e-10)

    def test_empty_finalize(self, comp: SiPMComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        np.testing.assert_array_equal(result.hg_mean, np.zeros(1024))
        np.testing.assert_array_equal(result.hg_std, np.zeros(1024))

    def test_two_batch_accumulation(
        self, comp: SiPMComponent, rng: np.random.Generator
    ) -> None:
        n_ch = 1024
        a1 = rng.uniform(0, 500, size=(50, n_ch))
        a2 = rng.uniform(0, 500, size=(30, n_ch))

        state = comp.create_state("")
        comp.fill_batch(state, "SiPM_rawTree_aligned", ak.Array({"SiPM_HG": a1}))
        comp.fill_batch(state, "SiPM_rawTree_aligned", ak.Array({"SiPM_HG": a2}))
        result = comp.finalize(state)

        combined = np.concatenate([a1, a2], axis=0)
        np.testing.assert_allclose(
            result.hg_mean, combined.mean(axis=0), atol=1e-10
        )
        np.testing.assert_allclose(
            result.hg_std, combined.std(axis=0), atol=1e-10
        )


# ── Muon Component ──────────────────────────────────────────────────


class TestMuonComponent:
    """Tests for MuonComponent batch accumulation and finalize."""

    @pytest.fixture()
    def comp(self) -> MuonComponent:
        return MuonComponent()

    def test_name_and_label(self, comp: MuonComponent) -> None:
        assert comp.name == "muon"
        assert comp.label == "Muon Counter"

    def test_tree_branches(self, comp: MuonComponent) -> None:
        tb = comp.tree_branches()
        assert "CERNSPS2025" in tb
        assert "ADCs" in tb["CERNSPS2025"]
        assert "TriggerMask" in tb["CERNSPS2025"]

    def test_fill_and_finalize(
        self, comp: MuonComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert isinstance(result, MuonResults)
        assert result.all_events.sum() == 100
        # Pedestal is subset of all events
        assert result.pedestal.sum() <= result.all_events.sum()

    def test_pedestal_filters_by_trigger_mask(
        self, comp: MuonComponent, rng: np.random.Generator
    ) -> None:
        """Only events with TriggerMask==2 go into the pedestal histogram."""
        n = 200
        n_adc = 224
        masks = np.array([1] * 120 + [2] * 80)
        rng.shuffle(masks)
        batch = ak.Array({
            "ADCs": rng.integers(0, 4096, size=(n, n_adc)).astype(np.float64),
            "TriggerMask": masks,
        })

        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", batch)
        result = comp.finalize(state)

        assert result.all_events.sum() == 200
        assert result.pedestal.sum() == 80

    def test_empty_finalize(self, comp: MuonComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        assert result.all_events.sum() == 0
        assert result.pedestal.sum() == 0
