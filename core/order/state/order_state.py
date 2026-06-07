from dataclasses import dataclass

from ...product.models.product import Product
from ...shipping.models import ShippingAddress


@dataclass
class OrderState:
    product: Product | None = None
    asset_id: str | None = None
    shipping_address: ShippingAddress | None = None

    def set_uploaded_product(self, product: Product, asset_id: str) -> None:
        self.product = product
        self.asset_id = asset_id
        self.shipping_address = None

    def set_shipping_address(self, shipping_address: ShippingAddress) -> None:
        self.shipping_address = shipping_address

    def to_quote_payload(self) -> dict:
        if self.product is None or self.asset_id is None or self.shipping_address is None:
            raise ValueError("Order state is incomplete.")

        return {
            "assetId": self.asset_id,
            "productId": self.product.id,
            "quantity": 1,
            "recipient": self.shipping_address.to_quote_recipient_payload(),
        }
