from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..models import QuoteResponse
from ..quote_service import QuoteService

MESSAGE_CATEGORY = "UpdateShippingOptionTask"


class UpdateShippingOptionTask(QgsTask):
    def __init__(
        self,
        quote_service: QuoteService,
        quote_id: str,
        selected_shipping_option_id: str,
        on_finished_callback: callable,
    ):
        super().__init__(
            "Update quote shipping option",
            QgsTask.CanCancel,
        )
        self._quote_service = quote_service
        self._quote_id = quote_id
        self._selected_shipping_option_id = selected_shipping_option_id
        self._on_finished_callback = on_finished_callback
        self._quote: QuoteResponse | None = None
        self._error_message = ""

    def run(self):
        try:
            self._quote = self._quote_service.update_shipping_option(
                self._quote_id,
                self._selected_shipping_option_id,
            )
            return True
        except Exception as e:
            import traceback

            self._error_message = str(e)
            QgsMessageLog.logMessage(
                f"Error updating quote shipping option: {e}\n{traceback.format_exc()}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        self._on_finished_callback(result, self._quote, self._error_message)
