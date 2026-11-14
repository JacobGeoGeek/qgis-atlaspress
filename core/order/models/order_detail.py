from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from ._parsing import money, parse_date
from .order_preview import OrderPreview
from .order_summary import OrderSummary


@dataclass(frozen=True)
class OrderDetail:
    summary: OrderSummary
    paid_at: datetime | None
    item_subtotal: Decimal
    shipping_total: Decimal
    tax_total: Decimal
    mockup: OrderPreview | None

    @classmethod
    def from_json(cls, data):
        return cls(
            OrderSummary.from_json(data),
            parse_date(data["paidAt"]) if data["paidAt"] is not None else None,
            money(data["itemSubtotal"]),
            money(data["shippingTotal"]),
            money(data["taxTotal"]),
            OrderPreview.from_json(data["mockup"]) if data["mockup"] is not None else None,
        )
