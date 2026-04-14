"""Tests for tb_monitor.settings — config loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from tb_monitor.settings import Settings, load_settings, set_settings


class TestLoadSettings:
    """Tests for load_settings()."""

    def test_none_returns_defaults(self) -> None:
        s = load_settings(None)
        assert isinstance(s, Settings)
        assert s.port == 8050

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_settings(tmp_path / "nonexistent.toml")

    def test_malformed_toml_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.toml"
        bad.write_text("this is not [valid toml =")
        with pytest.raises(ValueError, match="Malformed TOML"):
            load_settings(bad)

    def test_invalid_regex_raises(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.toml"
        # Use TOML literal string to avoid TOML escape issues.
        # The pattern has an unclosed parenthesis → invalid regex.
        cfg.write_text("[processing]\nrun_file_pattern = 'run(\\d+\\.root$'\n")
        with pytest.raises(ValueError, match="Invalid run_file_pattern"):
            load_settings(cfg)

    def test_valid_config_loads(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text("[server]\nport = 9999\n\n[processing]\nstep_size = 10000\n")
        s = load_settings(cfg)
        assert s.port == 9999
        assert s.step_size == 10000

    def test_partial_config_keeps_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text('[server]\nhost = "127.0.0.1"\n')
        s = load_settings(cfg)
        assert s.host == "127.0.0.1"
        assert s.port == 8050  # default preserved

    def test_enabled_components_loaded(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text('[components]\nenabled = ["overview", "sipm"]\n')
        s = load_settings(cfg)
        assert s.enabled_components == ("overview", "sipm")

    def test_enabled_components_default_empty(self) -> None:
        s = load_settings(None)
        assert s.enabled_components == ()

    def test_unknown_component_raises(self, tmp_path: Path) -> None:
        cfg = tmp_path / "config.toml"
        cfg.write_text('[components]\nenabled = ["overview", "bogus"]\n')
        with pytest.raises(ValueError, match="Unknown component"):
            load_settings(cfg)


class TestSettingsReplace:
    """Tests for Settings.replace()."""

    def test_replace_creates_new_instance(self) -> None:
        s = Settings()
        s2 = s.replace(port=1234)
        assert s2.port == 1234
        assert s.port == 8050  # original unchanged

    def test_replace_preserves_other_fields(self) -> None:
        s = Settings(host="myhost", port=5000)
        s2 = s.replace(port=6000)
        assert s2.host == "myhost"
        assert s2.port == 6000


class TestGetComponents:
    """Tests for get_components() filtering."""

    def test_default_returns_all(self) -> None:
        from tb_monitor.components import _ALL_COMPONENTS, get_components

        set_settings(Settings())
        result = get_components()
        assert len(result) == len(_ALL_COMPONENTS)

    def test_filter_by_name(self) -> None:
        from tb_monitor.components import get_components

        set_settings(Settings(enabled_components=("overview", "sipm")))
        result = get_components()
        assert [c.name for c in result] == ["overview", "sipm"]

    def test_preserves_configured_order(self) -> None:
        from tb_monitor.components import get_components

        set_settings(Settings(enabled_components=("sipm", "overview")))
        result = get_components()
        assert [c.name for c in result] == ["sipm", "overview"]

    def test_empty_tuple_returns_all(self) -> None:
        from tb_monitor.components import _ALL_COMPONENTS, get_components

        set_settings(Settings(enabled_components=()))
        result = get_components()
        assert len(result) == len(_ALL_COMPONENTS)
