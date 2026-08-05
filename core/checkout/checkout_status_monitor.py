from typing import Final

from qgis.core import QgsApplication, QgsTask
from qgis.PyQt.QtCore import QObject, Qt, QTimer, pyqtSignal
from qgis.PyQt.QtWidgets import QApplication

from ..config.model.http_response import HttpResponseError
from .checkout_service import CheckoutService
from .models import CheckoutStatusResponse
from .tasks import GetCheckoutStatusTask


class CheckoutStatusMonitor(QObject):
    status_received = pyqtSignal(object)
    recoverable_error = pyqtSignal(object)
    fatal_error = pyqtSignal(object)
    POLL_INTERVAL_MS: Final[int] = 5_000

    def __init__(
        self,
        checkout_service: CheckoutService,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._checkout_service = checkout_service
        self._quote_id: str | None = None
        self._generation = 0
        self._request_in_progress = False
        self._status_task: QgsTask | None = None

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self.POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self.refresh)

        application = QApplication.instance()
        if application is not None:
            application.applicationStateChanged.connect(self._on_application_state_changed)

    @property
    def is_active(self) -> bool:
        return self._quote_id is not None

    def start(self, quote_id: str) -> None:
        self.stop()
        self._quote_id = quote_id
        self._poll_timer.start()
        self.refresh()

    def stop(self) -> None:
        self._generation += 1
        self._quote_id = None
        self._request_in_progress = False
        self._poll_timer.stop()

        if self._status_task is not None:
            self._status_task.cancel()
            self._status_task = None

    def refresh(self) -> None:
        if self._quote_id is None or self._request_in_progress:
            return

        quote_id = self._quote_id
        generation = self._generation
        self._request_in_progress = True
        self._status_task = GetCheckoutStatusTask(
            self._checkout_service,
            quote_id,
            lambda result, status, error: self._on_status_result(
                generation,
                result,
                status,
                error,
            ),
        )
        QgsApplication.taskManager().addTask(self._status_task)

    def _on_status_result(
        self,
        generation: int,
        result: bool,
        status: CheckoutStatusResponse | None,
        error: HttpResponseError | None,
    ) -> None:
        if generation != self._generation or self._quote_id is None:
            return

        self._request_in_progress = False
        self._status_task = None

        if result and status is not None:
            self.status_received.emit(status)
            if status.status.is_final:
                self.stop()
            return

        normalized_error = error or HttpResponseError(
            status_code=0,
            message="Could not refresh payment status.",
            details=[],
        )
        status_code = normalized_error.status_code

        if status_code == 401:
            self.stop()
            self.fatal_error.emit(
                HttpResponseError(
                    status_code=401,
                    message="Your development access token has expired.",
                    details=[],
                )
            )
            return

        if status_code in {403, 404}:
            self.stop()
            self.fatal_error.emit(
                HttpResponseError(
                    status_code=status_code,
                    message="This checkout is no longer available.",
                    details=[],
                )
            )
            return

        if status_code == 0 or status_code >= 500:
            self.recoverable_error.emit(
                HttpResponseError(
                    status_code=status_code,
                    message="Payment status could not be refreshed. AtlasPress will retry.",
                    details=[],
                )
            )
            return

        self.stop()
        self.fatal_error.emit(normalized_error)

    def _on_application_state_changed(self, state: Qt.ApplicationState) -> None:
        if state == Qt.ApplicationState.ApplicationActive:
            self.refresh()
