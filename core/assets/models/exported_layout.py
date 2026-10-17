from dataclasses import dataclass

from .metadata_asset import MetadataAssetRequest


@dataclass(frozen=True)
class ExportedLayout:
    """Private lossless snapshot; metadata is finalized after JPEG preparation."""

    content: bytes
    metadata: MetadataAssetRequest
