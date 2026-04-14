"""ADC channel mapping for the CERN SPS 2025 test beam.

All values are derived from :func:`tb_monitor.settings.get_settings` so
they update automatically when a config file is loaded.
"""

from __future__ import annotations

from tb_monitor.settings import get_settings


def special_channels() -> dict[int, str]:
    return get_settings().special_channels


def leakage_channels() -> list[int]:
    return get_settings().leakage_channels


def beam_channels() -> dict[int, str]:
    return get_settings().beam_channels


def scintillation_channels() -> list[int]:
    return get_settings().scintillation_channels


def cherenkov_channels() -> list[int]:
    return get_settings().cherenkov_channels


def aux_channel_set() -> frozenset[int]:
    return frozenset(get_settings().special_channels.keys())
