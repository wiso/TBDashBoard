"""Application settings with TOML file loading and CLI overrides."""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """All tuneable application parameters.

    Load from a TOML file with :func:`load_settings`, then override
    individual values with CLI flags via :meth:`replace`.
    """

    # ── paths / server ──────────────────────────────────────────────
    data_dir: str = ""
    host: str = "0.0.0.0"
    port: int = 8050

    # ── processing ──────────────────────────────────────────────────
    step_size: int = 50_000
    run_file_pattern: str = r"run(\d+)\.root$"

    # ── detector geometry ───────────────────────────────────────────
    n_adc_channels: int = 224
    n_sipm_channels: int = 1024
    adc_lo: int = 0
    adc_hi: int = 4096

    scintillation_range: tuple[int, int] = (0, 64)
    cherenkov_range: tuple[int, int] = (64, 128)

    # channel_number → label
    special_channels: dict[int, str] = field(
        default_factory=lambda: {
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
    )

    leakage_range: tuple[int, int] = (128, 144)
    muon_channel: int = 161
    veto_channel: int = 63
    pedestal_trigger_mask: int = 2

    # ── overview histogram ──────────────────────────────────────────
    event_rate_bins: int = 200

    # ── SiPM saturation ────────────────────────────────────────────
    sipm_saturation_thresholds: tuple[int, ...] = (3000, 3200, 3400, 3600, 3800, 4000, 4096)

    # ── component selection (empty = all) ───────────────────────────
    enabled_components: tuple[str, ...] = ()

    # ── derived helpers ─────────────────────────────────────────────

    @property
    def leakage_channels(self) -> list[int]:
        return list(range(*self.leakage_range))

    @property
    def beam_channels(self) -> dict[int, str]:
        """Special channels excluding leakage (i.e. beam line detectors)."""
        lo, hi = self.leakage_range
        return {ch: label for ch, label in self.special_channels.items() if not (lo <= ch < hi)}

    @property
    def scintillation_channels(self) -> list[int]:
        r = range(*self.scintillation_range)
        return [ch for ch in r if ch not in self.special_channels]

    @property
    def cherenkov_channels(self) -> list[int]:
        return list(range(*self.cherenkov_range))

    def replace(self, **kwargs: Any) -> Settings:
        """Return a new Settings with selected fields overridden."""
        from dataclasses import asdict

        d = asdict(self)
        d.update(kwargs)
        return Settings(**d)


def load_settings(path: str | Path | None = None) -> Settings:
    """Load settings from a TOML file.

    Parameters
    ----------
    path : str | Path | None
        Path to a TOML config file.  ``None`` returns defaults.

    Returns
    -------
    Settings
    """
    if path is None:
        return Settings()

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        with path.open("rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Malformed TOML in {path}: {exc}") from exc

    kwargs: dict[str, Any] = {}

    # Flat mappings from TOML sections to dataclass fields.
    _simple = {
        ("server", "host"): "host",
        ("server", "port"): "port",
        ("server", "data_dir"): "data_dir",
        ("processing", "step_size"): "step_size",
        ("processing", "run_file_pattern"): "run_file_pattern",
        ("detector", "n_adc_channels"): "n_adc_channels",
        ("detector", "n_sipm_channels"): "n_sipm_channels",
        ("detector", "adc_lo"): "adc_lo",
        ("detector", "adc_hi"): "adc_hi",
        ("detector", "muon_channel"): "muon_channel",
        ("detector", "pedestal_trigger_mask"): "pedestal_trigger_mask",
        ("detector", "event_rate_bins"): "event_rate_bins",
    }

    # SiPM saturation thresholds — stored as array in TOML.
    if "detector" in raw and "sipm_saturation_thresholds" in raw["detector"]:
        kwargs["sipm_saturation_thresholds"] = tuple(raw["detector"]["sipm_saturation_thresholds"])

    # Components list — lives under [components] section.
    if "components" in raw and "enabled" in raw["components"]:
        kwargs["enabled_components"] = tuple(raw["components"]["enabled"])

    for (section, key), field_name in _simple.items():
        if section in raw and key in raw[section]:
            kwargs[field_name] = raw[section][key]

    # Ranges stored as [lo, hi] arrays in TOML.
    _ranges = {
        ("detector", "scintillation_range"): "scintillation_range",
        ("detector", "cherenkov_range"): "cherenkov_range",
        ("detector", "leakage_range"): "leakage_range",
    }
    for (section, key), field_name in _ranges.items():
        if section in raw and key in raw[section]:
            v = raw[section][key]
            kwargs[field_name] = (v[0], v[1])

    # Special channels: TOML table { "31" = "PS", ... }.
    if "detector" in raw and "special_channels" in raw["detector"]:
        kwargs["special_channels"] = {
            int(k): v for k, v in raw["detector"]["special_channels"].items()
        }

    settings = Settings(**kwargs)

    # Validate enabled_components against known names.
    _known = {"overview", "adc", "aux", "muon", "veto", "cherenkov", "sipm"}
    for name in settings.enabled_components:
        if name not in _known:
            raise ValueError(
                f"Unknown component {name!r} in enabled_components. Known: {sorted(_known)}"
            )

    # Validate regex pattern eagerly so errors surface at startup.
    try:
        re.compile(settings.run_file_pattern)
    except re.error as exc:
        raise ValueError(f"Invalid run_file_pattern {settings.run_file_pattern!r}: {exc}") from exc

    return settings


# ── Module-level singleton ──────────────────────────────────────────
_settings: Settings = Settings()


def get_settings() -> Settings:
    """Return the current application settings."""
    return _settings


def set_settings(s: Settings) -> None:
    """Set the application-wide settings (call once at startup)."""
    global _settings
    _settings = s
