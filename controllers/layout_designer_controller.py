from typing import Final

from qgis.core import Qgis, QgsLayout, QgsLayoutItem, QgsLayoutItemPage, QgsMessageLog
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtGui import QAction, QIcon
from qgis.PyQt.QtWidgets import QMenu, QToolBar

from ..core import (
    AssetService,
    CheckoutService,
    CoreServices,
    OrderState,
    ProductService,
    QuoteResponse,
    QuoteService,
    ShippingService,
)
from ..core.product.models.product import Product
from ..core.shipping.models import ShippingAddress
from ..ui.checkout import CheckoutDialog
from ..ui.product import ProductDialog
from ..ui.quote import QuoteDialog
from ..ui.shipping import ShippingAddressDialog


class LayoutDesignerController:
    def __init__(
        self,
        designer: QgsLayoutDesignerInterface,
        core_services: CoreServices,
    ):
        self._designer: QgsLayoutDesignerInterface = designer
        self._designer_id: Final[int] = id(self._designer)

        self._asset_service: AssetService = core_services.asset_service
        self._checkout_service: CheckoutService = core_services.checkout_service
        self._product_service: ProductService = core_services.product_service
        self._shipping_service: ShippingService = core_services.shipping_service
        self._quote_service: QuoteService = core_services.quote_service
        self._order_state: Final[OrderState] = OrderState()
        self._shipping_dialog: ShippingAddressDialog | None = None
        self._quote_dialog: QuoteDialog | None = None
        self._checkout_dialog: CheckoutDialog | None = None

        self._product_dialog: ProductDialog | None = None

        self._pdf_export_action_name_toolbar: Final[str] = "mActionExportAsPDF"
        self._pdf_export_action_atlas_menu: Final[str] = "mActionExportAtlasAsPDF"

        self._atlas_press_action: Final[QAction] = QAction(
            icon=QIcon(":/plugins/atlas_press/resources/icons/atlas_press.svg"),
            text="Export to Atlas Press",
            parent=self._designer,
            objectName="actionExportToAtlasPress",
        )
        self._atlas_press_action.triggered.connect(self._upload_layout_file)

    def add_export_to_atlas_actions(self):
        QgsMessageLog.logMessage(
            "Adding AtlasPress actions.",
            "AtlasPress",
            level=Qgis.Info,
        )

        self._add_export_to_atlas_action_to_layout_toolbar()
        self._add_export_to_atlas_action_to_atlas_menu()

    def remove_export_to_atlas_actions(self):
        layout_toolbar: Final[QToolBar] = self._designer.layoutToolbar()

        if layout_toolbar is not None:
            layout_toolbar.removeAction(self._atlas_press_action)
            QgsMessageLog.logMessage(
                f"Removed AtlasPress action from toolbar from {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Info,
            )

        atlas_menu: Final[QMenu] = self._designer.atlasMenu()

        if atlas_menu is not None:
            atlas_menu.removeAction(self._atlas_press_action)
            QgsMessageLog.logMessage(
                f"Removed AtlasPress action from atlas menu from {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Info,
            )

    def _add_export_to_atlas_action_to_layout_toolbar(self):
        layout_toolbar: Final[QToolBar] = self._designer.layoutToolbar()
        actions_toolbar: Final[list[QAction]] = layout_toolbar.actions()

        if self._pdf_export_action_name_toolbar not in [
            action.objectName() for action in actions_toolbar
        ]:
            QgsMessageLog.logMessage(
                f"Toolbar anchor '{self._pdf_export_action_name_toolbar}' not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        target_index: int = -1

        for index, action in enumerate(actions_toolbar):
            if action.objectName() == self._pdf_export_action_name_toolbar:
                target_index = index + 1
                break

        if target_index == -1:
            QgsMessageLog.logMessage(
                f"Toolbar insertion point not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        if target_index == len(actions_toolbar):
            layout_toolbar.addAction(self._atlas_press_action)
        else:
            layout_toolbar.insertAction(actions_toolbar[target_index], self._atlas_press_action)

        QgsMessageLog.logMessage(
            f"Inserted AtlasPress action into layout toolbar in {self._designer_id}.",
            "AtlasPress",
            level=Qgis.Info,
        )

    def _add_export_to_atlas_action_to_atlas_menu(self):
        atlas_menu: Final[QMenu] = self._designer.atlasMenu()

        if atlas_menu is None:
            QgsMessageLog.logMessage(
                f"No atlas menu found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        actions_atlas_menu: Final[list[QAction]] = atlas_menu.actions()

        if self._pdf_export_action_atlas_menu not in [
            action.objectName() for action in actions_atlas_menu
        ]:
            QgsMessageLog.logMessage(
                f"Atlas menu anchor '{self._pdf_export_action_atlas_menu}' not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        target_index: int = -1

        for index, action in enumerate(actions_atlas_menu):
            if action.objectName() == self._pdf_export_action_atlas_menu:
                target_index = index + 1
                break

        if target_index == -1:
            QgsMessageLog.logMessage(
                f"Atlas menu insertion point not found in {self._designer_id}.",
                "AtlasPress",
                level=Qgis.Warning,
            )
            return

        if target_index >= len(actions_atlas_menu):
            atlas_menu.addAction(self._atlas_press_action)
        else:
            atlas_menu.insertAction(actions_atlas_menu[target_index], self._atlas_press_action)

        QgsMessageLog.logMessage(
            f"Inserted AtlasPress action into atlas menu in {self._designer_id}.",
            "AtlasPress",
            level=Qgis.Info,
        )

    def _upload_layout_file(self, checked: bool = False):
        if not self._validate_designer_layout(self._designer):
            return

        self._product_dialog = ProductDialog(
            self._product_service,
            self._asset_service,
            self._designer,
            self._on_product_uploaded,
        )
        self._product_dialog.show()

    def _on_product_uploaded(self, product: Product, asset_id: str) -> None:
        self._order_state.set_uploaded_product(product, asset_id)
        self._shipping_dialog = ShippingAddressDialog(
            self._shipping_service,
            self._on_shipping_address_completed,
            self._on_shipping_back_requested,
        )
        self._shipping_dialog.show()

    def _on_shipping_address_completed(self, shipping_address: ShippingAddress) -> None:
        self._order_state.set_shipping_address(shipping_address)
        QgsMessageLog.logMessage(
            f"Shipping information captured for asset ID: {self._order_state.asset_id}",
            "AtlasPress",
            level=Qgis.Info,
        )
        self._quote_dialog = QuoteDialog(
            self._quote_service,
            self._order_state,
            self._on_quote_updated,
            self._on_checkout_requested,
            self._on_quote_back_requested,
        )
        self._quote_dialog.show()

    def _on_quote_updated(self, quote: QuoteResponse) -> None:
        self._order_state.set_quote(quote)
        QgsMessageLog.logMessage(
            f"Quote captured with ID: {quote.quote_id}",
            "AtlasPress",
            level=Qgis.Info,
        )

    def _on_checkout_requested(self) -> None:
        self._checkout_dialog = CheckoutDialog(
            self._checkout_service,
            self._order_state,
        )
        self._checkout_dialog.show()

    def _on_shipping_back_requested(self) -> None:
        if self._product_dialog is not None:
            self._product_dialog.show()

    def _on_quote_back_requested(self) -> None:
        if self._shipping_dialog is not None:
            self._shipping_dialog.show()

    def _validate_designer_layout(self, designer: QgsLayoutDesignerInterface) -> bool:
        layout: Final[QgsLayout] = designer.layout()

        if not layout:
            designer.messageBar().pushWarning("AtlasPress", "No layout found to export.")
            return False

        page_count: Final[int] = layout.pageCollection().pageCount()

        if page_count != 1:
            designer.messageBar().pushWarning(
                "AtlasPress",
                (
                    f"Layout has {page_count} pages. "
                    "Please ensure the layout has exactly one page before exporting."
                ),
            )
            return False

        content_items: Final[list[QgsLayoutItem]] = list(
            filter(
                lambda item: not isinstance(item, QgsLayoutItemPage),
                layout.pageCollection().itemsOnPage(0),
            )
        )

        if len(content_items) == 0:
            designer.messageBar().pushWarning(
                "AtlasPress",
                (
                    "Layout has no items on the first page. "
                    "Please ensure the layout has at least one item before exporting."
                ),
            )
            return False

        return True
