from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from ...config.model.http_response import HttpResponseError


def _required_text(data: dict, field: str) -> str:
    value = str(data.get(field) or "").strip()
    if not value:
        raise ValueError(f"Missing checkout response field: {field}")
    return value


def _required_uuid(data: dict, field: str) -> str:
    value = _required_text(data, field)
    UUID(value)
    return value


def _optional_uuid(data: dict, field: str) -> str | None:
    value = data.get(field)
    if value is None:
        return None

    normalized_value = str(value).strip()
    UUID(normalized_value)
    return normalized_value


def _required_datetime(data: dict, field: str) -> str:
    value = _required_text(data, field)
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


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
            checkout_url=_required_text(data, "checkoutUrl"),
            stripe_session_id=_required_text(data, "stripeSessionId"),
            expires_at=_required_datetime(data, "expiresAt"),
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


class CheckoutStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"

    @property
    def is_final(self) -> bool:
        return self in {
            CheckoutStatus.SUCCEEDED,
            CheckoutStatus.CANCELLED,
            CheckoutStatus.FAILED,
            CheckoutStatus.EXPIRED,
        }


@dataclass(frozen=True)
class CheckoutStatusResponse:
    quote_id: str
    status: CheckoutStatus
    public_order_id: str | None
    expires_at: str

    @classmethod
    def from_json(cls, data: dict) -> "CheckoutStatusResponse":
        status = CheckoutStatus(_required_text(data, "status"))
        public_order_id = _optional_uuid(data, "publicOrderId")

        if status == CheckoutStatus.SUCCEEDED and public_order_id is None:
            raise ValueError("Successful checkout is missing its public order ID.")

        if status != CheckoutStatus.SUCCEEDED and public_order_id is not None:
            raise ValueError("Only successful checkout can include a public order ID.")

        return cls(
            quote_id=_required_uuid(data, "quoteId"),
            status=status,
            public_order_id=public_order_id,
            expires_at=_required_datetime(data, "expiresAt"),
        )


@dataclass(frozen=True)
class CheckoutStatusResponseResult:
    checkout_status: CheckoutStatusResponse | None
    error: HttpResponseError | None
