from qgis.core import Qgis, QgsMessageLog, QgsTask
from qgis.gui import QgsLayoutDesignerInterface

from ..upload_service import UploadService

MESSAGE_CATEGORY = "UploadFileTask"


class UploadFileTask(QgsTask):
    def __init__(
        self,
        upload_service: UploadService,
        designer: QgsLayoutDesignerInterface,
        on_finished_callback: callable,
    ):
        super().__init__(
            "Upload layout file to Atlas Press",
            QgsTask.CanCancel,
        )
        self._upload_service = upload_service
        self._designer = designer
        self._on_finished_callback = on_finished_callback
        self._asset_id = None

    def run(self):
        try:
            self._asset_id = self._upload_service.upload_layout_file(self._designer)
            return True
        except Exception as e:
            # print stack trace for debugging purposes
            import traceback

            QgsMessageLog.logMessage(
                f"Error uploading layout file: {e}\n{traceback.format_exc()}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        self._on_finished_callback(result, self._asset_id)
