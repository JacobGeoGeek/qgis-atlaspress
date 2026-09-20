from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final
from urllib.parse import urlsplit

from qgis.core import QgsLayoutExporter
from qgis.gui import QgsLayoutDesignerInterface
from qgis.PyQt.QtGui import QImage

from .asset_repository import AssetRepository
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
        settings = QgsLayoutExporter.ImageExportSettings()
        settings.dpi = dpi

        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "layout.png")
            result = QgsLayoutExporter(layout).exportToImage(path, settings)

            if result != QgsLayoutExporter.Success:
                raise ValueError("Could not export the map. Please try again.")

            image = QImage(path)
            content = Path(path).read_bytes()

            if image.isNull() or not content or len(content) > 50 * 1024 * 1024:
                raise ValueError("The exported map must be a valid image smaller than 50 MB.")

            return ExportedLayout(
                content,
                MetadataAssetRequest(
                    filename=f"{layout_name}.png",
                    content_type="image/png",
                    width_px=image.width(),
                    height_px=image.height(),
                    size_bytes=len(content),
                    dpi=dpi,
                ),
            )

    def upload_export(self, exported: ExportedLayout) -> str:
        response = self._asset_repository.create_metadata_asset(exported.metadata)

        if response.error:
            raise ValueError(response.error.message)
        if not response.is_signed_upload_url_valid() or not response.asset_id:
            raise ValueError("Could not prepare the map upload. Please try again.")

        url = urlsplit(response.signed_upload_url)
        uploaded = self._asset_repository.upload_file(
            file=exported.content, upload_url=f"{url.path}?{url.query}"
        )

        if uploaded.error:
            raise ValueError(uploaded.error.message)

        completed = self._asset_repository.complete_upload(response.asset_id)

        if completed.error:
            raise ValueError(completed.error.message)
        if not completed.asset_id:
            raise ValueError("Upload completed without an asset ID. Please try again.")

        return completed.asset_id
