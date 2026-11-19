from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import QGroupBox

from ...core.order.models import OrderShipment
from .order_shipment_widget_ui import Ui_OrderShipmentWidget


class OrderShipmentWidget(QGroupBox, Ui_OrderShipmentWidget):
    def __init__(self, shipment: OrderShipment, package_number: int, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setTitle(f"Package {package_number}")
        self.reshipmentLabel.setVisible(shipment.reshipment)
        self.carrierValueLabel.setText(shipment.carrier or "Not available")
        self.serviceValueLabel.setText(shipment.service or "Not available")
        self.trackingNumberValueLabel.setText(shipment.tracking_number or "Not available")
        self.shippedAtValueLabel.setText(
            shipment.shipped_at.astimezone().strftime("%b %d, %Y %H:%M %Z")
            if shipment.shipped_at
            else "Not available"
        )
        self._tracking_url = QUrl(shipment.tracking_url or "")
        usable = self._has_usable_tracking_url()
        self.trackPackageButton.setVisible(usable)
        self.trackingLinkUnavailableLabel.setVisible(not usable)
        self.browserErrorLabel.hide()
        self.trackPackageButton.clicked.connect(self._open_tracking_url)

    def _has_usable_tracking_url(self):
        return (
            self._tracking_url.isValid()
            and self._tracking_url.scheme() in ("http", "https")
            and bool(self._tracking_url.host())
            and not self._tracking_url.userInfo()
        )

    def _open_tracking_url(self):
        if self._has_usable_tracking_url():
            self.browserErrorLabel.setVisible(not QDesktopServices.openUrl(self._tracking_url))

    def clear_tracking(self):
        self._tracking_url = QUrl()
        for label in (
            self.carrierValueLabel,
            self.serviceValueLabel,
            self.trackingNumberValueLabel,
            self.shippedAtValueLabel,
        ):
            label.clear()
        self.browserErrorLabel.hide()
        self.setEnabled(False)
        self.hide()
