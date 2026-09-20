from .errors import MockupRequestError
from .mockup_repository import MockupRepository
from .models import MockupResponse, MockupResponseResult


class MockupService:
    def __init__(self, repository: MockupRepository):
        self._repository = repository

    def create_mockup(self, asset_id: str, product_id: str) -> MockupResponse:
        result = self._repository.create_mockup_by_asset_and_product_ids(
            asset_id,
            product_id,
        )
        return self._require_response(result)

    def get_mockup(self, mockup_id: str) -> MockupResponse:
        result = self._repository.get_mockup_by_id(mockup_id)
        return self._require_response(result)

    def retry_mockup(self, mockup_id: str) -> MockupResponse:
        result = self._repository.retry_mockup_by_id(mockup_id)
        return self._require_response(result)

    def _require_response(self, result: MockupResponseResult) -> MockupResponse:
        if result.error:
            raise MockupRequestError(result.error)
        if result.mockup is None:
            raise ValueError("Preview response is empty.")
        return result.mockup
