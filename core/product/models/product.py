from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError
from .productType import ProductType


@dataclass
class Product:
    id: str
    sku: str
    name: str
    type: ProductType
    width_in: float
    height_in: float
    dpi: int
    retail_price: float
    currency: str
    preview_thumbnail_url: str


@dataclass
class ProductsResponse:
    products: list[Product]
    error: HttpResponseError | None
