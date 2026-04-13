"""Shared fixtures for TB2026 monitoring tests.

All test data is synthetic — no real ROOT files required.
"""

from __future__ import annotations

import awkward as ak
import numpy as np
import pytest


@pytest.fixture()
def rng() -> np.random.Generator:
    """Seeded random generator for reproducible tests."""
    return np.random.default_rng(42)


@pytest.fixture()
def cernsps_batch(rng: np.random.Generator) -> ak.Array:
    """One synthetic batch resembling CERNSPS2025 data.

    100 events, 224-channel ADCs, TDCs, TriggerMask, EventTime, etc.
    """
    n_events = 100
    n_adc = 224
    return ak.Array({
        "ADCs": rng.integers(0, 4096, size=(n_events, n_adc)).astype(np.float64),
        "TriggerMask": rng.choice([1, 2], size=n_events),
        "EventTime": np.sort(rng.uniform(1000.0, 2000.0, size=n_events)),
        "EventSpill": rng.choice([0, 1, 2, 3], size=n_events),
        "EventNumber": np.arange(n_events),
    })


@pytest.fixture()
def sipm_batch(rng: np.random.Generator) -> ak.Array:
    """One synthetic batch resembling SiPM_rawTree_aligned data.

    80 events, 1024-channel SiPM_HG.
    """
    n_events = 80
    n_ch = 1024
    return ak.Array({
        "SiPM_HG": rng.uniform(0.0, 500.0, size=(n_events, n_ch)),
    })
