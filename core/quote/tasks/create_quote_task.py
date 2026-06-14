from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..models import QuoteResponse
from ..quote_service import QuoteService

MESSAGE_CATEGORY = "CreateQuoteTask"


class CreateQuoteTask(QgsTask):
    def __init__(
        self,
        quote_service: QuoteService,
        payload: dict,
        on_finished_callback: callable,
    ):
        super().__init__(
            "Create Atlas Press quote",
            QgsTask.CanCancel,
        )
        self._quote_service = quote_service
        self._payload = payload
        self._on_finished_callback = on_finished_callback
        self._quote: QuoteResponse | None = None
        self._error_message = ""

    def run(self):
        try:
            self._quote = self._quote_service.create_quote(self._payload)
            return True
        except Exception as e:
            import traceback

            self._error_message = str(e)
            QgsMessageLog.logMessage(
                f"Error creating quote: {e}\n{traceback.format_exc()}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        self._on_finished_callback(result, self._quote, self._error_message)
