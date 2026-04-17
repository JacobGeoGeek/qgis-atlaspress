from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError


@dataclass
class MetadataAssetRequest:
    filename: str
    content_type: str
    size_bytes: int
    width_px: int
    height_px: int
    dpi: float

    def to_json(self) -> dict:
        return {
            "filename": self.filename,
            "contentType": self.content_type,
            "sizeBytes": self.size_bytes,
            "widthPx": self.width_px,
            "heightPx": self.height_px,
            "dpi": self.dpi,
        }


@dataclass
class MetadataAssetResponse:
    asset_id: str | None
    storage_bucket: str | None
    storage_path: str | None
    signed_upload_url: str | None
    expired_at: str | None
    error: HttpResponseError | None

    def is_signed_upload_url_valid(self) -> bool:
        return self.signed_upload_url is not None and self.signed_upload_url != ""
