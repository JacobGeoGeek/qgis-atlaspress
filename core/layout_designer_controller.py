from typing import Final

from qgis.core import Qgis, QgsMessageLog
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtGui import QAction, QIcon
from qgis.PyQt.QtWidgets import QMenu, QToolBar

from .upload import UploadService


class LayoutDesignerController:
    def __init__(self, designer: QgsLayoutDesignerInterface, upload_service: UploadService):
        self._designer: QgsLayoutDesignerInterface = designer
        self._upload_service: UploadService = upload_service
        self._designer_id: Final[int] = id(self._designer)

        self._pdf_export_action_name_toolbar: Final[str] = "mActionExportAsPDF"
        self._pdf_export_action_atlas_menu: Final[str] = "mActionExportAtlasAsPDF"

        self._atlas_press_action: Final[QAction] = QAction(
            icon=QIcon(":/plugins/atlas_press/resources/icons/atlas_press.svg"),
            text="Export to Atlas Press",
            parent=self._designer,
            objectName="actionExportToAtlasPress",
        )
        self._atlas_press_action.triggered.connect(self._upload_layout_file)

    def add_export_to_atlas_actions(self):
        QgsMessageLog.logMessage(
            "Adding AtlasPress actions.",
            "AtlasPress",
            level=Qgis.Info,
        )

        self._add_export_to_atlas_action_to_layout_toolbar()
        self._add_export_to_atlas_action_to_atlas_menu()

    def remove_export_to_atlas_actions(self):
        layout_toolbar: Final[QToolBar] = self._designer.layoutToolbar()

        if layout_toolbar is not None:
            layout_toolbar.removeAction(self._atlas_press_action)
            QgsMessageLog.logMessage(
                f"Removed AtlasPress action from toolbar from {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Info,
            )

        atlas_menu: Final[QMenu] = self._designer.atlasMenu()

        if atlas_menu is not None:
            atlas_menu.removeAction(self._atlas_press_action)
            QgsMessageLog.logMessage(
                f"Removed AtlasPress action from atlas menu from {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Info,
            )

    def _add_export_to_atlas_action_to_layout_toolbar(self):
        layout_toolbar: Final[QToolBar] = self._designer.layoutToolbar()
        actions_toolbar: Final[list[QAction]] = layout_toolbar.actions()

        if self._pdf_export_action_name_toolbar not in [
            action.objectName() for action in actions_toolbar
        ]:
            QgsMessageLog.logMessage(
                f"Toolbar anchor '{self._pdf_export_action_name_toolbar}' not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        target_index: int = -1

        for index, action in enumerate(actions_toolbar):
            if action.objectName() == self._pdf_export_action_name_toolbar:
                target_index = index + 1
                break

        if target_index == -1:
            QgsMessageLog.logMessage(
                f"Toolbar insertion point not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        layout_toolbar.insertAction(actions_toolbar[target_index], self._atlas_press_action)

        QgsMessageLog.logMessage(
            f"Inserted AtlasPress action into layout toolbar in {self._designer_id}.",
            "AtlasPress",
            level=Qgis.Info,
        )

    def _add_export_to_atlas_action_to_atlas_menu(self):
        atlas_menu: Final[QMenu] = self._designer.atlasMenu()

        if atlas_menu is None:
            QgsMessageLog.logMessage(
                f"No atlas menu found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        actions_atlas_menu: Final[list[QAction]] = atlas_menu.actions()

        if self._pdf_export_action_atlas_menu not in [
            action.objectName() for action in actions_atlas_menu
        ]:
            QgsMessageLog.logMessage(
                f"Atlas menu anchor '{self._pdf_export_action_atlas_menu}' not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        target_index: int = -1

        for index, action in enumerate(actions_atlas_menu):
            if action.objectName() == self._pdf_export_action_atlas_menu:
                target_index = index + 1
                break

        if target_index == -1:
            QgsMessageLog.logMessage(
                f"Atlas menu insertion point not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        atlas_menu.insertAction(actions_atlas_menu[target_index], self._atlas_press_action)

        QgsMessageLog.logMessage(
            f"Inserted AtlasPress action into atlas menu in {self._designer_id}.",
            "AtlasPress",
            level=Qgis.Info,
        )

    def _upload_layout_file(self, checked: bool = False):
        self._upload_service.upload_layout_file(self._designer)
