from datetime import datetime
from decimal import Decimal, InvalidOperation


def parse_date(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Order dates must include a timezone.")
    return result


def money(value) -> Decimal:
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError("Invalid order amount.") from error
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid order amount.")
    return result
