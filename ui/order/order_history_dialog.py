from qgis.PyQt.QtCore import QEvent, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog

from ..common.spinner_widget import SpinnerWidget
from .order_history_dialog_ui import Ui_AtlasPressOrderHistoryDialog
from .order_item_delegate import OrderItemDelegate
from .order_list_model import OrderListModel


def date_text(value):
    return value.astimezone().strftime("%b %d, %Y %H:%M %Z") if value else "Not available"


def set_text(label, value):
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setText(value)


class OrderHistoryDialog(QDialog, Ui_AtlasPressOrderHistoryDialog):
    order_selected = pyqtSignal(str)
    activated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self._pixmap = None
        self.previewImageLabel.installEventFilter(self)
        self.orders_model = OrderListModel(self)
        self.ordersListView.setModel(self.orders_model)
        self._order_delegate = OrderItemDelegate(self.ordersListView)
        self.ordersListView.setItemDelegate(self._order_delegate)
        self.ordersListView.clicked.connect(self._order_activated)
        self.ordersListView.activated.connect(self._order_activated)
        self._spinners = []

        for layout in (
            self.listLoadingPageLayout,
            self.detailLoadingPageLayout,
            self.mockupLoadingPageLayout,
        ):
            spinner = SpinnerWidget(self)
            layout.insertWidget(0, spinner, alignment=Qt.AlignmentFlag.AlignCenter)
            self._spinners.append(spinner)
        self.clear_user_data()

    def _scale_preview(self):
        if self._pixmap is not None:
            self.previewImageLabel.setPixmap(
                self._pixmap.scaled(
                    self.previewImageLabel.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

    def _order_activated(self, index):
        if self.screenStackedWidget.currentWidget() is not self.listScreenPage:
            return

        public_id = index.data(Qt.ItemDataRole.UserRole)

        if public_id:
            self.order_selected.emit(public_id)

    def event(self, event):
        if event.type() == QEvent.Type.WindowActivate:
            self.activated.emit()

        return super().event(event)

    def eventFilter(self, watched, event):
        if watched is self.previewImageLabel and event.type() == QEvent.Type.Resize:
            self._scale_preview()

        return super().eventFilter(watched, event)

    def clear_user_data(self):
        self.orders_model.clear()
        self.orderIdLabel.setToolTip("")

        for label in (
            self.orderIdLabel,
            self.statusBadgeLabel,
            self.placedDateLabel,
            self.productDetailLabel,
            self.quantityLabel,
            self.itemSubtotalValueLabel,
            self.shippingTotalValueLabel,
            self.taxTotalValueLabel,
            self.totalValueLabel,
            self.paidAtLabel,
            self.listErrorMessageLabel,
            self.detailErrorMessageLabel,
            self.loadMoreErrorLabel,
        ):
            label.clear()

        self.clear_preview()
        self.loadingMoreLabel.hide()
        self.pageRetryButton.hide()
        self.screenStackedWidget.setCurrentWidget(self.listScreenPage)
        self.listStackedWidget.setCurrentWidget(self.listAuthPage)
        self.set_loading()

    def clear_preview(self):
        self._pixmap = None
        self.previewImageLabel.clear()
        self.mockupOuterStackedWidget.setCurrentWidget(self.mockupAbsentPage)
        self.mockupOuterStackedWidget.setMaximumHeight(
            max(60, self.mockupAbsentPage.sizeHint().height())
        )

    def set_loading(self, list_loading=False, detail_loading=False, preview_loading=False):
        for spinner, active in zip(self._spinners, (list_loading, detail_loading, preview_loading)):
            spinner.start() if active else spinner.stop()

    def append_orders(self, orders):
        self.orders_model.append_orders(orders)

    def show_detail(self, detail):
        order = detail.summary
        self.screenStackedWidget.setCurrentWidget(self.detailScreenPage)
        self.detailStackedWidget.setCurrentWidget(self.detailContentPage)

        values = (
            (self.orderIdLabel, f"Order #{order.public_order_id[:8]}"),
            (self.statusBadgeLabel, order.status.value),
            (self.placedDateLabel, f"Placed {date_text(order.created_at)}"),
            (
                self.productDetailLabel,
                order.product.summary if order.product else "Product details unavailable",
            ),
            (self.quantityLabel, f"Quantity: {order.quantity}"),
            (self.itemSubtotalValueLabel, f"{order.currency} {detail.item_subtotal:.2f}"),
            (self.shippingTotalValueLabel, f"{order.currency} {detail.shipping_total:.2f}"),
            (self.taxTotalValueLabel, f"{order.currency} {detail.tax_total:.2f}"),
            (self.totalValueLabel, f"{order.currency} {order.total:.2f}"),
            (self.paidAtLabel, date_text(detail.paid_at)),
        )

        for label, value in values:
            set_text(label, value)

        self.orderIdLabel.setToolTip(order.public_order_id)

    def preview_error(self, can_refresh):
        self.clear_preview()
        self.mockupOuterStackedWidget.setMaximumHeight(16777215)
        self.mockupOuterStackedWidget.setCurrentWidget(self.mockupPresentPage)
        self.mockupStackedWidget.setCurrentWidget(self.mockupErrorPage)
        self.mockupRefreshButton.setVisible(can_refresh)
        self.mockupRefreshLimitLabel.setVisible(not can_refresh)
        self.set_loading()

    def show_preview(self, pixmap):
        self._pixmap = pixmap
        self.mockupOuterStackedWidget.setMaximumHeight(16777215)
        self.mockupOuterStackedWidget.setCurrentWidget(self.mockupPresentPage)
        self.mockupStackedWidget.setCurrentWidget(self.mockupContentPage)
        self.set_loading()
        self._scale_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scale_preview()
