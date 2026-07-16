from qgis.core import Qgis, QgsMessageLog, QgsTask

from ...config.model.http_response import HttpResponseError
from ..checkout_service import CheckoutRequestError, CheckoutService
from ..models import CheckoutResponse

MESSAGE_CATEGORY = "CreateCheckoutTask"


class CreateCheckoutTask(QgsTask):
    def __init__(
        self,
        checkout_service: CheckoutService,
        quote_id: str,
        on_finished_callback: callable,
    ):
        super().__init__("Create Atlas Press checkout", QgsTask.CanCancel)
        self._checkout_service = checkout_service
        self._quote_id = quote_id
        self._on_finished_callback = on_finished_callback
        self._checkout: CheckoutResponse | None = None
        self._error: HttpResponseError | None = None

    def run(self):
        try:
            self._checkout = self._checkout_service.create_checkout(self._quote_id)
            return True
        except CheckoutRequestError as error:
            self._error = error.error
            QgsMessageLog.logMessage(
                f"Error creating checkout: {error}",
                MESSAGE_CATEGORY,
                level=Qgis.Warning,
            )
            return False
        except Exception as error:
            import traceback

            self._error = HttpResponseError(
                status_code=0,
                message=str(error) or "Could not prepare checkout.",
                details=[],
            )
            QgsMessageLog.logMessage(
                f"Error creating checkout: {error}\n{traceback.format_exc()}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        self._on_finished_callback(result, self._checkout, self._error)
