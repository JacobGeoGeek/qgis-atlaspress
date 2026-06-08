from qgis.core import QgsMessageLog
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from qgis.PyQt.QtWidgets import QFrame, QLabel, QVBoxLayout

from ...core.product.models.product import Product


class SizeCard(QFrame):
    """A single clickable size card with a product image, dimension, and price."""

    def __init__(
        self,
        product: Product,
        on_card_selected: callable,
        parent=None,
    ):
        super().__init__(parent)
        self._product = product
        self._on_card_selected = on_card_selected
        self._network_manager = QNetworkAccessManager(self)

        self.setFixedSize(96, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.Box)
        self._apply_style(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 7)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Mockup image
        self.imageLabel = QLabel()
        self.imageLabel.setFixedSize(72, 72)
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.imageLabel.setScaledContents(False)
        layout.addWidget(self.imageLabel, alignment=Qt.AlignmentFlag.AlignCenter)

        # Dimension label
        self.dimLabel = QLabel(f'{self._product.width_in}" x {self._product.height_in}"')
        self.dimLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.dimLabel.setStyleSheet("font-weight: bold; font-size: 11px; color: #333333;")
        layout.addWidget(self.dimLabel)

        # Price label
        self.priceLabel = QLabel(f"${self._product.retail_price:.2f}")
        self.priceLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.priceLabel.setStyleSheet("font-size: 10px; color: #3a7ebf;")
        layout.addWidget(self.priceLabel)

        # Load image (swap for a real network fetch against your Supabase URL)
        self._load_image(self._product.preview_thumbnail_url)

    def display_product_info(self):
        return f'{self._product.width_in}" x {self._product.height_in}" - ${self._product.retail_price:.2f}'

    @property
    def product(self) -> Product:
        return self._product

    def _load_image(self, url: str):
        """Load image from a local path or remote URL into imageLabel."""
        if not url:
            self._show_image_placeholder()
            return

        image_url = QUrl(url)

        if not image_url.isValid() or image_url.scheme() == "":
            self._show_image_placeholder()
            return

        request = QNetworkRequest(image_url)

        reply = self._network_manager.get(request)
        reply.finished.connect(lambda: self._on_image_loaded(reply))

    def _on_image_loaded(self, reply: QNetworkReply) -> None:
        """Handle the image data once loaded from a remote URL."""
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QgsMessageLog.logMessage(
                f"Failed to load image: {reply.errorString()}", level=QgsMessageLog.Level.Warning
            )
        else:
            pixmap = QPixmap()
            pixmap.loadFromData(reply.readAll())
            if not pixmap.isNull():
                self.imageLabel.setPixmap(
                    pixmap.scaled(
                        72,
                        72,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        reply.deleteLater()

    def _apply_style(self, active: bool):
        if active:
            self.setStyleSheet("""
                SizeCard {
                    border: 2px solid #3a7ebf;
                    border-radius: 8px;
                    background: #eef5fc;
                }
            """)
        else:
            self.setStyleSheet("""
                SizeCard {
                    border: 1px solid #d0d0d0;
                    border-radius: 8px;
                    background: #ffffff;
                }
                SizeCard:hover {
                    border: 1px solid #3a7ebf;
                    background: #f5f9ff;
                }
            """)

    def _show_image_placeholder(self):
        self.imageLabel.setText("No\nimage")
        self.imageLabel.setStyleSheet(
            "color: #999999; font-size: 10px; border: 1px dashed #dddddd;"
        )

    def set_active(self, active: bool):
        self._active = active
        self._apply_style(active)

    def mousePressEvent(self, event):
        if self._on_card_selected:
            self._on_card_selected(self)
        super().mousePressEvent(event)
