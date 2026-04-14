"""Tests for individual component accumulation logic.

Tests use synthetic awkward arrays, not real ROOT files.
"""

from __future__ import annotations

import awkward as ak
import hist
import numpy as np
import pytest

from tb_monitor.backend.channel_map import (
    aux_channel_set,
    cherenkov_channels,
    scintillation_channels,
)
from tb_monitor.components.adc import ADCComponent, ADCResults
from tb_monitor.components.aux import AuxComponent, AuxResults
from tb_monitor.components.cherenkov_counter import CherCounterResults, CherenkovCounterComponent
from tb_monitor.components.muon import MuonComponent, MuonResults
from tb_monitor.components.overview import (
    OverviewComponent,
    OverviewResults,
    OverviewState,
)
from tb_monitor.components.sipm import SiPMComponent, SiPMResults
from tb_monitor.components.veto import VetoComponent, VetoResults

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

    def test_fill_and_finalize(self, comp: ADCComponent, cernsps_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert isinstance(result, ADCResults)
        assert result.mean.shape == (224,)
        assert result.std.shape == (224,)
        # Mean should be roughly in the middle of 0-4096
        assert 1500 < result.mean.mean() < 2500

    def test_calo_channels_exclude_aux(self, comp: ADCComponent, cernsps_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        # calo_channels should only contain S and C channels
        calo_set = set(result.calo_channels.tolist())
        s_chs = scintillation_channels()
        c_chs = cherenkov_channels()
        assert calo_set == set(s_chs + c_chs)
        assert calo_set.isdisjoint(aux_channel_set())
        # s_mask and c_mask should partition calo_channels
        assert result.s_mask.sum() == len(s_chs)
        assert result.c_mask.sum() == len(c_chs)
        assert (result.s_mask | result.c_mask).all()

    def test_online_mean_matches_direct(self, comp: ADCComponent, cernsps_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        adcs = np.asarray(cernsps_batch["ADCs"], dtype=np.float64)
        np.testing.assert_allclose(result.mean, adcs.mean(axis=0), atol=1e-10)
        np.testing.assert_allclose(result.std, adcs.std(axis=0), atol=1e-10)

    def test_2d_histogram_shape(self, comp: ADCComponent, cernsps_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        val, xedges, yedges = result.adc_2d.to_numpy()
        assert val.shape == (224, 4096)
        # Total entries should equal n_events × n_channels
        assert result.adc_2d.sum() == 100 * 224

    def test_empty_finalize(self, comp: ADCComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        np.testing.assert_array_equal(result.mean, np.zeros(224))
        np.testing.assert_array_equal(result.std, np.zeros(224))

    def test_two_batch_accumulation(self, comp: ADCComponent, rng: np.random.Generator) -> None:
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

    def test_fill_and_finalize(self, comp: AuxComponent, cernsps_batch: ak.Array) -> None:
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

    def test_beam_mean_matches_direct(self, comp: AuxComponent, cernsps_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        adcs = np.asarray(cernsps_batch["ADCs"], dtype=np.float64)
        # Check muon counter (channel 161)
        expected_mean = adcs[:, 161].mean()
        np.testing.assert_allclose(result.beam_mean["Muon"], expected_mean, atol=1e-10)

    def test_leakage_mean_matches_direct(self, comp: AuxComponent, cernsps_batch: ak.Array) -> None:
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
        assert comp.tree_branches() == {"SiPM_rawTree_aligned": ["SiPM_HG", "SiPM_LG"]}

    def test_fill_and_finalize(self, comp: SiPMComponent, sipm_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "SiPM_rawTree_aligned", sipm_batch)
        result = comp.finalize(state)

        assert isinstance(result, SiPMResults)
        assert result.hg_mean.shape == (1024,)
        assert result.hg_std.shape == (1024,)
        assert result.lg_mean.shape == (1024,)
        assert result.lg_std.shape == (1024,)
        assert result.zero_fraction.shape == (1024,)

    def test_online_mean_matches_direct(self, comp: SiPMComponent, sipm_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "SiPM_rawTree_aligned", sipm_batch)
        result = comp.finalize(state)

        # Fixture has no exact zeros, so mean over nonzero == mean over all
        hg = np.asarray(sipm_batch["SiPM_HG"], dtype=np.float64)
        np.testing.assert_allclose(result.hg_mean, hg.mean(axis=0), atol=1e-10)
        np.testing.assert_allclose(result.hg_std, hg.std(axis=0), atol=1e-10)
        lg = np.asarray(sipm_batch["SiPM_LG"], dtype=np.float64)
        np.testing.assert_allclose(result.lg_mean, lg.mean(axis=0), atol=1e-10)

    def test_empty_finalize(self, comp: SiPMComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        np.testing.assert_array_equal(result.hg_mean, np.zeros(1024))
        np.testing.assert_array_equal(result.hg_std, np.zeros(1024))
        np.testing.assert_array_equal(result.lg_mean, np.zeros(1024))
        np.testing.assert_array_equal(result.lg_std, np.zeros(1024))
        np.testing.assert_array_equal(result.zero_fraction, np.zeros(1024))

    def test_two_batch_accumulation(self, comp: SiPMComponent, rng: np.random.Generator) -> None:
        n_ch = 1024
        a1_hg = rng.uniform(0, 500, size=(50, n_ch))
        a1_lg = rng.uniform(0, 200, size=(50, n_ch))
        a2_hg = rng.uniform(0, 500, size=(30, n_ch))
        a2_lg = rng.uniform(0, 200, size=(30, n_ch))

        state = comp.create_state("")
        comp.fill_batch(
            state, "SiPM_rawTree_aligned", ak.Array({"SiPM_HG": a1_hg, "SiPM_LG": a1_lg})
        )
        comp.fill_batch(
            state, "SiPM_rawTree_aligned", ak.Array({"SiPM_HG": a2_hg, "SiPM_LG": a2_lg})
        )
        result = comp.finalize(state)

        combined_hg = np.concatenate([a1_hg, a2_hg], axis=0)
        np.testing.assert_allclose(result.hg_mean, combined_hg.mean(axis=0), atol=1e-10)
        np.testing.assert_allclose(result.hg_std, combined_hg.std(axis=0), atol=1e-10)
        combined_lg = np.concatenate([a1_lg, a2_lg], axis=0)
        np.testing.assert_allclose(result.lg_mean, combined_lg.mean(axis=0), atol=1e-10)

    def test_zero_fraction(self, comp: SiPMComponent, rng: np.random.Generator) -> None:
        n_ch = 1024
        hg = rng.uniform(1, 500, size=(100, n_ch))
        lg = rng.uniform(1, 200, size=(100, n_ch))
        # Set first 20 events of channel 0 to zero
        hg[:20, 0] = 0.0

        state = comp.create_state("")
        comp.fill_batch(state, "SiPM_rawTree_aligned", ak.Array({"SiPM_HG": hg, "SiPM_LG": lg}))
        result = comp.finalize(state)

        assert result.zero_fraction[0] == pytest.approx(0.2)
        assert result.zero_fraction[1] == pytest.approx(0.0)
        # HG mean for ch 0 should only consider nonzero entries
        np.testing.assert_allclose(result.hg_mean[0], hg[20:, 0].mean(), atol=1e-10)

    def test_saturation_fractions(self, comp: SiPMComponent, rng: np.random.Generator) -> None:
        n_ch = 1024
        hg = rng.uniform(100, 200, size=(100, n_ch))
        lg = rng.uniform(50, 100, size=(100, n_ch))
        # Force channel 0 HG above 3800 for 30 events
        hg[:30, 0] = 3900.0
        # Force channel 1 HG above 4096 for 10 events
        hg[:10, 1] = 4096.0

        state = comp.create_state("")
        comp.fill_batch(state, "SiPM_rawTree_aligned", ak.Array({"SiPM_HG": hg, "SiPM_LG": lg}))
        result = comp.finalize(state)

        thresholds = result.sat_thresholds
        assert 3800 in thresholds
        assert 4096 in thresholds
        assert result.sat_frac_hg.shape == (len(thresholds), n_ch)
        assert result.sat_frac_lg.shape == (len(thresholds), n_ch)

        # Check ch 0: 30/100 events >= 3800
        idx_3800 = list(thresholds).index(3800)
        assert result.sat_frac_hg[idx_3800, 0] == pytest.approx(0.3)
        # ch 0 has 30 events >= 3900 but < 4096 → 0 events >= 4096
        idx_4096 = list(thresholds).index(4096)
        assert result.sat_frac_hg[idx_4096, 0] == pytest.approx(0.0)
        # ch 1: 10 events == 4096 → >= 4096
        assert result.sat_frac_hg[idx_4096, 1] == pytest.approx(0.1)
        # ch 2 should have 0 saturation at 3800 (values 100-200)
        assert result.sat_frac_hg[idx_3800, 2] == pytest.approx(0.0)


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

    def test_fill_and_finalize(self, comp: MuonComponent, cernsps_batch: ak.Array) -> None:
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
        batch = ak.Array(
            {
                "ADCs": rng.integers(0, 4096, size=(n, n_adc)).astype(np.float64),
                "TriggerMask": masks,
            }
        )

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


# ── Cherenkov Counter Component ─────────────────────────────────────


class TestCherenkovCounterComponent:
    """Tests for CherenkovCounterComponent batch accumulation and finalize."""

    @pytest.fixture()
    def comp(self) -> CherenkovCounterComponent:
        return CherenkovCounterComponent()

    def test_name_and_label(self, comp: CherenkovCounterComponent) -> None:
        assert comp.name == "cherenkov_counter"
        assert comp.label == "Cherenkov Counters"

    def test_tree_branches(self, comp: CherenkovCounterComponent) -> None:
        tb = comp.tree_branches()
        assert "CERNSPS2025" in tb
        assert "ADCs" in tb["CERNSPS2025"]
        assert "TriggerMask" in tb["CERNSPS2025"]

    def test_fill_and_finalize(
        self, comp: CherenkovCounterComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert isinstance(result, CherCounterResults)
        # Default settings have Cher1 (162), Cher2 (163), Cher3 (164)
        assert set(result.labels.values()) == {"Cher1", "Cher2", "Cher3"}
        for ch in result.all_events:
            assert result.all_events[ch].sum() == 100
            assert result.pedestal[ch].sum() <= 100

    def test_pedestal_filters_by_trigger_mask(
        self, comp: CherenkovCounterComponent, rng: np.random.Generator
    ) -> None:
        n = 200
        n_adc = 224
        masks = np.array([1] * 120 + [2] * 80)
        rng.shuffle(masks)
        batch = ak.Array(
            {
                "ADCs": rng.integers(0, 4096, size=(n, n_adc)).astype(np.float64),
                "TriggerMask": masks,
            }
        )

        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", batch)
        result = comp.finalize(state)

        for ch in result.all_events:
            assert result.all_events[ch].sum() == 200
            assert result.pedestal[ch].sum() == 80

    def test_empty_finalize(self, comp: CherenkovCounterComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        for ch in result.all_events:
            assert result.all_events[ch].sum() == 0
            assert result.pedestal[ch].sum() == 0


# ── Veto Component ──────────────────────────────────────────────────


class TestVetoComponent:
    """Tests for VetoComponent batch accumulation and finalize."""

    @pytest.fixture()
    def comp(self) -> VetoComponent:
        return VetoComponent()

    def test_name_and_label(self, comp: VetoComponent) -> None:
        assert comp.name == "veto"
        assert comp.label == "Veto"

    def test_tree_branches(self, comp: VetoComponent) -> None:
        tb = comp.tree_branches()
        assert "CERNSPS2025" in tb
        assert "ADCs" in tb["CERNSPS2025"]
        assert "TriggerMask" in tb["CERNSPS2025"]

    def test_fill_and_finalize(self, comp: VetoComponent, cernsps_batch: ak.Array) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)

        assert isinstance(result, VetoResults)
        assert result.all_events.sum() == 100
        assert result.pedestal.sum() <= result.all_events.sum()

    def test_fills_correct_channel(self, comp: VetoComponent, rng: np.random.Generator) -> None:
        """Verify the histogram is filled from the veto channel (63)."""
        n, n_adc = 50, 224
        adcs = np.zeros((n, n_adc), dtype=np.int64)
        adcs[:, 63] = 1000  # only veto channel has nonzero
        batch = ak.Array(
            {
                "ADCs": adcs,
                "TriggerMask": np.ones(n, dtype=np.int64),
            }
        )

        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", batch)
        result = comp.finalize(state)

        values, edges = result.all_events.to_numpy()
        assert result.all_events.sum() == 50
        # All entries should be in bin corresponding to ADC=1000
        idx = np.searchsorted(edges, 1000, side="right") - 1
        assert values[idx] == 50

    def test_multiple_batches_accumulate(
        self, comp: VetoComponent, cernsps_batch: ak.Array
    ) -> None:
        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        comp.fill_batch(state, "CERNSPS2025", cernsps_batch)
        result = comp.finalize(state)
        assert result.all_events.sum() == 200

    def test_empty_finalize(self, comp: VetoComponent) -> None:
        state = comp.create_state("")
        result = comp.finalize(state)
        assert result.all_events.sum() == 0
        assert result.pedestal.sum() == 0

    def test_pedestal_filters_by_trigger_mask(
        self, comp: VetoComponent, rng: np.random.Generator
    ) -> None:
        """Only events with TriggerMask==2 go into the pedestal histogram."""
        n = 200
        n_adc = 224
        masks = np.array([1] * 120 + [2] * 80)
        rng.shuffle(masks)
        batch = ak.Array(
            {
                "ADCs": rng.integers(0, 4096, size=(n, n_adc)).astype(np.float64),
                "TriggerMask": masks,
            }
        )

        state = comp.create_state("")
        comp.fill_batch(state, "CERNSPS2025", batch)
        result = comp.finalize(state)

        assert result.all_events.sum() == 200
        assert result.pedestal.sum() == 80
