from qgis.core import QgsApplication
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtCore import QEvent, Qt, QTimer, QUrl
from qgis.PyQt.QtGui import QPainter, QPixmap
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from ...core.assets.asset_service import AssetService
from ...core.assets.tasks.upload_file_task import UploadFileTask
from ...core.mockup.mockup_preview_monitor import MockupPreviewMonitor
from ...core.mockup.mockup_service import MockupService
from ...core.mockup.models import MockupStatus
from ...core.product.models.product import ProductType
from ...core.product.product_service import ProductService
from ...core.product.tasks.fetch_products_by_type_task import FetchProductsByTypeTask
from ..common.spinner_widget import SpinnerWidget
from .product_selection_ui import Ui_AtlasPressProductSelectionDialog


class ProductDialog(QDialog, Ui_AtlasPressProductSelectionDialog):
    _ZOOM_STEP = 1.25
    _MIN_ZOOM = 0.5
    _MAX_ZOOM = 8.0

    def __init__(
        self,
        product_service: ProductService,
        asset_service: AssetService,
        mockup_service: MockupService,
        designer: QgsLayoutDesignerInterface,
        on_product_uploaded: callable,
        parent=None,
    ):
        super().__init__(parent)
        self.setupUi(self)
        self._product_service = product_service
        self._asset_service = asset_service
        self._designer = designer
        self._on_product_uploaded = on_product_uploaded

        self._asset_id = None
        self._exported = None
        self._selected_product = None
        self._initializing = True
        self._products_ready = False
        self._export_pending = False
        self._upload_task = None
        self._product_task = None
        self._generation = 0
        self._product_generation = 0
        self._image_reply = None
        self._pixmap = None
        self._zoom_factor = 1.0
        self._retry_image = False

        self._network = QNetworkAccessManager(self)

        self._monitor = MockupPreviewMonitor(mockup_service, self)
        self._monitor.updated.connect(self._on_preview)
        self._monitor.failed.connect(self._on_preview_error)

        self._products = []
        self._startup_spinner = SpinnerWidget()
        self._spinner = SpinnerWidget()

        self.startupSpinnerLabel.hide()
        self.startupLoadingLayout.insertWidget(
            1, self._startup_spinner, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self.previewLoadingSpinnerLabel.hide()
        self.previewLoadingLayout.insertWidget(
            1, self._spinner, alignment=Qt.AlignmentFlag.AlignCenter
        )
        self._preview_scene = QGraphicsScene(self)
        self._preview_item = QGraphicsPixmapItem()
        self._preview_item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)

        self._preview_scene.addItem(self._preview_item)

        self.previewGraphicsView.setScene(self._preview_scene)
        self.previewGraphicsView.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.previewGraphicsView.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.previewGraphicsView.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.previewGraphicsView.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.previewGraphicsView.viewport().installEventFilter(self)

        self.zoomOutButton.clicked.connect(lambda: self._change_zoom(1 / self._ZOOM_STEP))
        self.zoomFitButton.clicked.connect(self._reset_zoom)
        self.zoomInButton.clicked.connect(lambda: self._change_zoom(self._ZOOM_STEP))
        self._update_zoom_controls()

        self.mainSplitter.setStretchFactor(0, 2)
        self.mainSplitter.setStretchFactor(1, 1)
        self.mainSplitter.setSizes([440, 280])

        self.rootLayout.setStretch(3, 1)
        self.rootLayout.setStretch(4, 1)

        self.continueButton = self.actionButtonBox.button(QDialogButtonBox.StandardButton.Ok)
        self.continueButton.setText("Continue to Shipping")
        self.continueButton.setEnabled(False)

        self.actionButtonBox.accepted.disconnect(self.accept)
        self.continueButton.clicked.connect(self._continue)
        self.productLoadingRetryButton.hide()
        self.mapUploadGroupBox.hide()
        self.mapUploadRetryButton.hide()

        self.productComboBox.currentIndexChanged.connect(self._on_product_type_changed)
        self.sizeComboBox.currentIndexChanged.connect(self._on_size_changed)
        self.productLoadingRetryButton.clicked.connect(self._on_product_retry_clicked)
        self.mapUploadRetryButton.clicked.connect(self._prepare_map)
        self.previewRetryButton.clicked.connect(self._retry_preview)

        self._show_startup_loading("Preparing your order...")

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._resume)

    def _resume(self):
        if not self.isVisible():
            return
        if self._initializing:
            self._show_startup_loading("Preparing your order...")
        else:
            self._show_main_content()

        if self.sizeComboBox.count() <= 1 and self._product_task is None:
            self._load_products()

        if self._asset_id is None:
            self._prepare_map()
        elif self._selected_product is not None:
            self._start_preview()

    def hideEvent(self, event):
        self._generation += 1
        self._product_generation += 1
        self._export_pending = False
        self._monitor.stop()
        self._abort_image()
        self._startup_spinner.stop()
        self._spinner.stop()

        for task in (self._upload_task, self._product_task):
            if task is not None:
                task.cancel()

        self._upload_task = None
        self._product_task = None

        super().hideEvent(event)

    def _prepare_map(self):
        if (
            not self.isVisible()
            or self._export_pending
            or self._upload_task is not None
            or self._asset_id
        ):
            return

        self.mapUploadRetryButton.hide()
        self.mapUploadGroupBox.hide()
        self.mapUploadStatusLabel.setText("Preparing map...")

        if self._initializing:
            self._show_startup_loading("Preparing your map...")
        else:
            self._loading("Preparing your map...")

        self._update_continue()
        self._export_pending = True
        generation = self._generation

        QTimer.singleShot(0, lambda: self._export_and_upload(generation))

    def _export_and_upload(self, generation):
        if generation != self._generation:
            return

        self._export_pending = False

        if not self.isVisible() or self._asset_id is not None:
            return

        try:
            if self._exported is None:
                self._exported = self._asset_service.export_layout(self._designer)
        except Exception:
            self._initializing = False
            self._show_main_content()
            self.mapUploadGroupBox.show()
            self.mapUploadStatusLabel.setText(
                "Could not export the map. Please check the layout and retry."
            )
            self.mapUploadRetryButton.show()
            self._preview_error("Map preparation failed. Use Retry map preparation.", False)
            return

        self.mapUploadStatusLabel.setText("Uploading map...")

        if self._initializing:
            self._show_startup_loading("Uploading your map...")
        else:
            self._loading("Uploading your map...")

        self._upload_task = UploadFileTask(
            self._asset_service,
            self._exported,
            lambda result, asset_id, error: self._uploaded(generation, result, asset_id, error),
        )

        QgsApplication.taskManager().addTask(self._upload_task)

    def _uploaded(self, generation, result, asset_id, error):
        if generation != self._generation or not self.isVisible():
            return

        self._upload_task = None

        if not result or not asset_id:
            self._initializing = False

            self._show_main_content()

            self.mapUploadGroupBox.show()
            self.mapUploadStatusLabel.setText(error or "Could not upload the map.")
            self.mapUploadRetryButton.show()

            self._preview_error("Map upload failed. Use Retry map preparation.", False)

            return

        self._asset_id = asset_id
        self._exported = None

        self.mapUploadGroupBox.hide()
        self._update_continue()

        if self._initializing:
            self._finish_startup()
        else:
            self._start_preview()

    def _load_products(self):
        if self._product_task is not None:
            self._product_task.cancel()

        self._product_generation += 1
        generation = self._product_generation

        if self._initializing:
            self._products_ready = False

        self._clear_selection()

        self._products = []

        self.sizeComboBox.blockSignals(True)
        self.sizeComboBox.clear()
        self.sizeComboBox.addItem("Select a size")
        self.sizeComboBox.blockSignals(False)
        self.productLoadingStatusLabel.show()
        self.productLoadingStatusLabel.setText("Fetching sizes...")
        self.productLoadingRetryButton.hide()
        self.sizeComboBox.setEnabled(False)

        product_type = (
            ProductType.CANVAS if self.productComboBox.currentIndex() == 0 else ProductType.POSTER
        )

        self._product_task = FetchProductsByTypeTask(
            self._product_service,
            product_type,
            lambda result, products: self._products_loaded(generation, result, products),
        )

        QgsApplication.taskManager().addTask(self._product_task)

    def _on_product_type_changed(self, _index):
        self._load_products()

    def _on_product_retry_clicked(self, _checked=False):
        self._load_products()

    def _products_loaded(self, generation, result, products):
        if generation != self._product_generation or not self.isVisible():
            return

        self._product_task = None

        if not result or not products:
            self._initializing = False
            self._show_main_content()
            self.productLoadingStatusLabel.setText("No sizes available. Please try again.")
            self.productLoadingRetryButton.show()
            return

        self.productLoadingStatusLabel.hide()
        self._products = list(products)
        self.sizeComboBox.blockSignals(True)

        for product in self._products:
            self.sizeComboBox.addItem(f"{product.width_in} x {product.height_in} in")

        self.sizeComboBox.blockSignals(False)
        self.sizeComboBox.setEnabled(True)
        self._products_ready = True

        self._finish_startup()

    def _show_startup_loading(self, message):
        self.startupLoadingTextLabel.setText(message)
        self.mainSplitter.hide()
        self.startupLoadingPage.show()
        self._startup_spinner.start()

    def _show_main_content(self):
        self._startup_spinner.stop()
        self.startupLoadingPage.hide()
        self.mainSplitter.show()

    def _finish_startup(self):
        if not self._initializing or not self._asset_id or not self._products_ready:
            return

        self._initializing = False

        self._show_main_content()
        self._start_preview()

    def _on_size_changed(self, index):
        if index <= 0 or index > len(self._products):
            self._clear_selection()
            return

        self._select_product(self._products[index - 1])

    def _clear_selection(self):
        self._monitor.stop()
        self._abort_image()
        self._selected_product = None
        self._pixmap = None
        self._preview_item.setPixmap(QPixmap())
        self._preview_scene.setSceneRect(self._preview_item.boundingRect())
        self._zoom_factor = 1.0
        self._update_zoom_controls()
        self.productPriceValueLabel.setText("—")

        if self._asset_id is None and (self._export_pending or self._upload_task is not None):
            return

        self._spinner.stop()
        self.previewStackedWidget.setCurrentWidget(self.previewEmptyPage)

        self._update_continue()

    def _select_product(self, product):
        if self._selected_product is not None and self._selected_product.id == product.id:
            return

        self._selected_product = product
        self.productPriceValueLabel.setText(f"{product.currency} {product.retail_price:.2f}")
        self._pixmap = None
        self._preview_item.setPixmap(QPixmap())
        self._preview_scene.setSceneRect(self._preview_item.boundingRect())
        self._zoom_factor = 1.0

        self._update_zoom_controls()
        self._update_continue()
        self._start_preview()

    def _update_continue(self):
        self.continueButton.setEnabled(bool(self._asset_id and self._selected_product))

    def _continue(self):
        if self._asset_id and self._selected_product:
            product, asset_id = self._selected_product, self._asset_id

            self.accept()

            self._on_product_uploaded(product, asset_id)

    def _start_preview(self):
        self._abort_image()
        self._retry_image = False

        if self._asset_id is None:
            return

        if self._selected_product is None:
            self._spinner.stop()
            self.previewStackedWidget.setCurrentWidget(self.previewEmptyPage)
            return

        if self._pixmap is None:
            self._loading(
                "Generating your preview... You can select Continue to Shipping now."
            )

        self._monitor.start(self._asset_id, self._selected_product.id)

    def _loading(self, message):
        self.previewLoadingTextLabel.setText(message)
        self.previewStackedWidget.setCurrentWidget(self.previewLoadingPage)
        self._spinner.start()

    def _on_preview(self, response):
        if response.status == MockupStatus.PENDING:
            self._loading(
                "Generating your preview... You can select Continue to Shipping now."
            )
        elif response.status == MockupStatus.FAILED:
            self._preview_error(
                response.error_message or "Could not generate a preview.", response.retryable
            )
        else:
            self._download_image(response.preview_url)

    def _on_preview_error(self, error):
        message = "\n".join([error.message] + [f"- {detail.message}" for detail in error.details])
        self._preview_error(message, error.status_code not in (400, 401, 403, 409))

    def _preview_error(self, message, retryable):
        self._spinner.stop()
        self.previewErrorTextLabel.setText(
            f"{message}\nYou can continue without a preview once your map is uploaded."
        )

        self.previewRetryButton.setVisible(retryable)
        self.previewStackedWidget.setCurrentWidget(self.previewErrorPage)

    def _retry_preview(self):
        self._loading("Loading your preview...")

        if self._retry_image:
            self._retry_image = False
            self._monitor.refresh()
        else:
            self._monitor.retry()

    def _download_image(self, url):
        self._abort_image()
        image_url = QUrl(url)

        if not image_url.isValid() or not image_url.host():
            self._image_error()
            return

        self._loading("Loading product preview...")

        request = QNetworkRequest(image_url)
        request.setTransferTimeout(30000)
        reply = self._network.get(request)
        self._image_reply = reply
        reply.finished.connect(lambda: self._image_loaded(reply))

    def _abort_image(self):
        reply = self._image_reply
        self._image_reply = None

        if reply is not None:
            reply.abort()

    def _image_loaded(self, reply):
        if reply is not self._image_reply or not self.isVisible():
            reply.deleteLater()
            return

        self._image_reply = None
        pixmap = QPixmap()
        success = reply.error() == QNetworkReply.NetworkError.NoError and pixmap.loadFromData(
            reply.readAll()
        )

        reply.deleteLater()

        if not success:
            self._image_error()
            return

        self._pixmap = pixmap
        self._preview_item.setPixmap(pixmap)
        self._preview_scene.setSceneRect(self._preview_item.boundingRect())
        self._spinner.stop()
        self.previewStackedWidget.setCurrentWidget(self.previewContentPage)
        self._reset_zoom()

    def _image_error(self):
        self._retry_image = True
        self._preview_error("Could not download the preview image. Please retry.", True)

    def _reset_zoom(self):
        self._zoom_factor = 1.0
        self._fit_preview()

    def _fit_preview(self):
        if self._pixmap is None or self._pixmap.isNull():
            self._update_zoom_controls()
            return

        self.previewGraphicsView.resetTransform()
        self.previewGraphicsView.fitInView(
            self._preview_item,
            Qt.AspectRatioMode.KeepAspectRatio,
        )
        self.previewGraphicsView.scale(self._zoom_factor, self._zoom_factor)

        self._update_zoom_controls()

    def _change_zoom(self, multiplier):
        if self._pixmap is None or self._pixmap.isNull():
            return

        zoom_factor = min(
            self._MAX_ZOOM,
            max(self._MIN_ZOOM, self._zoom_factor * multiplier),
        )

        if zoom_factor == self._zoom_factor:
            return

        self.previewGraphicsView.scale(
            zoom_factor / self._zoom_factor,
            zoom_factor / self._zoom_factor,
        )
        self._zoom_factor = zoom_factor

        self._update_zoom_controls()

    def _toggle_zoom(self):
        if self._pixmap is None or self._pixmap.isNull():
            return
        if self._zoom_factor > 1.0:
            self._reset_zoom()
        else:
            self._change_zoom(2.0 / self._zoom_factor)

    def _update_zoom_controls(self):
        has_preview = self._pixmap is not None and not self._pixmap.isNull()

        self.zoomOutButton.setEnabled(has_preview and self._zoom_factor > self._MIN_ZOOM)
        self.zoomFitButton.setEnabled(has_preview)
        self.zoomInButton.setEnabled(has_preview and self._zoom_factor < self._MAX_ZOOM)

    def eventFilter(self, watched, event):
        if watched is self.previewGraphicsView.viewport():
            if event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._fit_preview)
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                self._toggle_zoom()
                event.accept()
                return True
            elif event.type() == QEvent.Type.Wheel and self._pixmap is not None:
                self._change_zoom(
                    self._ZOOM_STEP if event.angleDelta().y() > 0 else 1 / self._ZOOM_STEP
                )
                event.accept()
                return True
        return super().eventFilter(watched, event)
