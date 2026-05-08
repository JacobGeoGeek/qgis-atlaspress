from typing import Final

from .models.product import Product, ProductsResponse
from .models.productType import ProductType
from .product_repository import ProductRepository


class ProductService:
    def __init__(self, product_repository: ProductRepository):
        self._product_repository = product_repository

    def get_products_by_type(self, product_type: ProductType) -> list[Product]:
        if product_type not in ProductType:
            raise ValueError(f"Invalid product type: {product_type}")

        result: Final[ProductsResponse] = self._product_repository.get_products_by_type(
            product_type.value
        )

        if result.error:
            raise Exception(f"Error fetching products: {result.error.message}")

        return result.products
