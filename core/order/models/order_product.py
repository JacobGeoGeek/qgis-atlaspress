from dataclasses import dataclass
from decimal import Decimal

from ._parsing import money


@dataclass(frozen=True)
class OrderProduct:
    name: str
    type: str
    width_in: Decimal
    height_in: Decimal

    @classmethod
    def from_json(cls, data):
        return cls(
            data["name"],
            data["type"],
            money(data["widthIn"]),
            money(data["heightIn"]),
        )

    @property
    def summary(self) -> str:
        return f"{self.name} - {self.width_in:g} x {self.height_in:g} in"
