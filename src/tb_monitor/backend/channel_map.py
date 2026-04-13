"""ADC channel mapping for the CERN SPS 2025 test beam.

Based on hidraTBAnalysis/hidraTBAnalysis/format_data.py.
"""

from __future__ import annotations

# ── Special / auxiliary channels ────────────────────────────────────
SPECIAL_CHANNELS: dict[int, str] = {
    31: "PS",
    63: "Veto",
    128: "L1",
    129: "L2",
    130: "L3",
    131: "L4",
    132: "L5",
    133: "L6",
    134: "L7",
    135: "L8",
    136: "L9",
    137: "L10",
    138: "L11",
    139: "L12",
    140: "L13",
    141: "L14",
    142: "L15",
    143: "L16",
    160: "Tail Catcher",
    161: "Muon",
    162: "Cher1",
    163: "Cher2",
    164: "Cher3",
}

# Convenience subsets
LEAKAGE_CHANNELS: list[int] = list(range(128, 144))
BEAM_CHANNELS: dict[int, str] = {
    31: "PS",
    63: "Veto",
    160: "Tail Catcher",
    161: "Muon",
    162: "Cher1",
    163: "Cher2",
    164: "Cher3",
}

# ── Calorimeter channels (S + C fibres) ────────────────────────────
N_ADC_TOTAL = 224
SCINTILLATION_RANGE = range(0, 64)   # channels 0-63 (includes PS=31, Veto=63)
CHERENKOV_RANGE = range(64, 128)     # channels 64-127

# Indices of pure calorimeter channels (exclude embedded specials 31, 63)
SCINTILLATION_CHANNELS: list[int] = [
    ch for ch in SCINTILLATION_RANGE if ch not in SPECIAL_CHANNELS
]
CHERENKOV_CHANNELS: list[int] = list(CHERENKOV_RANGE)

AUX_CHANNEL_SET: frozenset[int] = frozenset(SPECIAL_CHANNELS.keys())
