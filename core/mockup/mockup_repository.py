from ..config.http_client import HttpClient
from ..config.model.http_response import HttpResponseError
from .models import MockupResponse, MockupResponseResult


class MockupRepository:
    def __init__(self, http_client: HttpClient):
        self._http_client = http_client

    def create_mockup_by_asset_and_product_ids(
        self,
        asset_id: str,
        product_id: str,
    ) -> MockupResponseResult:
        return self._parse_response(
            self._http_client.post(
                endpoint="/functions/v1/mockups",
                payload={"assetId": asset_id, "productId": product_id},
            )
        )

    def get_mockup_by_id(self, mockup_id: str) -> MockupResponseResult:
        return self._parse_response(
            self._http_client.get(endpoint=f"/functions/v1/mockups/{mockup_id}")
        )

    def retry_mockup_by_id(self, mockup_id: str) -> MockupResponseResult:
        return self._parse_response(
            self._http_client.post(endpoint=f"/functions/v1/mockups/{mockup_id}/retry")
        )

    def _parse_response(self, response) -> MockupResponseResult:
        if not response.is_success():
            return MockupResponseResult(None, HttpResponseError.from_response(response))

        try:
            return MockupResponseResult(MockupResponse.from_json(response.content_json()), None)
        except (ValueError, TypeError):
            return MockupResponseResult(
                None,
                HttpResponseError(
                    status_code=response.status_code() or 0,
                    message="The product preview response was not valid.",
                    details=[],
                ),
            )
