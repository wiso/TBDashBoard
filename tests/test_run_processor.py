"""Tests for tb_monitor.backend.run_processor.RunProcessor."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from tb_monitor.backend.run_processor import RunProcessor, RunStatus


def _fake_iter(path: str, step_size: int = 50_000, components=None):
    """Fake iter_process_run that yields 3 batches."""
    for i in range(1, 4):
        yield i / 3, i * 100, {"comp": f"batch-{i}", "_metadata": {}}


def _slow_iter(path: str, step_size: int = 50_000, components=None):
    """Fake iter_process_run that sleeps between yields."""
    for i in range(1, 3):
        time.sleep(0.05)
        yield i / 2, i * 10, {"comp": f"batch-{i}", "_metadata": {}}


def _error_iter(path: str, step_size: int = 50_000, components=None):
    """Fake iter_process_run that raises."""
    yield 0.5, 50, {"comp": "partial", "_metadata": {}}
    raise RuntimeError("simulated error")


class TestRunProcessor:
    """Tests for the RunProcessor singleton."""

    def test_processes_run_to_completion(self) -> None:
        proc = RunProcessor(max_cached=4)

        with patch(
            "tb_monitor.backend.run_processor.iter_process_run",
            side_effect=_fake_iter,
        ):
            proc.start("/fake.root")
            # Wait for completion
            for _ in range(100):
                status, *_ = proc.get_state("/fake.root")
                if status == RunStatus.DONE:
                    break
                time.sleep(0.01)

        status, progress, entries, results, error = proc.get_state("/fake.root")
        assert status == RunStatus.DONE
        assert progress == pytest.approx(1.0)
        assert entries == 300
        assert results is not None
        assert error is None

    def test_get_results_returns_latest(self) -> None:
        proc = RunProcessor(max_cached=4)

        with patch(
            "tb_monitor.backend.run_processor.iter_process_run",
            side_effect=_fake_iter,
        ):
            proc.start("/fake.root")
            for _ in range(100):
                status, *_ = proc.get_state("/fake.root")
                if status == RunStatus.DONE:
                    break
                time.sleep(0.01)

        results = proc.get_results("/fake.root")
        assert results is not None
        assert results["comp"] == "batch-3"

    def test_duplicate_start_is_noop(self) -> None:
        proc = RunProcessor(max_cached=4)
        call_count = 0

        def counting_iter(path, step_size=50_000, components=None):
            nonlocal call_count
            call_count += 1
            yield from _fake_iter(path, step_size, components)

        with patch(
            "tb_monitor.backend.run_processor.iter_process_run",
            side_effect=counting_iter,
        ):
            proc.start("/fake.root")
            proc.start("/fake.root")  # should be no-op
            for _ in range(100):
                status, *_ = proc.get_state("/fake.root")
                if status == RunStatus.DONE:
                    break
                time.sleep(0.01)

        assert call_count == 1

    def test_done_run_start_is_noop(self) -> None:
        proc = RunProcessor(max_cached=4)
        call_count = 0

        def counting_iter(path, step_size=50_000, components=None):
            nonlocal call_count
            call_count += 1
            yield from _fake_iter(path, step_size, components)

        with patch(
            "tb_monitor.backend.run_processor.iter_process_run",
            side_effect=counting_iter,
        ):
            proc.start("/fake.root")
            for _ in range(100):
                status, *_ = proc.get_state("/fake.root")
                if status == RunStatus.DONE:
                    break
                time.sleep(0.01)
            # Starting again after done should be no-op
            proc.start("/fake.root")

        assert call_count == 1

    def test_error_captured(self) -> None:
        proc = RunProcessor(max_cached=4)

        with patch(
            "tb_monitor.backend.run_processor.iter_process_run",
            side_effect=_error_iter,
        ):
            proc.start("/bad.root")
            for _ in range(100):
                status, *_ = proc.get_state("/bad.root")
                if status in (RunStatus.DONE, RunStatus.ERROR):
                    break
                time.sleep(0.01)

        status, progress, entries, results, error = proc.get_state("/bad.root")
        assert status == RunStatus.ERROR
        assert error is not None
        assert "simulated error" in error

    def test_unknown_path_returns_idle(self) -> None:
        proc = RunProcessor(max_cached=4)
        status, progress, entries, results, error = proc.get_state("/unknown.root")
        assert status == RunStatus.IDLE
        assert results is None

    def test_get_results_unknown_path_returns_none(self) -> None:
        proc = RunProcessor(max_cached=4)
        assert proc.get_results("/unknown.root") is None

    def test_evicts_oldest_when_full(self) -> None:
        proc = RunProcessor(max_cached=2)

        with patch(
            "tb_monitor.backend.run_processor.iter_process_run",
            side_effect=_fake_iter,
        ):
            # Fill cache with 2 runs
            proc.start("/run1.root")
            proc.start("/run2.root")
            for _ in range(200):
                s1, *_ = proc.get_state("/run1.root")
                s2, *_ = proc.get_state("/run2.root")
                if s1 == RunStatus.DONE and s2 == RunStatus.DONE:
                    break
                time.sleep(0.01)

            # Adding a third should evict one
            proc.start("/run3.root")
            for _ in range(100):
                s3, *_ = proc.get_state("/run3.root")
                if s3 == RunStatus.DONE:
                    break
                time.sleep(0.01)

        # run3 should be cached
        assert proc.get_results("/run3.root") is not None
