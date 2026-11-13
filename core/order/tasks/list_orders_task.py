from qgis.core import QgsFeedback, QgsTask

from ...config.model.http_response import HttpResponseError
from ..models import OrderPage
from ..order_service import OrderRequestError


class ListOrdersTask(QgsTask):
    def __init__(self, service, cursor, callback):
        super().__init__("Load AtlasPress orders", QgsTask.CanCancel)
        self._service = service
        self._cursor = cursor
        self._callback = callback
        self._data: OrderPage | None = None
        self._error: HttpResponseError | None = None
        self._feedback = QgsFeedback()

    def cancel(self):
        self._feedback.cancel()
        super().cancel()

    def run(self):
        if self.isCanceled():
            return False

        try:
            self._data = self._service.list_orders(self._cursor, feedback=self._feedback)
            return True
        except OrderRequestError as error:
            self._error = error.error
        except Exception:
            # Do not log backend bodies, credentials, or signed URLs.
            self._error = HttpResponseError(0, "Could not load order information.", [])

        return False

    def finished(self, result):
        if not self.isCanceled():
            self._callback(self._data if result else None, self._error)
