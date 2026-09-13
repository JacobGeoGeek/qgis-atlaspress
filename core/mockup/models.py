from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from ..config.model.http_response import HttpResponseError


class MockupStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class MockupResponse:
    mockup_id: str
    status: MockupStatus
    preview_url: str | None
    preview_expires_at: datetime | None
    next_poll_at: datetime | None
    error_code: str | None
    error_message: str | None
    retryable: bool

    @classmethod
    def from_json(cls, data: dict) -> "MockupResponse":
        if not isinstance(data, dict):
            raise ValueError("Expected a preview object")

        mockup_id = data.get("mockupId")

        if not isinstance(mockup_id, str):
            raise ValueError("Missing mockup ID")

        UUID(mockup_id)
        status = MockupStatus(data.get("status"))
        retryable = data.get("retryable")

        if not isinstance(retryable, bool):
            raise ValueError("Missing retry eligibility")

        for key in ("previewUrl", "errorCode", "errorMessage"):
            if data.get(key) is not None and not isinstance(data[key], str):
                raise ValueError(f"Invalid {key}")

        if status == MockupStatus.READY and not data.get("previewUrl"):
            raise ValueError("Ready preview has no URL")

        return cls(
            mockup_id,
            status,
            data.get("previewUrl"),
            cls._date(data.get("previewExpiresAt")),
            cls._date(data.get("nextPollAt")),
            data.get("errorCode"),
            data.get("errorMessage"),
            retryable,
        )

    @staticmethod
    def _date(value: str | None) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Invalid preview timestamp")

        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if parsed.tzinfo is None:
            raise ValueError("Preview timestamp requires a timezone")

        return parsed

    def poll_delay_ms(self) -> int:
        if self.next_poll_at is None:
            return 10000

        delay = (self.next_poll_at - datetime.now(timezone.utc)).total_seconds() * 1000

        return max(1000, min(2147483647, int(delay)))


@dataclass(frozen=True)
class MockupResponseResult:
    mockup: MockupResponse | None
    error: HttpResponseError | None
