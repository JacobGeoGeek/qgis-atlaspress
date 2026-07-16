from typing import Final

from qgis.core import Qgis, QgsMessageLog

from ..config.http_client import HttpClient
from ..config.model.http_response import HttpResponse, HttpResponseError
from .models import CheckoutResponse, CheckoutResponseResult


class CheckoutRepository:
    def __init__(self, http_client: HttpClient):
        self._http_client: Final[HttpClient] = http_client

    def create_checkout(self, quote_id: str) -> CheckoutResponseResult:
        response: Final[HttpResponse] = self._http_client.post(
            endpoint="/functions/v1/checkout",
            payload={"quoteId": quote_id},
        )

        if not response.is_success():
            return CheckoutResponseResult(
                checkout=None,
                error=HttpResponseError.from_response(response),
            )

        data = response.content_json()
        if not isinstance(data, dict):
            return self._invalid_response(response)

        totals_data = data.get("totals")
        if not isinstance(totals_data, dict) or not all(
            field in totals_data for field in ("itemSubtotal", "shipping", "tax", "total")
        ):
            return self._invalid_response(response)

        try:
            checkout = CheckoutResponse.from_json(data)
        except Exception as error:
            QgsMessageLog.logMessage(
                f"Invalid checkout response: {error}", "AtlasPress", level=Qgis.Warning
            )
            return self._invalid_response(response)

        if not all(
            (
                checkout.checkout_url,
                checkout.stripe_session_id,
                checkout.expires_at,
            )
        ):
            return self._invalid_response(response)

        return CheckoutResponseResult(checkout=checkout, error=None)

    def _invalid_response(self, response: HttpResponse) -> CheckoutResponseResult:
        return CheckoutResponseResult(
            checkout=None,
            error=HttpResponseError(
                status_code=response.status_code() or 0,
                message="Checkout response was not valid.",
                details=[],
            ),
        )
