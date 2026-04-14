"""Tests for tb_monitor.backend.file_scanner."""

from __future__ import annotations

from pathlib import Path

from tb_monitor.backend.file_scanner import RunFile, run_options, scan_directory


class TestScanDirectory:
    """Tests for scan_directory()."""

    def test_finds_run_files(self, tmp_path: Path) -> None:
        (tmp_path / "merged_sps2025_run990.root").touch()
        (tmp_path / "merged_sps2025_run1001.root").touch()

        result = scan_directory(tmp_path)

        assert len(result) == 2
        assert result[0].run_number == 990
        assert result[1].run_number == 1001

    def test_sorted_by_run_number(self, tmp_path: Path) -> None:
        for n in [300, 100, 200]:
            (tmp_path / f"run{n}.root").touch()

        result = scan_directory(tmp_path)

        assert [r.run_number for r in result] == [100, 200, 300]

    def test_ignores_non_root_files(self, tmp_path: Path) -> None:
        (tmp_path / "run42.root").touch()
        (tmp_path / "run99.txt").touch()
        (tmp_path / "notes.root").touch()  # no run number

        result = scan_directory(tmp_path)

        assert len(result) == 1
        assert result[0].run_number == 42

    def test_empty_directory(self, tmp_path: Path) -> None:
        assert scan_directory(tmp_path) == []

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        result = scan_directory(tmp_path / "no_such_dir")
        assert result == []

    def test_runfile_fields(self, tmp_path: Path) -> None:
        fname = "merged_sps2025_run7.root"
        (tmp_path / fname).touch()

        r = scan_directory(tmp_path)[0]

        assert isinstance(r, RunFile)
        assert r.run_number == 7
        assert r.filename == fname
        assert r.path == tmp_path / fname

    def test_glob_is_case_sensitive_on_linux(self, tmp_path: Path) -> None:
        # glob("*.root") is case-sensitive; uppercase extension is missed.
        (tmp_path / "Run123.ROOT").touch()
        (tmp_path / "run456.root").touch()

        result = scan_directory(tmp_path)

        assert len(result) == 1
        assert result[0].run_number == 456


class TestRunOptions:
    """Tests for run_options()."""

    def test_returns_dash_options(self, tmp_path: Path) -> None:
        (tmp_path / "merged_sps2025_run5.root").touch()

        opts = run_options(tmp_path)

        assert len(opts) == 1
        assert "label" in opts[0]
        assert "value" in opts[0]
        assert "Run 5" in opts[0]["label"]
        assert str(tmp_path) in opts[0]["value"]

    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        assert run_options(tmp_path) == []
