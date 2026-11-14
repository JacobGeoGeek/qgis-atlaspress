from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError
from .order_page import OrderPage


@dataclass(frozen=True)
class OrderPageResult:
    data: OrderPage | None
    error: HttpResponseError | None
