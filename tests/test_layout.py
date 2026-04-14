"""Tests for tb_monitor.frontend.layout."""

from __future__ import annotations

from tb_monitor.frontend.layout import make_layout


class TestMakeLayout:
    """Tests for make_layout()."""

    def test_empty_run_options(self) -> None:
        layout = make_layout([])
        # Should not raise; dropdown value is None.
        dropdown = _find_component(layout, "run-selector")
        assert dropdown is not None
        assert dropdown.value is None
        assert dropdown.placeholder == "No run files found"

    def test_with_run_options(self) -> None:
        opts = [
            {"label": "Run 1 (run1.root)", "value": "/data/run1.root"},
            {"label": "Run 2 (run2.root)", "value": "/data/run2.root"},
        ]
        layout = make_layout(opts)
        dropdown = _find_component(layout, "run-selector")
        assert dropdown is not None
        assert dropdown.value == "/data/run2.root"  # last option
        assert dropdown.placeholder == "Select a run…"

    def test_error_banner_hidden_by_default(self) -> None:
        layout = make_layout([])
        error_div = _find_component(layout, "run-error")
        assert error_div is not None
        assert error_div.style["display"] == "none"


def _find_component(component, target_id: str):
    """Recursively search a Dash component tree for a component by id."""
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, list):
        children = [children]
    for child in children:
        result = _find_component(child, target_id)
        if result is not None:
            return result
    return None
