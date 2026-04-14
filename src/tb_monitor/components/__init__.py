"""Component registry.

All available components are listed in ``_ALL_COMPONENTS``.
Use :func:`get_components` to get the active subset based on
:pydata:`~tb_monitor.settings.Settings.enabled_components`.
"""

from __future__ import annotations

from tb_monitor.components.adc import ADCComponent
from tb_monitor.components.aux import AuxComponent
from tb_monitor.components.base import Component
from tb_monitor.components.cherenkov_counter import CherenkovCounterComponent
from tb_monitor.components.muon import MuonComponent
from tb_monitor.components.overview import OverviewComponent
from tb_monitor.components.sipm import SiPMComponent
from tb_monitor.components.veto import VetoComponent

_ALL_COMPONENTS: list[Component] = [
    OverviewComponent(),
    ADCComponent(),
    AuxComponent(),
    MuonComponent(),
    VetoComponent(),
    CherenkovCounterComponent(),
    SiPMComponent(),
]
"""All available monitoring components, in default tab order."""


def get_components() -> list[Component]:
    """Return active components filtered by settings.

    If ``enabled_components`` is empty, all components are returned.
    Otherwise only those whose :attr:`Component.name` appears in
    the list are returned, preserving the configured order.
    """
    from tb_monitor.settings import get_settings

    enabled = get_settings().enabled_components
    if not enabled:
        return list(_ALL_COMPONENTS)
    by_name = {c.name: c for c in _ALL_COMPONENTS}
    return [by_name[n] for n in enabled if n in by_name]


# Backwards-compatible alias used by existing imports.
COMPONENTS = _ALL_COMPONENTS

__all__ = ["Component", "COMPONENTS", "get_components"]
