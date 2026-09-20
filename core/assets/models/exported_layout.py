from dataclasses import dataclass

from .metadata_asset import MetadataAssetRequest


@dataclass(frozen=True)
class ExportedLayout:
    content: bytes
    metadata: MetadataAssetRequest
