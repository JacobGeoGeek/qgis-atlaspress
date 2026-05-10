from qgis.core import Qgis, QgsMessageLog, QgsTask

from ..models.product import ProductType
from ..product_service import ProductService

MESSAGE_CATEGORY = "ProductsByTypeTask"


class FetchProductsByTypeTask(QgsTask):
    def __init__(
        self,
        product_service: ProductService,
        product_type: ProductType,
        on_finished_callback: callable,
    ):
        super().__init__(
            f"Fetch products of type {product_type}",
            QgsTask.CanCancel,
        )
        self._product_service = product_service
        self._product_type = product_type
        self._on_finished_callback = on_finished_callback
        self._products = []

    def run(self):
        try:
            self._products = self._product_service.get_products_by_type(self._product_type)
            return True
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Error fetching products of type {self._product_type}: {e}",
                MESSAGE_CATEGORY,
                level=Qgis.Critical,
            )
            return False

    def finished(self, result):
        self._on_finished_callback(result, self._products)
