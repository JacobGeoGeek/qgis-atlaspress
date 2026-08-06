from qgis.core import Qgis, QgsMessageLog, QgsTask

from ...config.model.http_response import HttpResponseError
from ..checkout_service import CheckoutRequestError, CheckoutService
from ..models import CheckoutStatusResponse

MESSAGE_CATEGORY = "GetCheckoutStatusTask"


class GetCheckoutStatusTask(QgsTask):
    def __init__(
        self,
        checkout_service: CheckoutService,
        quote_id: str,
        on_finished_callback: callable,
    ):
        super().__init__("Refresh Atlas Press checkout status", QgsTask.CanCancel)
        self._checkout_service = checkout_service
        self._quote_id = quote_id
        self._on_finished_callback = on_finished_callback
        self._checkout_status: CheckoutStatusResponse | None = None
        self._error: HttpResponseError | None = None

    def run(self):
        try:
            self._checkout_status = self._checkout_service.get_checkout_status(self._quote_id)
            return True
        except CheckoutRequestError as error:
            self._error = error.error
            level = Qgis.Warning if error.error.status_code < 500 else Qgis.Critical
            QgsMessageLog.logMessage(
                f"Error refreshing checkout status: {error}",
                MESSAGE_CATEGORY,
                level=level,
            )
            return False
        except Exception as error:
            import traceback

            self._error = HttpResponseError(
                status_code=0,
                message=str(error) or "Could not refresh checkout status.",
                details=[],
            )
            QgsMessageLog.logMessage(
                f"Error refreshing checkout status: {error}\n{traceback.format_exc()}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        self._on_finished_callback(result, self._checkout_status, self._error)
