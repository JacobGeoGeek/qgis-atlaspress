from qgis.core import QgsTask

from ..config.model.http_response import HttpResponseError
from .errors import MockupRequestError
from .mockup_service import MockupService
from .models import MockupResponse


class CreateMockupTask(QgsTask):
    def __init__(self, service: MockupService, asset_id: str, product_id: str, callback):
        super().__init__("Create AtlasPress product preview", QgsTask.CanCancel)
        self._service = service
        self._asset_id = asset_id
        self._product_id = product_id
        self._callback = callback
        self._response: MockupResponse | None = None
        self._error: HttpResponseError | None = None

    def run(self):
        if self.isCanceled():
            return False

        try:
            self._response = self._service.create_mockup(self._asset_id, self._product_id)
            return True
        except MockupRequestError as error:
            self._error = error.error
        except Exception:
            self._error = _unexpected_error()
        return False

    def finished(self, result):
        self._callback(self._response if result else None, self._error)


class GetMockupTask(QgsTask):
    def __init__(self, service: MockupService, mockup_id: str, callback):
        super().__init__("Refresh AtlasPress product preview", QgsTask.CanCancel)
        self._service = service
        self._mockup_id = mockup_id
        self._callback = callback
        self._response: MockupResponse | None = None
        self._error: HttpResponseError | None = None

    def run(self):
        if self.isCanceled():
            return False

        try:
            self._response = self._service.get_mockup(self._mockup_id)
            return True
        except MockupRequestError as error:
            self._error = error.error
        except Exception:
            self._error = _unexpected_error()
        return False

    def finished(self, result):
        self._callback(self._response if result else None, self._error)


class RetryMockupTask(QgsTask):
    def __init__(self, service: MockupService, mockup_id: str, callback):
        super().__init__("Retry AtlasPress product preview", QgsTask.CanCancel)
        self._service = service
        self._mockup_id = mockup_id
        self._callback = callback
        self._response: MockupResponse | None = None
        self._error: HttpResponseError | None = None

    def run(self):
        if self.isCanceled():
            return False

        try:
            self._response = self._service.retry_mockup(self._mockup_id)
            return True
        except MockupRequestError as error:
            self._error = error.error
        except Exception:
            self._error = _unexpected_error()
        return False

    def finished(self, result):
        self._callback(self._response if result else None, self._error)


def _unexpected_error() -> HttpResponseError:
    return HttpResponseError(
        0,
        "Could not load the product preview. Please retry.",
        [],
    )
