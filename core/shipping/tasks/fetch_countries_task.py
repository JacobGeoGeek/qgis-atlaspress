from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..shipping_service import ShippingService

MESSAGE_CATEGORY = "FetchCountriesTask"


class FetchCountriesTask(QgsTask):
    def __init__(
        self,
        shipping_service: ShippingService,
        on_finished_callback: callable,
    ):
        super().__init__(
            "Fetch supported shipping countries",
            QgsTask.CanCancel,
        )
        self._shipping_service = shipping_service
        self._on_finished_callback = on_finished_callback
        self._countries = []

    def run(self):
        try:
            self._countries = self._shipping_service.get_countries()
            return True
        except Exception as e:
            import traceback

            QgsMessageLog.logMessage(
                f"Error fetching supported countries: {e}\n{traceback.format_exc()}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        self._on_finished_callback(result, self._countries)
