from typing_extensions import Final

from qgis.core import Qgis, QgsMessageLog

from ..config.http_client import HttpClient
from ..config.model.http_response import HttpResponse, HttpResponseError
from .models.product import Product, ProductsResponse, ProductType

MESSAGE_CATEGORY = "AtlasPress"


class ProductRepository:
    def __init__(self, http_client: HttpClient):
        self._http_client = http_client

    def get_products_by_type(self, product_type: str) -> ProductsResponse:
        response: Final[HttpResponse] = self._http_client.get(
            endpoint=f"/functions/v1/products?type={product_type}"
        )

        if not response.is_success():
            error: Final[HttpResponseError] = HttpResponseError.from_response(response)
            return ProductsResponse(products=[], error=error)

        data: Final[dict] = response.content_json() or {}
        products_data: Final[list] = data.get("products", [])
        products = []

        for product_data in products_data:
            product_type = self._parse_product_type(product_data.get("type", ""))

            if product_type is None:
                QgsMessageLog.logMessage(
                    f"Skipping product with unknown type: {product_data.get('type', '')}",
                    MESSAGE_CATEGORY,
                    level=Qgis.Warning,
                )
                continue

            products.append(
                Product(
                    id=product_data.get("id", ""),
                    sku=product_data.get("sku", ""),
                    name=product_data.get("name", ""),
                    type=product_type,
                    width_in=product_data.get("widthIn", 0.0),
                    height_in=product_data.get("heightIn", 0.0),
                    dpi=product_data.get("dpi", 0),
                    retail_price=product_data.get("retailPrice", 0.0),
                    currency=product_data.get("currency", ""),
                    preview_thumbnail_url=product_data.get("previewThumbnailUrl", ""),
                )
            )

        return ProductsResponse(products=products, error=None)

    def _parse_product_type(self, value: str) -> ProductType | None:
        try:
            return ProductType(value)
        except ValueError:
            return None
