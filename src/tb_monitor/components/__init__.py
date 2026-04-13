"""Component registry.

To add or remove a component, edit the ``COMPONENTS`` list below.
"""

from tb_monitor.components.adc import ADCComponent
from tb_monitor.components.base import Component
from tb_monitor.components.overview import OverviewComponent
from tb_monitor.components.sipm import SiPMComponent

COMPONENTS: list[Component] = [
    OverviewComponent(),
    ADCComponent(),
    SiPMComponent(),
]
"""Active monitoring components, in tab order."""

__all__ = ["Component", "COMPONENTS"]
