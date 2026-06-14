from dataclasses import dataclass

from .config.config import load_config_file
from .config.http_client import HttpClient
from .product.product_repository import ProductRepository
from .product.product_service import ProductService
from .assets.asset_repository import AssetRepository
from .assets.asset_service import AssetService
from .quote.quote_repository import QuoteRepository
from .quote.quote_service import QuoteService
from .shipping.shipping_repository import ShippingRepository
from .shipping.shipping_service import ShippingService


@dataclass(frozen=True)
class CoreServices:
    http_client: HttpClient
    product_service: ProductService
    asset_service: AssetService
    shipping_service: ShippingService
    quote_service: QuoteService


def create_core_services() -> CoreServices:
    config = load_config_file()
    http_client = HttpClient(
        config["supabase"]["baseUrl"],
        config["supabase"]["anonKey"],
    )

    return CoreServices(
        http_client=http_client,
        product_service=ProductService(ProductRepository(http_client)),
        asset_service=AssetService(AssetRepository(http_client)),
        shipping_service=ShippingService(ShippingRepository(http_client)),
        quote_service=QuoteService(QuoteRepository(http_client)),
    )
