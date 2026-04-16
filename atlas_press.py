from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgisInterface, QgsLayoutDesignerInterface
from typing_extensions import Final

from . import resources  # noqa: F401  Needed to register Qt resources
from .core.config.config import load_config_file
from .core.config.http_client import HttpClient
from .core.layout_designer_controller import LayoutDesignerController
from .core.upload.upload_repository import UploadRepository
from .core.upload.upload_service import UploadService


class AtlasPress:
    def __init__(self, iface: QgisInterface):
        self._config = load_config_file()
        self._iface: Final[QgisInterface] = iface
        self._upload_service: Final[UploadService] = UploadService(
            UploadRepository(
                HttpClient(self._config["supabase"]["baseUrl"], self._config["supabase"]["anonKey"])
            )
        )
        self._layer_desiner_controllers_by_desiner: Final[
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

        for controller in self._layer_desiner_controllers_by_desiner.values():
            controller.remove_export_to_atlas_actions()

        self._layer_desiner_controllers_by_desiner.clear()

    def _on_layout_designer_opened(self, designer: QgsLayoutDesignerInterface):
        QgsMessageLog.logMessage(
            f"Layout designer opened, adding AtlasPress actions. {id(designer)}",
            "AtlasPress",
            level=Qgis.Info,
        )
        controller: Final[LayoutDesignerController] = LayoutDesignerController(
            designer, self._upload_service
        )

        controller.add_export_to_atlas_actions()
        self._layer_desiner_controllers_by_desiner[designer] = controller

    def _on_layout_designer_closed(self, designer: QgsLayoutDesignerInterface):
        controller: Final[LayoutDesignerController | None] = (
            self._layer_desiner_controllers_by_desiner.get(designer)
        )

        if controller is not None:
            controller.remove_export_to_atlas_actions()
            QgsMessageLog.logMessage(
                f"Layout designer closed, removing AtlasPress actions. {id(designer)}",
                "AtlasPress",
                level=Qgis.Info,
            )

            del self._layer_desiner_controllers_by_desiner[designer]
