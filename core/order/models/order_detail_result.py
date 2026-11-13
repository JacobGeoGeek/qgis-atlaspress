from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError
from .order_detail import OrderDetail


@dataclass(frozen=True)
class OrderDetailResult:
    data: OrderDetail | None
    error: HttpResponseError | None
