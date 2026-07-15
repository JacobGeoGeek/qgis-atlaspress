from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices, QPixmap
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QWidget,
)

from ...core.checkout.checkout_service import CheckoutService
from ...core.checkout.models import CheckoutResponse
from ...core.checkout.tasks import CreateCheckoutTask
from ...core.config.model.http_response import HttpResponseError
from ...core.order import OrderState
from ...core.product.models.product import Product
from ...core.quote.models import QuoteResponse, ShippingOption
from ...core.quote.quote_service import QuoteService
from ...core.quote.tasks import CreateQuoteTask, UpdateShippingOptionTask
from ...core.shipping.models import ShippingAddress
from ..common.spinner_widget import SpinnerWidget
from .quote_dialog_ui import Ui_AtlasPressQuoteDialog


class QuoteDialog(QDialog, Ui_AtlasPressQuoteDialog):
    def __init__(
        self,
        quote_service: QuoteService,
        checkout_service: CheckoutService,
        order_state: OrderState,
        on_quote_updated: callable,
        on_back_requested: callable,
        parent=None,
    ):
        super().__init__(parent)
        self.setupUi(self)

        self._quote_service = quote_service
        self._checkout_service = checkout_service
        self._order_state = order_state
        self._on_quote_updated = on_quote_updated
        self._on_back_requested = on_back_requested
        self._network_manager = QNetworkAccessManager(self)
        self._current_quote: QuoteResponse | None = None
        self._pending_shipping_option_id: str | None = None
        self._last_failed_operation = "create"
        self._checkout_in_progress = False
        self._pending_checkout_url: str | None = None
        self._rendering_shipping_options = False
        self._shipping_option_button_group = QButtonGroup(self)
        self._shipping_option_button_group.setExclusive(True)

        self._spinner = SpinnerWidget()
        self.quoteLoadingSpinnerLabel.hide()
        self.quoteLoadingLayout.insertWidget(
            1, self._spinner, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self._continue_button = self.buttonsActions.button(QDialogButtonBox.StandardButton.Ok)
        if self._continue_button is not None:
            self._continue_button.setText("Continue to Payment")
            self._continue_button.clicked.connect(self._continue_to_payment)
        self._back_button = self.buttonsActions.addButton(
            "Back",
            QDialogButtonBox.ButtonRole.ActionRole,
        )

        self.buttonsActions.accepted.disconnect(self.accept)
        self.buttonsActions.rejected.connect(self.reject)
        self._back_button.clicked.connect(self._go_back)
        self.quoteRetryButton.clicked.connect(self._retry_last_request)
        self._set_continue_enabled(False)
        self._request_quote()

    def _request_quote(self) -> None:
        try:
            quote_payload = self._order_state.to_quote_payload()
        except ValueError as error:
            self._show_error(None, str(error))
            return

        self._last_failed_operation = "create"
        self._show_loading("Calculating your quote...")
        QgsApplication.taskManager().addTask(
            CreateQuoteTask(
                self._quote_service,
                quote_payload,
                self._on_quote_created,
            )
        )

    def _request_shipping_option_update(self, shipping_option_id: str) -> None:
        if self._current_quote is None:
            return

        self._pending_shipping_option_id = shipping_option_id
        self._last_failed_operation = "update"
        self._show_loading("Updating shipping method...")
        QgsApplication.taskManager().addTask(
            UpdateShippingOptionTask(
                self._quote_service,
                self._current_quote.quote_id,
                shipping_option_id,
                self._on_shipping_option_updated,
            )
        )

    def _on_quote_created(
        self,
        result: bool,
        quote: QuoteResponse | None,
        error: HttpResponseError | None,
    ) -> None:
        if not result or quote is None:
            self._show_error(error, "Could not calculate quote.")
            return

        self._current_quote = quote
        self._render_quote(quote)

    def _on_shipping_option_updated(
        self,
        result: bool,
        quote: QuoteResponse | None,
        error: HttpResponseError | None,
    ) -> None:
        if not result or quote is None:
            self._show_error(error, "Could not update shipping method.")
            return

        self._pending_shipping_option_id = None
        self._current_quote = quote
        self._render_quote(quote)

    def _render_quote(self, quote: QuoteResponse) -> None:
        self._spinner.stop()
        self._current_quote = quote
        self._on_quote_updated(quote)
        self._render_product(self._order_state.product, quote)
        self._render_shipping_address(self._order_state.shipping_address)
        self._render_shipping_options(quote)
        self._render_price_summary(quote)
        self.dialogStackedWidget.setCurrentWidget(self.quoteContentPage)
        self._set_continue_enabled(True)

    def _render_product(self, product: Product | None, quote: QuoteResponse) -> None:
        if product is None:
            self.productNameLabel.setText("Selected product")
            self.productVariantLabel.setText(quote.item.name or quote.item.sku)
            self._show_product_placeholder()
            return

        self.productNameLabel.setText(product.name)
        self.productVariantLabel.setText(f'Size: {product.width_in}" x {product.height_in}"')
        self._load_product_image(product.preview_thumbnail_url)

    def _render_shipping_address(self, address: ShippingAddress | None) -> None:
        if address is None:
            return

        self.shipNameLabel.setText(address.name)
        self.shipEmailLabel.setText(address.email)
        self.shipAddressLabel.setText(
            f"{address.address1}{', ' + address.address2 if address.address2 else ''}"
        )
        self.shipCityLabel.setText(
            f"{address.city}{', ' + address.state_code if address.state_code else ''}"
        )
        self.shipCountryPostalLabel.setText(f"{address.country_code} - {address.zip}")

    def _render_shipping_options(self, quote: QuoteResponse) -> None:
        self._clear_shipping_options()
        self._shipping_option_button_group = QButtonGroup(self)
        self._shipping_option_button_group.setExclusive(True)
        self._rendering_shipping_options = True
        selected_option_id = quote.selected_shipping_option_id

        for option in quote.shipping_options:
            radio_button = QRadioButton()
            radio_button.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Fixed,
            )
            radio_button.setChecked(option.id == selected_option_id)
            radio_button.toggled.connect(
                lambda checked, option_id=option.id: self._on_shipping_option_selected(
                    option_id,
                    checked,
                )
            )
            self._shipping_option_button_group.addButton(radio_button)
            self.shippingOptionsLayout.addWidget(
                self._build_shipping_option_row(
                    radio_button,
                    self._format_shipping_option(option, quote.currency),
                )
            )

        self._rendering_shipping_options = False

    def _render_price_summary(self, quote: QuoteResponse) -> None:
        self.productPriceLabel.setText(
            self._format_price(quote.currency, quote.totals.item_subtotal)
        )
        self.shippingPriceLabel.setText(self._format_price(quote.currency, quote.totals.shipping))
        self.totalPriceLabel.setText(self._format_price(quote.currency, quote.totals.total))
        self.currencyNoteLabel.setText(
            f"All prices in {quote.currency}. Taxes may apply at checkout."
        )

    def _on_shipping_option_selected(self, shipping_option_id: str, checked: bool) -> None:
        if self._rendering_shipping_options or not checked or self._current_quote is None:
            return

        if shipping_option_id == self._current_quote.selected_shipping_option_id:
            return

        self._request_shipping_option_update(shipping_option_id)

    def _retry_last_request(self) -> None:
        if self._last_failed_operation == "open_browser" and self._pending_checkout_url:
            self._open_checkout_url(self._pending_checkout_url)
            return

        if self._last_failed_operation == "checkout":
            self._request_checkout()
            return

        if self._last_failed_operation == "update" and self._pending_shipping_option_id:
            self._request_shipping_option_update(self._pending_shipping_option_id)
            return

        self._request_quote()

    def _continue_to_payment(self) -> None:
        self._request_checkout()

    def _request_checkout(self) -> None:
        if self._current_quote is None or self._checkout_in_progress:
            return

        self._checkout_in_progress = True
        self._pending_checkout_url = None
        self._last_failed_operation = "checkout"
        self._show_loading("Preparing secure checkout...")
        self._set_navigation_enabled(False)
        QgsApplication.taskManager().addTask(
            CreateCheckoutTask(
                self._checkout_service,
                self._current_quote.quote_id,
                self._on_checkout_created,
            )
        )

    def _on_checkout_created(
        self,
        result: bool,
        checkout: CheckoutResponse | None,
        error: HttpResponseError | None,
    ) -> None:
        self._checkout_in_progress = False
        self._set_navigation_enabled(True)

        if not result or checkout is None:
            self._show_error(error, "Could not prepare checkout.")
            return

        self._open_checkout_url(checkout.checkout_url)

    def _open_checkout_url(self, checkout_url: str) -> None:
        url = QUrl(checkout_url)
        if not url.isValid() or url.scheme().lower() != "https" or not url.host():
            self._last_failed_operation = "checkout"
            self._show_error(None, "Checkout returned an invalid secure URL.")
            return

        self._pending_checkout_url = checkout_url
        if not QDesktopServices.openUrl(url):
            self._last_failed_operation = "open_browser"
            self._show_error(None, "Could not open checkout in your default browser.")
            return

        self._pending_checkout_url = None
        self._show_quote_content()

    def _show_quote_content(self) -> None:
        self._spinner.stop()
        self.dialogStackedWidget.setCurrentWidget(self.quoteContentPage)
        self._set_navigation_enabled(True)
        self._set_continue_enabled(self._current_quote is not None)

    def _go_back(self) -> None:
        self.reject()
        self._on_back_requested()

    def _show_loading(self, message: str) -> None:
        self._spinner.start()
        self.quoteLoadingTextLabel.setText(message)
        self.dialogStackedWidget.setCurrentWidget(self.quoteLoadingPage)
        self._set_continue_enabled(False)

    def _show_error(
        self,
        error: HttpResponseError | None,
        fallback_message: str,
    ) -> None:
        self._spinner.stop()
        self.quoteErrorTitleLabel.setText(error.message if error else fallback_message)

        detail_messages = [detail.message for detail in error.details] if error else []
        self.quoteErrorDetailsLabel.setText(
            "\n".join(f"• {message}" for message in detail_messages)
        )
        self.quoteErrorDetailsLabel.setVisible(bool(detail_messages))
        self.quoteErrorMessageLabel.setText(
            "Review the details below, then go back and try again."
            if detail_messages
            else "Go back and review your information, then try again."
        )
        self.dialogStackedWidget.setCurrentWidget(self.quoteErrorPage)
        self._set_navigation_enabled(True)
        self._set_continue_enabled(False)

    def _set_navigation_enabled(self, enabled: bool) -> None:
        self._back_button.setEnabled(enabled)
        cancel_button = self.buttonsActions.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button is not None:
            cancel_button.setEnabled(enabled)

    def _build_shipping_option_row(self, radio_button: QRadioButton, text: str) -> QWidget:
        row = QWidget(self.shippingOptionsGroupBox)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        label = QLabel(text, row)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        label.setStyleSheet("color: palette(text); font-size: 12px;")
        label.mousePressEvent = lambda _event: radio_button.setChecked(True)

        row_layout.addWidget(radio_button, 0, Qt.AlignmentFlag.AlignTop)
        row_layout.addWidget(label, 1)
        return row

    def _clear_shipping_options(self) -> None:
        while self.shippingOptionsLayout.count():
            item = self.shippingOptionsLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_continue_enabled(self, enabled: bool) -> None:
        if self._continue_button is not None:
            self._continue_button.setEnabled(enabled)

    def _format_price(self, currency: str, amount: float) -> str:
        return f"{currency} {amount:.2f}"

    def _format_shipping_option(self, option: ShippingOption, currency: str) -> str:
        estimated_days = (
            f" - {option.estimated_days} business days" if option.estimated_days else ""
        )
        return f"{option.name} - {self._format_price(currency, option.rate)}{estimated_days}"

    def _load_product_image(self, url: str) -> None:
        if not url:
            self._show_product_placeholder()
            return

        image_url = QUrl(url)
        if not image_url.isValid() or image_url.scheme() == "":
            self._show_product_placeholder()
            return

        reply = self._network_manager.get(QNetworkRequest(image_url))
        reply.finished.connect(lambda: self._on_product_image_loaded(reply))

    def _on_product_image_loaded(self, reply: QNetworkReply) -> None:
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._show_product_placeholder()
        else:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            if pixmap.isNull():
                self._show_product_placeholder()
            else:
                self.productThumbnailLabel.setPixmap(
                    pixmap.scaled(
                        56,
                        56,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        reply.deleteLater()

    def _show_product_placeholder(self) -> None:
        self.productThumbnailLabel.setText("No\nimage")
        self.productThumbnailLabel.setStyleSheet(
            "background: #f0f0f0; border: 1px dashed #cccccc; "
            "border-radius: 4px; color: #999999; font-size: 10px;"
        )
