from dataclasses import dataclass

from .assets.asset_repository import AssetRepository
from .assets.asset_service import AssetService
from .checkout.checkout_repository import CheckoutRepository
from .checkout.checkout_service import CheckoutService
from .config.config import load_config_file
from .config.http_client import HttpClient
from .product.product_repository import ProductRepository
from .product.product_service import ProductService
from .quote.quote_repository import QuoteRepository
from .quote.quote_service import QuoteService
from .shipping.shipping_repository import ShippingRepository
from .shipping.shipping_service import ShippingService


@dataclass(frozen=True)
class CoreServices:
    http_client: HttpClient
    checkout_service: CheckoutService
    product_service: ProductService
    asset_service: AssetService
    shipping_service: ShippingService
    quote_service: QuoteService


def create_core_services() -> CoreServices:
    config = load_config_file()
    supabase_config = config["supabase"]
    base_url = str(supabase_config.get("baseUrl", "")).strip()
    access_token = str(supabase_config.get("accessToken", "")).strip()

    if not base_url or not access_token:
        raise ValueError(
            "Supabase configuration requires baseUrl and a development accessToken."
        )

    http_client = HttpClient(
        base_url,
        access_token,
    )

    return CoreServices(
        http_client=http_client,
        checkout_service=CheckoutService(CheckoutRepository(http_client)),
        product_service=ProductService(ProductRepository(http_client)),
        asset_service=AssetService(AssetRepository(http_client)),
        shipping_service=ShippingService(ShippingRepository(http_client)),
        quote_service=QuoteService(QuoteRepository(http_client)),
    )
