"""Component registry.

To add or remove a component, edit the ``COMPONENTS`` list below.
"""

from tb_monitor.components.adc import ADCComponent
from tb_monitor.components.aux import AuxComponent
from tb_monitor.components.base import Component
from tb_monitor.components.overview import OverviewComponent
from tb_monitor.components.sipm import SiPMComponent

COMPONENTS: list[Component] = [
    OverviewComponent(),
    ADCComponent(),
    AuxComponent(),
    SiPMComponent(),
]
"""Active monitoring components, in tab order."""

__all__ = ["Component", "COMPONENTS"]
