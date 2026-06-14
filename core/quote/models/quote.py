from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError


@dataclass(frozen=True)
class QuoteItem:
    product_id: str
    sku: str
    quantity: int
    retail_price: float


@dataclass(frozen=True)
class ShippingOption:
    id: str
    name: str
    rate: float
    estimated_days: int | None


@dataclass(frozen=True)
class QuoteTotals:
    item_subtotal: float
    shipping: float
    tax: float
    total: float


@dataclass(frozen=True)
class QuoteResponse:
    quote_id: str
    expires_at: str
    currency: str
    item: QuoteItem
    shipping_options: list[ShippingOption]
    selected_shipping_option_id: str | None
    totals: QuoteTotals

    @classmethod
    def from_json(cls, data: dict) -> "QuoteResponse":
        item_data = data.get("item", {})
        totals_data = data.get("totals", {})
        shipping_options_data = data.get("shippingOptions", [])

        return cls(
            quote_id=str(data.get("quoteId", "")),
            expires_at=str(data.get("expiresAt", "")),
            currency=str(data.get("currency", "")),
            item=QuoteItem(
                product_id=str(item_data.get("productId", "")),
                sku=str(item_data.get("sku", "")),
                quantity=int(item_data.get("quantity", 0)),
                retail_price=float(item_data.get("retailPrice", 0.0)),
            ),
            shipping_options=[
                ShippingOption(
                    id=str(option_data.get("id", "")),
                    name=str(option_data.get("name", "")),
                    rate=float(option_data.get("rate", 0.0)),
                    estimated_days=(
                        int(option_data["estimatedDays"])
                        if option_data.get("estimatedDays") is not None
                        else None
                    ),
                )
                for option_data in shipping_options_data
            ],
            selected_shipping_option_id=data.get("selectedShippingOptionId"),
            totals=QuoteTotals(
                item_subtotal=float(totals_data.get("itemSubtotal", 0.0)),
                shipping=float(totals_data.get("shipping", 0.0)),
                tax=float(totals_data.get("tax", 0.0)),
                total=float(totals_data.get("total", 0.0)),
            ),
        )


@dataclass(frozen=True)
class QuoteResponseResult:
    quote: QuoteResponse | None
    error: HttpResponseError | None
