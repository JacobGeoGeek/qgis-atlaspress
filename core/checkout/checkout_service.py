from ..config.model.http_response import HttpResponseError
from .checkout_repository import CheckoutRepository
from .models import CheckoutResponse, CheckoutStatusResponse


class CheckoutRequestError(Exception):
    def __init__(self, error: HttpResponseError):
        super().__init__(error.message)
        self.error = error


class CheckoutService:
    def __init__(self, checkout_repository: CheckoutRepository):
        self._checkout_repository = checkout_repository

    def create_checkout(self, quote_id: str) -> CheckoutResponse:
        result = self._checkout_repository.create_checkout(quote_id)

        if result.error:
            raise CheckoutRequestError(result.error)

        if result.checkout is None:
            raise Exception("Checkout response is empty.")

        return result.checkout

    def get_checkout_status(self, quote_id: str) -> CheckoutStatusResponse:
        result = self._checkout_repository.get_checkout_status(quote_id)

        if result.error:
            raise CheckoutRequestError(result.error)

        if result.checkout_status is None:
            raise Exception("Checkout status response is empty.")

        return result.checkout_status
