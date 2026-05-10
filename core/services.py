from dataclasses import dataclass

from .config.config import load_config_file
from .config.http_client import HttpClient
from .product.product_repository import ProductRepository
from .product.product_service import ProductService
from .upload.upload_repository import UploadRepository
from .upload.upload_service import UploadService


@dataclass(frozen=True)
class CoreServices:
    http_client: HttpClient
    product_service: ProductService
    upload_service: UploadService


def create_core_services() -> CoreServices:
    config = load_config_file()
    http_client = HttpClient(
        config["supabase"]["baseUrl"],
        config["supabase"]["anonKey"],
    )

    return CoreServices(
        http_client=http_client,
        product_service=ProductService(ProductRepository(http_client)),
        upload_service=UploadService(UploadRepository(http_client)),
    )
