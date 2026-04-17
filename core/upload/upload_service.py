from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final
from urllib.parse import urlsplit

from qgis.core import (
    Qgis,
    QgsLayout,
    QgsLayoutExporter,
    QgsLayoutItem,
    QgsLayoutItemPage,
    QgsMessageLog,
)
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtGui import QImage

from .models.metadata_asset import MetadataAssetRequest, MetadataAssetResponse
from .upload_repository import UploadRepository


class UploadService:
    def __init__(self, upload_repository: UploadRepository):
        self._upload_repository: Final[UploadRepository] = upload_repository

    def _validate_designer_layout(self, designer: QgsLayoutDesignerInterface) -> bool:
        layout: Final[QgsLayout] = designer.layout()

        if not layout:
            designer.messageBar().pushWarning("AtlasPress", "No layout found to export.")
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

    def upload_layout_file(self, designer: QgsLayoutDesignerInterface):
        if not self._validate_designer_layout(designer):
            return

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
                designer.messageBar().pushCritical(
                    "AtlasPress",
                    f"Failed to export layout to image: {result}",
                )
                return

            image: Final[QImage] = QImage(temp_file_path)
            width_px: Final[int] = image.width()
            height_px: Final[int] = image.height()
            file_bytes: Final[bytes] = Path(temp_file_path).read_bytes()
            size_bytes: Final[int] = len(file_bytes)

            metadata_asset: Final[MetadataAssetRequest] = MetadataAssetRequest(
                filename=f"{file_name.strip().replace(' ', '_')}.png",
                content_type="image/png",
                width_px=width_px,
                height_px=height_px,
                size_bytes=size_bytes,
                dpi=dpi,
            )

            try:
                metadata_response: Final[MetadataAssetResponse] = (
                    self._upload_repository.create_metadata_asset(metadata_asset)
                )

                if metadata_response.error:
                    designer.messageBar().pushCritical(
                        "AtlasPress",
                        f"Failed to create metadata asset: {metadata_response.error.message}",
                    )
                    return

                if not metadata_response.is_signed_upload_url_valid():
                    designer.messageBar().pushCritical(
                        "AtlasPress",
                        "Unexpected error: unable to upload file due to invalid upload URL.",
                    )
                    return

                url_parts = urlsplit(metadata_response.signed_upload_url)

                file_uploaded = self._upload_repository.upload_file(
                    file=file_bytes, upload_url=f"{url_parts.path}?{url_parts.query}"
                )

                if file_uploaded.error:
                    designer.messageBar().pushCritical(
                        "AtlasPress",
                        f"Failed to upload file: {file_uploaded.error.message}",
                    )
                    return

                designer.messageBar().pushSuccess(
                    "AtlasPress",
                    f"File uploaded successfully with key: {file_uploaded.key}",
                )

            except Exception as exc:
                QgsMessageLog.logMessage(
                    f"An unexpected error occurred during the upload process: {exc}",
                    "AtlasPress",
                    level=Qgis.Critical,
                )

                designer.messageBar().pushCritical(
                    "AtlasPress",
                    "An unexpected error occurred during the upload process",
                )
