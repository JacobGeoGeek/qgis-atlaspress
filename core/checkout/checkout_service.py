from ..config.model.http_response import HttpResponseError
from .checkout_repository import CheckoutRepository
from .models import CheckoutResponse


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
