from dataclasses import dataclass

from .order_shipment import OrderShipment


@dataclass(frozen=True, repr=False)
class OrderTracking:
    shipments: list[OrderShipment]

    @classmethod
    def from_json(cls, data):
        if not isinstance(data["shipments"], list):
            raise ValueError("Invalid order shipments.")
        return cls(shipments=[OrderShipment.from_json(item) for item in data["shipments"]])
