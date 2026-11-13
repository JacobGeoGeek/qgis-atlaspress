from dataclasses import dataclass

from .order_summary import OrderSummary


@dataclass(frozen=True)
class OrderPage:
    orders: list[OrderSummary]
    next_cursor: str | None

    @classmethod
    def from_json(cls, data):
        cursor = data["nextCursor"]
        if not isinstance(data["orders"], list) or (
            cursor is not None and (not isinstance(cursor, str) or not cursor)
        ):
            raise ValueError("Invalid order page.")
        return cls(
            [OrderSummary.from_json(item) for item in data["orders"]],
            cursor,
        )
