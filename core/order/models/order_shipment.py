from dataclasses import dataclass
from datetime import datetime

from ._parsing import parse_date


@dataclass(frozen=True, repr=False)
class OrderShipment:
    carrier: str | None
    service: str | None
    tracking_number: str | None
    tracking_url: str | None
    shipped_at: datetime | None
    reshipment: bool

    @classmethod
    def from_json(cls, data):
        for name in ("carrier", "service", "trackingNumber", "trackingUrl"):
            if data[name] is not None and not isinstance(data[name], str):
                raise ValueError("Invalid shipment field.")
        if type(data["reshipment"]) is not bool:
            raise ValueError("Invalid shipment reshipment flag.")
        return cls(
            carrier=data["carrier"],
            service=data["service"],
            tracking_number=data["trackingNumber"],
            tracking_url=data["trackingUrl"],
            shipped_at=parse_date(data["shippedAt"]) if data["shippedAt"] is not None else None,
            reshipment=data["reshipment"],
        )
