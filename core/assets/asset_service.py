from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final
from urllib.parse import urlsplit

from qgis.core import (
    Qgis,
    QgsLayout,
    QgsLayoutExporter,
    QgsMessageLog,
)
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtGui import QImage

from .models.metadata_asset import MetadataAssetRequest, MetadataAssetResponse
from .asset_repository import AssetRepository


class AssetService:
    def __init__(self, asset_repository: AssetRepository):
        self._asset_repository: Final[AssetRepository] = asset_repository

    def upload_layout_file(self, designer: QgsLayoutDesignerInterface) -> str:
        layout: Final[QgsLayout] = designer.layout()
        file_name: Final[str] = designer.masterLayout().name()

        dpi: Final[float] = (
            layout.renderContext().dpi() if layout.renderContext().dpi() > 0 else 300
        )

        exporter: Final[QgsLayoutExporter] = QgsLayoutExporter(layout)

        settings: Final[QgsLayoutExporter.ImageExportSettings] = (
            QgsLayoutExporter.ImageExportSettings()
        )
        settings.dpi = dpi

        with TemporaryDirectory() as temp_dir:
            temp_file_path = f"{temp_dir}/{file_name}.png"
            result: Final[QgsLayoutExporter.ExportResult] = exporter.exportToImage(
                temp_file_path, settings
            )

            if result != QgsLayoutExporter.Success:
                QgsMessageLog.logMessage(
                    f"Failed to export layout to image: {result}",
                    "AtlasPress",
                    level=Qgis.Critical,
                )

                raise Exception(
                    "An error has occurred during the export map layout process. Please try again."
                )

            image: Final[QImage] = QImage(temp_file_path)
            width_px: Final[int] = image.width()
            height_px: Final[int] = image.height()
            file_bytes: Final[bytes] = Path(temp_file_path).read_bytes()
            size_bytes: Final[int] = len(file_bytes)

            if size_bytes == 0 or size_bytes > (50 * 1024 * 1024):
                raise Exception(
                    "The layout file size must not exceed 50MB. Please simplify your layout and try again."
                )

            metadata_asset: Final[MetadataAssetRequest] = MetadataAssetRequest(
                filename=f"{file_name.strip().replace(' ', '_')}.png",
                content_type="image/png",
                width_px=width_px,
                height_px=height_px,
                size_bytes=size_bytes,
                dpi=dpi,
            )

            metadata_response: Final[MetadataAssetResponse] = (
                self._asset_repository.create_metadata_asset(metadata_asset)
            )

            if metadata_response.error:
                QgsMessageLog.logMessage(
                    f"Failed to create metadata asset: {metadata_response.error.message}",
                    "AtlasPress",
                    level=Qgis.Critical,
                )
                raise Exception(
                    "An error has occurred while preparing the file for upload. Please try again."
                )

            if not metadata_response.is_signed_upload_url_valid():
                QgsMessageLog.logMessage(
                    f"Received invalid signed upload URL: {metadata_response.signed_upload_url}",
                    "AtlasPress",
                    level=Qgis.Critical,
                )
                raise Exception(
                    "An error has occurred while preparing the file for upload. Please try again."
                )

            url_parts = urlsplit(metadata_response.signed_upload_url)

            file_uploaded = self._asset_repository.upload_file(
                file=file_bytes, upload_url=f"{url_parts.path}?{url_parts.query}"
            )

            if file_uploaded.error:
                QgsMessageLog.logMessage(
                    f"Failed to upload file: {file_uploaded.error.message}",
                    "AtlasPress",
                    level=Qgis.Critical,
                )
                raise Exception("An error has occurred during file upload. Please try again.")

            if not metadata_response.asset_id:
                QgsMessageLog.logMessage(
                    "Upload completed but no asset ID was returned.",
                    "AtlasPress",
                    level=Qgis.Critical,
                )
                raise Exception("An error has occurred during file upload. Please try again.")

            complete_response = self._asset_repository.complete_upload(metadata_response.asset_id)

            if complete_response.error:
                QgsMessageLog.logMessage(
                    f"Failed to complete upload: {complete_response.error.message}",
                    "AtlasPress",
                    level=Qgis.Critical,
                )
                raise Exception(
                    "An error has occurred while finalizing the upload. Please try again."
                )

            return complete_response.asset_id
