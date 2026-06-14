from typing import Final

from ..config.http_client import HttpClient
from ..config.model.http_response import HttpResponse, HttpResponseError
from .models import QuoteResponse, QuoteResponseResult


class QuoteRepository:
    def __init__(self, http_client: HttpClient):
        self._http_client: Final[HttpClient] = http_client

    def create_quote(self, payload: dict) -> QuoteResponseResult:
        response: Final[HttpResponse] = self._http_client.post(
            endpoint="/functions/v1/quotes",
            payload=payload,
        )

        return self._parse_quote_response(response)

    def update_shipping_option(
        self,
        quote_id: str,
        selected_shipping_option_id: str,
    ) -> QuoteResponseResult:
        response: Final[HttpResponse] = self._http_client.patch(
            endpoint=f"/functions/v1/quotes/{quote_id}/shipping-option",
            payload={"selectedShippingOptionId": selected_shipping_option_id},
        )

        return self._parse_quote_response(response)

    def _parse_quote_response(self, response: HttpResponse) -> QuoteResponseResult:
        if not response.is_success():
            error: Final[HttpResponseError] = HttpResponseError.from_response(response)
            return QuoteResponseResult(quote=None, error=error)

        data = response.content_json()
        if not isinstance(data, dict):
            return QuoteResponseResult(
                quote=None,
                error=HttpResponseError(
                    status_code=response.status_code() or 0,
                    message="Quote response was not valid JSON.",
                    details=[],
                ),
            )

        return QuoteResponseResult(
            quote=QuoteResponse.from_json(data),
            error=None,
        )
