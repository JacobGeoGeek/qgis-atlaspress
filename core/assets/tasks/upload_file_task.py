from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..asset_service import AssetService
from ..models.exported_layout import ExportedLayout

MESSAGE_CATEGORY = "UploadFileTask"


class UploadFileTask(QgsTask):
    def __init__(
        self,
        asset_service: AssetService,
        exported: ExportedLayout,
        on_finished_callback: callable,
    ):
        super().__init__(
            "Upload layout file to Atlas Press",
            QgsTask.CanCancel,
        )
        self._asset_service = asset_service
        self._exported = exported
        self._on_finished_callback = on_finished_callback
        self._asset_id = None
        self._error_message = ""

    def run(self):
        if self.isCanceled():
            return False

        try:
            self._asset_id = self._asset_service.upload_export(self._exported)
            return True
        except Exception as e:
            self._error_message = "Could not upload the map. Please try again."
            # print stack trace for debugging purposes
            import traceback

            QgsMessageLog.logMessage(
                f"Error uploading layout file: {e}\n{traceback.format_exc()}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        if not self.isCanceled():
            self._on_finished_callback(result, self._asset_id, self._error_message)
