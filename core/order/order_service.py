from .models import OrderDetail, OrderPage
from .order_repository import OrderRepository


class OrderRequestError(Exception):
    def __init__(self, error):
        super().__init__(error.message)
        self.error = error


class OrderService:
    def __init__(self, repository: OrderRepository):
        self._repository = repository

    def _require_data(self, result):
        if result.error:
            raise OrderRequestError(result.error)
        if result.data is None:
            raise ValueError("Empty order response.")
        return result.data

    def list_orders(self, cursor=None, feedback=None) -> OrderPage:
        return self._require_data(self._repository.list_orders(cursor, feedback=feedback))

    def get_order(self, public_order_id, feedback=None) -> OrderDetail:
        return self._require_data(
            self._repository.get_order_by_public_id(public_order_id, feedback=feedback)
        )
