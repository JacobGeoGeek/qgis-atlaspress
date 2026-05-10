from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgisInterface, QgsLayoutDesignerInterface
from typing_extensions import Final

from . import resources  # noqa: F401  Needed to register Qt resources
from .controllers import LayoutDesignerController
from .core.services import CoreServices, create_core_services


class AtlasPress:
    def __init__(self, iface: QgisInterface):
        self._iface: Final[QgisInterface] = iface
        self._services: Final[CoreServices] = create_core_services()

        self._layout_designer_controllers_by_designer: Final[
            dict[QgsLayoutDesignerInterface, LayoutDesignerController]
        ] = {}

    def initGui(self):
        QgsMessageLog.logMessage(
            "Initializing AtlasPress plugin.",
            "AtlasPress",
            level=Qgis.Info,
        )

        self._iface.layoutDesignerOpened.connect(self._on_layout_designer_opened)
        self._iface.layoutDesignerWillBeClosed.connect(self._on_layout_designer_closed)

    def unload(self):
        QgsMessageLog.logMessage(
            "Unloading AtlasPress plugin.",
            "AtlasPress",
            level=Qgis.Info,
        )

        self._iface.layoutDesignerOpened.disconnect(self._on_layout_designer_opened)
        self._iface.layoutDesignerWillBeClosed.disconnect(self._on_layout_designer_closed)

        for controller in self._layout_designer_controllers_by_designer.values():
            controller.remove_export_to_atlas_actions()

        self._layout_designer_controllers_by_designer.clear()

    def _on_layout_designer_opened(self, designer: QgsLayoutDesignerInterface):
        QgsMessageLog.logMessage(
            f"Layout designer opened, adding AtlasPress actions. {id(designer)}",
            "AtlasPress",
            level=Qgis.Info,
        )
        controller: Final[LayoutDesignerController] = LayoutDesignerController(
            designer,
            self._services,
        )

        controller.add_export_to_atlas_actions()
        self._layout_designer_controllers_by_designer[designer] = controller

    def _on_layout_designer_closed(self, designer: QgsLayoutDesignerInterface):
        controller: Final[LayoutDesignerController | None] = (
            self._layout_designer_controllers_by_designer.get(designer)
        )

        if controller is not None:
            controller.remove_export_to_atlas_actions()
            QgsMessageLog.logMessage(
                f"Layout designer closed, removing AtlasPress actions. {id(designer)}",
                "AtlasPress",
                level=Qgis.Info,
            )

            del self._layout_designer_controllers_by_designer[designer]
