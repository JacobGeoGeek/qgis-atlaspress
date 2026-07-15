from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError


@dataclass(frozen=True)
class CheckoutTotals:
    item_subtotal: float
    shipping: float
    tax: float
    total: float


@dataclass(frozen=True)
class CheckoutResponse:
    checkout_url: str
    stripe_session_id: str
    expires_at: str
    totals: CheckoutTotals

    @classmethod
    def from_json(cls, data: dict) -> "CheckoutResponse":
        totals_data = data.get("totals", {})

        return cls(
            checkout_url=str(data.get("checkoutUrl") or "").strip(),
            stripe_session_id=str(data.get("stripeSessionId") or "").strip(),
            expires_at=str(data.get("expiresAt") or "").strip(),
            totals=CheckoutTotals(
                item_subtotal=float(totals_data.get("itemSubtotal", 0.0)),
                shipping=float(totals_data.get("shipping", 0.0)),
                tax=float(totals_data.get("tax", 0.0)),
                total=float(totals_data.get("total", 0.0)),
            ),
        )


@dataclass(frozen=True)
class CheckoutResponseResult:
    checkout: CheckoutResponse | None
    error: HttpResponseError | None
