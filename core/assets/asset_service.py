from dataclasses import replace
from pathlib import Path
from typing import Final

from qgis.core import QgsLayoutExporter
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtCore import QBuffer, QIODevice, QSize
from qgis.PyQt.QtGui import QImage

from .asset_repository import AssetRepository
from .image_normalization import normalize_print_image
from .models.exported_layout import ExportedLayout
from .models.metadata_asset import MetadataAssetRequest


class AssetService:
    def __init__(self, asset_repository: AssetRepository):
        self._asset_repository: Final[AssetRepository] = asset_repository

    def export_layout(self, designer: QgsLayoutDesignerInterface) -> ExportedLayout:
        """Capture the live layout on the GUI thread before network work."""
        layout = designer.layout()
        layout_name = designer.masterLayout().name().strip().replace(" ", "_")
        dpi = layout.renderContext().dpi() or 300
        image = QgsLayoutExporter(layout).renderPageToImage(0, QSize(), dpi)
        if image.isNull():
            raise ValueError("Could not export the map. Please try again.")

        # Keep the GUI-thread snapshot lossless until the upload task encodes JPEG once.
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not image.save(buffer, "PNG"):
            raise ValueError("Could not capture the map image. Please try again.")
        content = bytes(buffer.data())
        if not content or len(content) > 50 * 1024 * 1024:
            raise ValueError("The exported map must be a valid image smaller than 50 MB.")

        return ExportedLayout(
            content,
            MetadataAssetRequest(
                filename=f"{layout_name}.jpg",
                content_type="image/jpeg",
                width_px=image.width(),
                height_px=image.height(),
                size_bytes=len(content),
                dpi=dpi,
            ),
        )

    def upload_export(self, exported: ExportedLayout) -> str:
        content = normalize_print_image(
            exported.content,
            exported.metadata.width_px,
            exported.metadata.height_px,
            exported.metadata.dpi,
            qgis_rgb=True,
        )
        image = QImage.fromData(content, "JPEG")
        metadata = replace(
            exported.metadata,
            filename=f"{Path(exported.metadata.filename).stem}.jpg",
            content_type="image/jpeg",
            size_bytes=len(content),
            width_px=image.width(),
            height_px=image.height(),
            # Qt's integer dots/metre round-trip gives 299.9994 for 300 DPI.
            dpi=round(image.dotsPerMeterX() * 0.0254),
        )
        response = self._asset_repository.create_metadata_asset(metadata)

        if response.error:
            raise ValueError(response.error.message)
        if not response.is_signed_upload_url_valid() or not response.asset_id:
            raise ValueError("Could not prepare the map upload. Please try again.")

        uploaded = self._asset_repository.upload_file(
            file=content, upload_url=response.signed_upload_url
        )

        if uploaded.error:
            raise ValueError(uploaded.error.message)

        completed = self._asset_repository.complete_upload(response.asset_id)

        if completed.error:
            raise ValueError(completed.error.message)
        if not completed.asset_id:
            raise ValueError("Upload completed without an asset ID. Please try again.")

        return completed.asset_id
