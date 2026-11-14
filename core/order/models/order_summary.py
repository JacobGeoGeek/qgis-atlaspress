from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from ._parsing import money, parse_date
from .order_product import OrderProduct
from .order_status import OrderStatus


@dataclass(frozen=True)
class OrderSummary:
    public_order_id: str
    created_at: datetime
    updated_at: datetime
    status: OrderStatus
    product: OrderProduct | None
    quantity: int
    total: Decimal
    currency: str

    @classmethod
    def from_json(cls, data):
        public_id = data["publicOrderId"]
        UUID(public_id)
        quantity = data["quantity"]
        if type(quantity) is not int or quantity < 1:
            raise ValueError("Invalid order quantity.")
        currency = data["currency"]
        if not isinstance(currency, str) or not currency:
            raise ValueError("Invalid order currency.")
        return cls(
            public_id,
            parse_date(data["createdAt"]),
            parse_date(data["updatedAt"]),
            OrderStatus[data["status"]],
            OrderProduct.from_json(data["product"]) if data["product"] is not None else None,
            quantity,
            money(data["total"]),
            currency,
        )
