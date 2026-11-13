from urllib.parse import quote

from ..config.http_client import HttpClient
from ..config.model.http_response import HttpResponse, HttpResponseError
from .models import OrderDetail, OrderDetailResult, OrderPage, OrderPageResult


class OrderRepository:
    def __init__(self, http_client: HttpClient):
        self._http_client = http_client

    def _get(self, endpoint: str, feedback) -> HttpResponse:
        return (
            self._http_client.get(endpoint=endpoint, feedback=feedback)
            if feedback is not None
            else self._http_client.get(endpoint=endpoint)
        )

    def _invalid_response_error(self, response: HttpResponse) -> HttpResponseError:
        return HttpResponseError(
            status_code=response.status_code() or 0,
            message="Invalid order response.",
            details=[],
        )

    def list_orders(self, cursor: str | None = None, feedback=None) -> OrderPageResult:
        endpoint = "/functions/v1/orders?limit=20"
        if cursor is not None:
            endpoint += f"&cursor={quote(cursor, safe='')}"
        response = self._get(endpoint, feedback)

        if not response.is_success():
            return OrderPageResult(
                data=None,
                error=HttpResponseError.from_response(response),
            )

        try:
            data = response.content_json()

            if not isinstance(data, dict):
                raise ValueError("Invalid order response.")

            return OrderPageResult(
                data=OrderPage.from_json(data),
                error=None,
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            return OrderPageResult(
                data=None,
                error=self._invalid_response_error(response),
            )

    def get_order_by_public_id(self, public_order_id: str, feedback=None) -> OrderDetailResult:
        response = self._get(
            f"/functions/v1/orders/{quote(public_order_id, safe='')}",
            feedback,
        )

        if not response.is_success():
            return OrderDetailResult(
                data=None,
                error=HttpResponseError.from_response(response),
            )

        try:
            data = response.content_json()

            if not isinstance(data, dict):
                raise ValueError("Invalid order response.")

            return OrderDetailResult(
                data=OrderDetail.from_json(data),
                error=None,
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            return OrderDetailResult(
                data=None,
                error=self._invalid_response_error(response),
            )
