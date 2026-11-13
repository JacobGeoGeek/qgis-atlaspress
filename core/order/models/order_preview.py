from dataclasses import dataclass
from datetime import datetime

from ._parsing import parse_date


@dataclass(frozen=True, repr=False)
class OrderPreview:
    url: str
    expires_at: datetime

    @classmethod
    def from_json(cls, data):
        if not isinstance(data["previewUrl"], str) or not data["previewUrl"]:
            raise ValueError("Missing preview URL.")
        return cls(
            data["previewUrl"],
            parse_date(data["previewExpiresAt"]),
        )
