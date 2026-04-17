from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError


@dataclass
class UploadFileResponse:
    key: str
    error: HttpResponseError | None
