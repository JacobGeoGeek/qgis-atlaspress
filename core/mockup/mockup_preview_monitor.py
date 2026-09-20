from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal

from .models import MockupStatus
from .tasks import CreateMockupTask, GetMockupTask, RetryMockupTask


class MockupPreviewMonitor(QObject):
    updated = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self._service = service
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._request)
        self._generation = 0
        self._task = None
        self._asset_product_ids_key = None
        self._cache = {}
        self._operation = "create"

    def stop(self):
        self._generation += 1
        self._timer.stop()

        if self._task is not None:
            self._task.cancel()

        self._asset_product_ids_key = None

    def start(self, asset_id, product_id):
        self.stop()

        self._asset_product_ids_key = (asset_id, product_id)
        self._operation = "get" if self._asset_product_ids_key in self._cache else "create"
        previous = self._cache.get(self._asset_product_ids_key)

        delay = (
            previous.poll_delay_ms()
            if previous and previous.status == MockupStatus.PENDING
            else 300
        )

        self._timer.start(delay)

    def retry(self):
        if self._asset_product_ids_key is None or self._task is not None:
            return

        previous = self._cache.get(self._asset_product_ids_key)

        if previous and previous.status == MockupStatus.FAILED:
            if not previous.retryable:
                return
            self._operation = "retry"

        self._timer.stop()
        self._request()

    def refresh(self):
        if self._asset_product_ids_key is not None and self._task is None:
            self._operation = "get" if self._asset_product_ids_key in self._cache else "create"
            self._timer.stop()
            self._request()

    def _request(self):
        if self._asset_product_ids_key is None or self._task is not None:
            return

        previous = self._cache.get(self._asset_product_ids_key)
        generation = self._generation

        def callback(response, error):
            self._finished(generation, response, error)

        if self._operation == "create":
            asset_id, product_id = self._asset_product_ids_key
            self._task = CreateMockupTask(self._service, asset_id, product_id, callback)
        elif self._operation == "retry":
            self._task = RetryMockupTask(self._service, previous.mockup_id, callback)
        else:
            self._task = GetMockupTask(self._service, previous.mockup_id, callback)

        QgsApplication.taskManager().addTask(self._task)

    def _finished(self, generation, response, error):
        self._task = None

        if generation != self._generation or self._asset_product_ids_key is None:
            if self._asset_product_ids_key is not None and not self._timer.isActive():
                self._timer.start(1)
            return

        if error is not None:
            if error.status_code == 404:
                self._cache.pop(self._asset_product_ids_key, None)
                self._operation = "create"
            self.failed.emit(error)
            return

        self._cache[self._asset_product_ids_key] = response
        self._operation = "get"
        self.updated.emit(response)

        if response.status == MockupStatus.PENDING and self._asset_product_ids_key is not None:
            self._timer.start(response.poll_delay_ms())
