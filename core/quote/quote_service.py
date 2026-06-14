from .models import QuoteResponse
from .quote_repository import QuoteRepository


class QuoteService:
    def __init__(self, quote_repository: QuoteRepository):
        self._quote_repository = quote_repository

    def create_quote(self, payload: dict) -> QuoteResponse:
        result = self._quote_repository.create_quote(payload)

        if result.error:
            raise Exception(result.error.message)

        if result.quote is None:
            raise Exception("Quote response is empty.")

        return result.quote

    def update_shipping_option(
        self,
        quote_id: str,
        selected_shipping_option_id: str,
    ) -> QuoteResponse:
        result = self._quote_repository.update_shipping_option(
            quote_id,
            selected_shipping_option_id,
        )

        if result.error:
            raise Exception(result.error.message)

        if result.quote is None:
            raise Exception("Quote response is empty.")

        return result.quote
