from dataclasses import dataclass

from ...config.model.http_response import HttpResponseError


@dataclass
class UploadCompleteResponse:
    asset_id: str
    message: str
    error: HttpResponseError | None
