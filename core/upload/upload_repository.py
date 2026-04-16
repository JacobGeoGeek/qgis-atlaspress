from typing import Final

from ..config import HttpClient
from ..config.model import HttpResponse, HttpResponseError
from .models.metadata_asset import MetadataAssetRequest, MetadataAssetResponse
from .models.upload_file import UploadFileResponse


class UploadRepository:
    def __init__(self, http_client: HttpClient):
        self._http_client: Final[HttpClient] = http_client

    def create_metadata_asset(self, metadata_asset: MetadataAssetRequest) -> MetadataAssetResponse:
        response: Final[HttpResponse] = self._http_client.post(
            endpoint="/functions/v1/uploads", payload=metadata_asset.to_json()
        )

        if not response.is_success():
            error: Final[HttpResponseError] = HttpResponseError.from_response(response)
            return MetadataAssetResponse(
                asset_id="",
                storage_bucket="",
                storage_path="",
                signed_upload_url="",
                expired_at="",
                error=error,
            )

        data: Final[dict] = response.content_json() or {}
        return MetadataAssetResponse(
            asset_id=data.get("assetId", ""),
            storage_bucket=data.get("storageBucket", ""),
            storage_path=data.get("storagePath", ""),
            signed_upload_url=data.get("signedUploadUrl", ""),
            expired_at=data.get("expiredAt", ""),
            error=None,
        )

    def upload_file(self, file: bytes, upload_url: str) -> UploadFileResponse:
        response: Final[HttpResponse] = self._http_client.put(
            endpoint=upload_url,
            data=file,
            use_auth=False,
            content_type="image/png",
        )

        if not response.is_success():
            error: Final[HttpResponseError] = HttpResponseError.from_response(response)
            return UploadFileResponse(key="", error=error)

        data: Final[dict] = response.content_json() or {}
        return UploadFileResponse(key=data.get("Key", ""), error=None)
