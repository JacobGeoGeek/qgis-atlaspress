from qgis.core import QgsApplication, QgsTask
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QCloseEvent, QDesktopServices
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QMessageBox

from ...core.checkout.checkout_service import CheckoutService
from ...core.checkout.checkout_status_monitor import CheckoutStatusMonitor
from ...core.checkout.models import (
    CheckoutResponse,
    CheckoutStatus,
    CheckoutStatusResponse,
)
from ...core.checkout.tasks import CreateCheckoutTask
from ...core.config.model.http_response import HttpResponseError
from ...core.order import OrderState
from ..common.spinner_widget import SpinnerWidget
from .checkout_dialog_ui import Ui_AtlasPressCheckoutDialog


class CheckoutDialog(QDialog, Ui_AtlasPressCheckoutDialog):
    def __init__(
        self,
        checkout_service: CheckoutService,
        order_state: OrderState,
        parent=None,
    ):
        super().__init__(parent)
        self.setupUi(self)

        self._checkout_service = checkout_service
        self._order_state = order_state
        self._status_monitor = CheckoutStatusMonitor(checkout_service, self)
        self._checkout_task: QgsTask | None = None
        self._active_checkout: CheckoutResponse | None = None
        self._payment_status = CheckoutStatus.NOT_STARTED
        self._pending_checkout_url: str | None = None
        self._retry_operation = "create"
        self._closed = False

        self._spinner = SpinnerWidget()
        self.checkoutLoadingSpinnerLabel.hide()
        self.checkoutLoadingLayout.insertWidget(
            1, self._spinner, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self._close_button = self.buttonsActions.button(QDialogButtonBox.StandardButton.Close)
        self._action_button = self.buttonsActions.button(QDialogButtonBox.StandardButton.Retry)
        if self._close_button is not None:
            self._close_button.clicked.connect(self.reject)
        if self._action_button is not None:
            self._action_button.clicked.connect(self._retry)

        self.buttonsActions.rejected.disconnect(self.reject)
        self._status_monitor.status_received.connect(self._on_status_received)
        self._status_monitor.recoverable_error.connect(self._on_recoverable_error)
        self._status_monitor.fatal_error.connect(self._on_fatal_error)
        self._request_checkout()

    def _request_checkout(self) -> None:
        quote = self._order_state.quote
        if quote is None or self._checkout_task is not None:
            if quote is None:
                self._show_error(None, "A valid quote is required before checkout.", False)
            return

        self._status_monitor.stop()
        self._active_checkout = None
        self._payment_status = CheckoutStatus.NOT_STARTED
        self._pending_checkout_url = None
        self._retry_operation = "create"
        self._show_loading("Preparing secure checkout...")
        self._checkout_task = CreateCheckoutTask(
            self._checkout_service,
            quote.quote_id,
            self._on_checkout_created,
        )
        QgsApplication.taskManager().addTask(self._checkout_task)

    def _on_checkout_created(
        self,
        result: bool,
        checkout: CheckoutResponse | None,
        error: HttpResponseError | None,
    ) -> None:
        self._checkout_task = None
        if self._closed:
            return

        if not result or checkout is None:
            self._show_error(error, "Could not prepare checkout.")
            return

        self._active_checkout = checkout
        self._open_checkout_url(checkout.checkout_url)

    def _open_checkout_url(self, checkout_url: str) -> None:
        url = QUrl(checkout_url)
        if not url.isValid() or url.scheme().lower() != "https" or not url.host():
            self._retry_operation = "create"
            self._show_error(None, "Checkout returned an invalid secure URL.")
            return

        self._pending_checkout_url = checkout_url
        if not QDesktopServices.openUrl(url):
            self._retry_operation = "open_browser"
            self._show_error(None, "Could not open checkout in your default browser.")
            return

        self._pending_checkout_url = None
        self._show_payment_status(CheckoutStatus.PENDING)
        self._start_status_monitor()

    def _start_status_monitor(self) -> None:
        quote = self._order_state.quote
        if quote is None or self._active_checkout is None:
            return

        self._status_monitor.start(quote.quote_id)

    def _on_status_received(self, checkout_status: CheckoutStatusResponse) -> None:
        if self._closed:
            return

        self._order_state.set_checkout_status(checkout_status)
        self.paymentRefreshWarningLabel.clear()
        self.paymentRefreshWarningLabel.hide()

        status = checkout_status.status
        if status == CheckoutStatus.NOT_STARTED:
            status = CheckoutStatus.PENDING

        self._show_payment_status(status, checkout_status.public_order_id)

    def _on_recoverable_error(self, error: HttpResponseError) -> None:
        if self._closed or self.checkoutStackedWidget.currentWidget() != self.checkoutStatusPage:
            return

        self.paymentRefreshWarningLabel.setText(error.message)
        self.paymentRefreshWarningLabel.show()

    def _on_fatal_error(self, error: HttpResponseError) -> None:
        if self._closed:
            return

        self._show_error(error, "Could not refresh payment status.", False)

    def _show_payment_status(
        self,
        status: CheckoutStatus,
        public_order_id: str | None = None,
    ) -> None:
        content = {
            CheckoutStatus.PENDING: (
                "...",
                "Waiting for payment confirmation",
                "Complete payment in your browser. AtlasPress will update automatically.",
            ),
            CheckoutStatus.SUCCEEDED: (
                "✓",
                "Payment successful",
                "Your payment was confirmed and your order was created.",
            ),
            CheckoutStatus.CANCELLED: (
                "X",
                "Payment cancelled",
                "No payment was completed. You can close this window.",
            ),
            CheckoutStatus.FAILED: (
                "!",
                "Payment failed",
                "The payment could not be completed. You can start a new checkout.",
            ),
            CheckoutStatus.EXPIRED: (
                "!",
                "Quote expired",
                "Close this window and start a new AtlasPress order to request another quote.",
            ),
        }
        icon, title, message = content.get(
            status,
            ("...", "Checking payment status", "AtlasPress is checking your payment."),
        )

        self._spinner.stop()
        self._payment_status = status
        self.paymentStatusIconLabel.setText(icon)
        self.paymentStatusTitleLabel.setText(title)
        self.paymentStatusMessageLabel.setText(message)
        self.publicOrderIdLabel.setText(f"Order ID: {public_order_id}" if public_order_id else "")
        self.publicOrderIdLabel.setVisible(bool(public_order_id))
        self.paymentRefreshWarningLabel.clear()
        self.paymentRefreshWarningLabel.hide()
        self.checkoutStackedWidget.setCurrentWidget(self.checkoutStatusPage)

        if status == CheckoutStatus.FAILED:
            self._retry_operation = "create"
            self._set_action("Try Payment Again", True)
        else:
            self._set_action("Retry", False)

        self._set_close_enabled(True)

    def _show_loading(self, message: str) -> None:
        self._spinner.start()
        self.checkoutLoadingTextLabel.setText(message)
        self.checkoutStackedWidget.setCurrentWidget(self.checkoutLoadingPage)
        self._set_action("Retry", False)
        self._set_close_enabled(False)

    def _show_error(
        self,
        error: HttpResponseError | None,
        fallback_message: str,
        retry_enabled: bool = True,
    ) -> None:
        self._spinner.stop()
        self.checkoutErrorTitleLabel.setText(error.message if error else fallback_message)
        detail_messages = [detail.message for detail in error.details] if error else []
        self.checkoutErrorDetailsLabel.setText(
            "\n".join(f"• {message}" for message in detail_messages)
        )
        self.checkoutErrorDetailsLabel.setVisible(bool(detail_messages))
        self.checkoutErrorMessageLabel.setText(
            "Review the details and try again."
            if retry_enabled
            else "Close this window and restart the AtlasPress order flow."
        )
        self.checkoutStackedWidget.setCurrentWidget(self.checkoutErrorPage)
        self._set_action("Retry", retry_enabled)
        self._set_close_enabled(True)

    def _retry(self) -> None:
        if self._retry_operation == "open_browser" and self._pending_checkout_url:
            self._open_checkout_url(self._pending_checkout_url)
            return

        self._request_checkout()

    def _set_action(self, text: str, visible: bool) -> None:
        if self._action_button is not None:
            self._action_button.setText(text)
            self._action_button.setVisible(visible)
            self._action_button.setEnabled(visible)

    def _set_close_enabled(self, enabled: bool) -> None:
        if self._close_button is not None:
            self._close_button.setEnabled(enabled)

    def _confirm_pending_close(self) -> bool:
        if self._payment_status != CheckoutStatus.PENDING:
            return True

        message_box = QMessageBox(self)
        message_box.setIcon(QMessageBox.Icon.Warning)
        message_box.setWindowTitle("Close payment status?")
        message_box.setText("AtlasPress will stop checking the payment status.")
        message_box.setInformativeText(
            "Your Stripe checkout session will remain open. To cancel payment, "
            "use the cancellation option in the Stripe checkout page."
        )
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Close | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return message_box.exec() == QMessageBox.StandardButton.Close

    def reject(self) -> None:
        if not self._confirm_pending_close():
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_pending_close():
            event.ignore()
            return

        self._stop_background_work()
        event.accept()

    def done(self, result: int) -> None:
        self._stop_background_work()
        super().done(result)

    def _stop_background_work(self) -> None:
        self._closed = True
        self._status_monitor.stop()
        if self._checkout_task is not None:
            self._checkout_task.cancel()
            self._checkout_task = None
