import json
from typing import Final

from qgis.core import QgsBlockingNetworkRequest, QgsNetworkAccessManager, QgsNetworkReplyContent
from qgis.PyQt.QtCore import QByteArray, QEventLoop, QUrl
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from .model.http_response import HttpResponse


class HttpClient:
    def __init__(self, base_url: str, publishable_key: str):
        self._base_url: QUrl = QUrl(base_url)
        self._publishable_key: Final[str] = publishable_key

    def _build_url(self, endpoint: str) -> QUrl:
        return self._base_url.resolved(QUrl(endpoint))

    def _apply_auth(self, request: QNetworkRequest) -> None:
        request.setRawHeader(
            b"Authorization",
            f"Bearer {self._publishable_key}".encode("utf-8"),
        )

    def _build_response(
        self,
        request: QgsBlockingNetworkRequest,
        error_code: QgsBlockingNetworkRequest.ErrorCode,
    ) -> HttpResponse:
        reply = request.reply()
        error_message = reply.errorString() if reply is not None else request.errorMessage()
        return HttpResponse(
            error_code=error_code,
            error_message=error_message,
            reply=reply,
        )

    def get(self, endpoint: str) -> HttpResponse:
        url = self._build_url(endpoint)

        request: Final[QNetworkRequest] = QNetworkRequest(url)

        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json",
        )

        self._apply_auth(request)

        reply: Final[QgsBlockingNetworkRequest] = QgsBlockingNetworkRequest()
        error_code: Final[QgsBlockingNetworkRequest.ErrorCode] = reply.get(request)

        return self._build_response(reply, error_code)

    def post(self, endpoint: str, payload: dict = None) -> HttpResponse:
        url: Final[QUrl] = self._build_url(endpoint)

        request: Final[QNetworkRequest] = QNetworkRequest(url)

        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json",
        )

        self._apply_auth(request)

        body: Final[QByteArray] = (
            QByteArray(json.dumps(payload).encode("utf-8")) if payload else QByteArray()
        )

        reply: Final[QgsBlockingNetworkRequest] = QgsBlockingNetworkRequest()
        error_code: Final[QgsBlockingNetworkRequest.ErrorCode] = reply.post(request, body)

        return self._build_response(reply, error_code)

    def patch(self, endpoint: str, payload: dict = None) -> HttpResponse:
        url: Final[QUrl] = self._build_url(endpoint)

        request: Final[QNetworkRequest] = QNetworkRequest(url)

        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            "application/json",
        )

        self._apply_auth(request)

        body: Final[QByteArray] = (
            QByteArray(json.dumps(payload).encode("utf-8")) if payload else QByteArray()
        )

        manager: Final[QgsNetworkAccessManager] = QgsNetworkAccessManager.instance()
        reply: Final[QNetworkReply] = manager.sendCustomRequest(request, b"PATCH", body)
        event_loop: Final[QEventLoop] = QEventLoop()
        reply.finished.connect(event_loop.quit)
        event_loop.exec()

        http_status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        error_code = (
            QgsBlockingNetworkRequest.NoError
            if reply.error() == QNetworkReply.NetworkError.NoError
            and (http_status_code is None or int(http_status_code) < 400)
            else QgsBlockingNetworkRequest.NetworkError
        )
        response = HttpResponse(
            error_code=error_code,
            error_message=reply.errorString(),
            reply=self._build_reply_content(reply),
        )
        reply.deleteLater()
        return response

    def _build_reply_content(self, reply: QNetworkReply) -> QgsNetworkReplyContent:
        reply_content = QgsNetworkReplyContent(reply)
        reply_content.setContent(reply.readAll())
        return reply_content

    def put(
        self,
        endpoint: str,
        data: bytes | bytearray = None,
        use_auth: bool = True,
        content_type: str = "application/octet-stream",
    ) -> HttpResponse:
        url: Final[QUrl] = self._build_url(endpoint)

        request: Final[QNetworkRequest] = QNetworkRequest(url)

        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader,
            content_type,
        )

        if use_auth:
            self._apply_auth(request)

        body: Final[QByteArray] = QByteArray(data) if data else QByteArray()

        reply: Final[QgsBlockingNetworkRequest] = QgsBlockingNetworkRequest()
        error_code: Final[QgsBlockingNetworkRequest.ErrorCode] = reply.put(request, body)

        return self._build_response(reply, error_code)

    def delete(self, endpoint: str, params: dict = None):
        # Implement DELETE request logic here
        raise NotImplementedError("HttpClient.delete() is not implemented yet")
