from typing import Final

from qgis.core import Qgis, QgsApplication, QgsMessageLog
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QWidget

from ...core import (
    FetchProductsByTypeTask,
    ProductService,
    ProductType,
    UploadFileTask,
    UploadService,
)
from ..common.spinner_widget import SpinnerWidget
from .product_selection_ui import Ui_AtlassPressProductDialog
from .size_product_card import SizeCard


class ProductDialog(QDialog, Ui_AtlassPressProductDialog):
    def __init__(
        self,
        product_service: ProductService,
        upload_service: UploadService,
        designer: QgsLayoutDesignerInterface,
        parent=None,
    ):
        super().__init__(parent)
        self.setupUi(self)
        self._product_service = product_service
        self._upload_service = upload_service
        self._designer = designer
        self.radioCanvas.toggled.connect(self._on_product_type_changed)
        self.radioPoster.toggled.connect(self._on_product_type_changed)

        self._spinner = SpinnerWidget()
        self.loadingPageLayout.insertWidget(
            0, self._spinner, alignment=Qt.AlignmentFlag.AlignCenter
        )

        self._products_size_cards: Final[list[SizeCard]] = []
        self._selected_product: SizeCard | None = None
        self._ok_button = self.buttonsActions.button(QDialogButtonBox.StandardButton.Ok)
        self._set_ok_enabled(False)
        self.buttonsActions.accepted.disconnect(self.accept)
        self._ok_button.clicked.connect(self._upload_file)
        self.buttonsActions.rejected.connect(self.reject)
        self._on_product_type_changed()  # trigger initial load

    def _on_product_type_changed(self):
        if not self.radioCanvas.isChecked() and not self.radioPoster.isChecked():
            return

        product_type = ProductType.CANVAS if self.radioCanvas.isChecked() else ProductType.POSTER

        self.descriptionLabel.setText(
            (
                "Canvas prints are made using high-quality canvas material, "
                "providing a textured and artistic finish. "
                "They are ideal for showcasing artwork, photographs, and designs "
                "with a classic and elegant look."
            )
            if product_type == ProductType.CANVAS
            else (
                "Poster prints are produced on smooth, glossy paper, offering "
                "vibrant colors and sharp details. They are perfect for "
                "promotional materials, event posters, and any design that "
                "requires a bold and eye-catching presentation."
            )
        )

        self._show_loading_state()
        QgsApplication.taskManager().addTask(
            FetchProductsByTypeTask(self._product_service, product_type, self._on_project_loaded)
        )

    def _on_project_loaded(self, result, products):
        if result:
            self._populate_product_cards(products)

        self._hide_loading_state(self.sizeCardsPage if result else self.sizeErrorPage)

    def _on_file_uploaded(self, result, asset_id):
        if not result:
            self._hide_loading_state(self.sizeErrorPage)
            return

        QgsMessageLog.logMessage(
            f"Layout file uploaded successfully with asset ID: {asset_id}",
            "AtlasPress",
            level=Qgis.Info,
        )
        self._hide_loading_state(self.sizeCardsPage)

    def _populate_product_cards(self, products):
        self._clear_cards_layout()
        self._products_size_cards.clear()
        for product in products:
            self._products_size_cards.append(
                SizeCard(
                    product=product,
                    on_card_selected=self._on_product_selected,
                    parent=self,
                )
            )
            self.sizeCardsLayout.addWidget(self._products_size_cards[-1])

    def _show_loading_state(self, text: str = "Fetching products..."):
        self._spinner.start()
        self.radioCanvas.setEnabled(False)
        self.radioPoster.setEnabled(False)
        self._set_ok_enabled(False)
        self.loadingTextLabel.setText(text)
        self.sizeStackedWidget.setCurrentWidget(self.sizeLoadingPage)

    def _hide_loading_state(self, widget: QWidget):
        self._spinner.stop()
        self.radioCanvas.setEnabled(True)
        self.radioPoster.setEnabled(True)
        self.sizeStackedWidget.setCurrentWidget(widget)

    def _clear_cards_layout(self):
        for card in self._products_size_cards:
            self.sizeCardsLayout.removeWidget(card)
            card.setParent(None)
        self._products_size_cards.clear()
        self.selectionSizeLabel.setText("No size selected")
        self._selected_product = None
        self._set_ok_enabled(False)

    def _on_product_selected(self, card: SizeCard):
        if self._selected_product:
            self._selected_product._apply_style(False)
        card._apply_style(True)

        self._selected_product = card
        self.selectionSizeLabel.setText(card.display_product_info())
        self._set_ok_enabled(True)

    def _set_ok_enabled(self, enabled: bool):
        if self._ok_button is not None:
            self._ok_button.setEnabled(enabled)

    def _upload_file(self):
        if self._selected_product:
            self._show_loading_state("Uploading layout file...")
            QgsApplication.taskManager().addTask(
                UploadFileTask(
                    self._upload_service,
                    self._designer,
                    self._on_file_uploaded,
                )
            )
