from dataclasses import dataclass
from enum import Enum

from ...config.model.http_response import HttpResponseError


class ProductType(Enum):
    POSTER = "poster"
    CANVAS = "canvas"


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
