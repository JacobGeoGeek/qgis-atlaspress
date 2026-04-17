import json
from dataclasses import dataclass

from qgis.core import QgsBlockingNetworkRequest, QgsNetworkReplyContent
from qgis.PyQt.QtNetwork import QNetworkRequest

from .error_details import ErrorDetails


@dataclass
class HttpResponse:
    error_code: QgsBlockingNetworkRequest.ErrorCode
    error_message: str
    reply: QgsNetworkReplyContent | None

    def is_success(self) -> bool:
        return self.error_code == QgsBlockingNetworkRequest.NoError

    def content_json(self) -> dict | list | None:
        if self.reply is None:
            return None

        raw = self.reply.content()
        if not raw:
            return None

        try:
            return json.loads(bytes(raw).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def content_text(self) -> str:
        if self.reply is None:
            return ""

        raw = self.reply.content()
        if not raw:
            return ""

        try:
            return bytes(raw).decode("utf-8")
        except UnicodeDecodeError:
            return ""

    def status_code(self) -> int | None:
        if self.reply is None:
            return None

        status_code = self.reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status_code is None:
            return None
        return int(status_code)


@dataclass
class HttpResponseError:
    status_code: int
    message: str
    details: list[ErrorDetails]

    @classmethod
    def from_response(cls, response: HttpResponse) -> "HttpResponseError":
        data = response.content_json()
        if not isinstance(data, dict):
            return cls(
                status_code=response.status_code() or 0,
                message=response.content_text() or response.error_message,
                details=[],
            )

        details = [ErrorDetails(**detail) for detail in data.get("details", [])]

        return cls(
            status_code=response.status_code() or 0,
            message=data.get("error", "") or response.content_text() or response.error_message,
            details=details,
        )
