from ..config.model.http_response import HttpResponseError


class MockupRequestError(Exception):
    def __init__(self, error: HttpResponseError):
        super().__init__(error.message)
        self.error = error
