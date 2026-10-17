"""Run with QGIS's Python: python -m unittest discover -s tests -v."""

import struct
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, call, patch

from qgis.PyQt import QtGui
from qgis.PyQt.QtCore import QBuffer, QIODevice

from core.assets import image_normalization as normalization
from core.assets.asset_repository import AssetRepository
from core.assets.asset_service import AssetService
from core.assets.models.exported_layout import ExportedLayout
from core.assets.models.metadata_asset import MetadataAssetRequest


def snapshot_bytes(image):
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise AssertionError("Could not save lossless test snapshot")
    return bytes(buffer.data())


def jpeg_segments(content):
    """Read JPEG header markers up to the compressed scan."""
    if content[:2] != b"\xff\xd8":
        raise AssertionError("Not JPEG bytes")
    offset = 2
    segments = []
    while offset < len(content):
        if content[offset] != 255:
            raise AssertionError("Invalid JPEG header")
        marker = content[offset + 1]
        length = struct.unpack_from(">H", content, offset + 2)[0]
        segments.append((marker, content[offset + 4 : offset + 2 + length]))
        if marker == 0xDA:
            break
        offset += length + 2
    return segments


class ImageNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.image = QtGui.QImage(32, 24, QtGui.QImage.Format.Format_RGBA8888)
        self.image.fill(QtGui.QColor(160, 90, 40, 96))
        self.image.setDotsPerMeterX(round(300 / 0.0254))
        self.image.setDotsPerMeterY(round(300 / 0.0254))
        self.srgb = QtGui.QColorSpace(QtGui.QColorSpace.NamedColorSpace.SRgb)

    def normalize(self, content=None, dpi=300):
        return normalization.normalize_print_image(
            snapshot_bytes(self.image) if content is None else content,
            32,
            24,
            dpi,
            qgis_rgb=True,
        )

    def assert_properties(self, content, dpi=300):
        segments = jpeg_segments(content)
        self.assertIn(0xC0, [marker for marker, _ in segments])
        self.assertNotIn(0xC2, [marker for marker, _ in segments])
        self.assertTrue(
            any(marker == 0xE2 and data.startswith(b"ICC_PROFILE\0") for marker, data in segments)
        )
        self.assertNotIn(0xFE, [marker for marker, _ in segments])
        saved = QtGui.QImage.fromData(content, "JPEG")
        self.assertFalse(saved.isNull())
        self.assertEqual((saved.width(), saved.height()), (32, 24))
        self.assertAlmostEqual(saved.dotsPerMeterX() * 0.0254, dpi, delta=0.51)
        self.assertAlmostEqual(saved.dotsPerMeterY() * 0.0254, dpi, delta=0.51)
        self.assertTrue(saved.colorSpace().isValid())
        self.assertEqual(saved.colorSpace(), self.srgb)
        self.assertFalse(saved.hasAlphaChannel())
        self.assertEqual(saved.textKeys(), [])
        return saved

    def assert_color_close(self, actual, expected):
        for channel in ("red", "green", "blue"):
            self.assertAlmostEqual(
                getattr(actual, channel)(), getattr(expected, channel)(), delta=3
            )

    def test_untagged_qgis_rgb_becomes_baseline_srgb_jpeg(self):
        self.image.fill(QtGui.QColor(160, 90, 40))
        content = snapshot_bytes(self.image)
        saved = self.assert_properties(self.normalize(content))
        self.assert_color_close(saved.pixelColor(10, 10), self.image.pixelColor(10, 10))
        self.assertFalse(QtGui.QImage.fromData(content).colorSpace().isValid())

    def test_unknown_untagged_input_is_rejected(self):
        with self.assertRaisesRegex(normalization.ImageNormalizationError, "no known"):
            normalization.normalize_print_image(snapshot_bytes(self.image), 32, 24, 300)

    def test_existing_srgb(self):
        self.image.fill(QtGui.QColor(160, 90, 40))
        self.image.setColorSpace(self.srgb)
        saved = self.assert_properties(self.normalize())
        self.assert_color_close(saved.pixelColor(10, 10), self.image.pixelColor(10, 10))

    def test_adobe_rgb_is_converted_before_encoding(self):
        self.image.fill(QtGui.QColor(160, 90, 40))
        self.image.setColorSpace(QtGui.QColorSpace(QtGui.QColorSpace.NamedColorSpace.AdobeRgb))
        expected = self.image.convertedToColorSpace(self.srgb)
        saved = self.assert_properties(self.normalize())
        self.assert_color_close(saved.pixelColor(10, 10), expected.pixelColor(10, 10))
        self.assertNotEqual(saved.pixelColor(10, 10), self.image.pixelColor(10, 10))

    def test_transparent_pixels_are_white(self):
        self.image.fill(QtGui.QColor(10, 20, 30, 0))
        saved = self.assert_properties(self.normalize())
        self.assertEqual(saved.pixelColor(10, 10), QtGui.QColor("white"))

    def test_partial_alpha_is_composited_onto_white(self):
        saved = self.assert_properties(self.normalize())
        expected = QtGui.QColor(*(round(value * 96 / 255 + 255 - 96) for value in (160, 90, 40)))
        self.assert_color_close(saved.pixelColor(10, 10), expected)

    def test_inherited_qgis_text_is_omitted(self):
        self.image.setText("Author", "QGIS project author")
        self.image.setText("Description", "QGIS layout details")
        content = self.normalize()
        self.assert_properties(content)
        self.assertNotIn(b"QGIS project author", content)
        self.assertNotIn(b"QGIS layout details", content)

    def test_other_dpi_is_preserved(self):
        self.image.setDotsPerMeterX(round(240 / 0.0254))
        self.image.setDotsPerMeterY(round(240 / 0.0254))
        self.assert_properties(self.normalize(dpi=240), dpi=240)

    def test_invalid_source_dimensions_or_dpi_fail(self):
        for content, width, dpi in (
            (b"invalid", 32, 300),
            (snapshot_bytes(self.image), 99, 300),
            (snapshot_bytes(self.image), 32, 72),
        ):
            with self.subTest(width=width, dpi=dpi):
                with self.assertRaises(normalization.ImageNormalizationError):
                    normalization.normalize_print_image(content, width, 24, dpi, qgis_rgb=True)

    def test_quality_95_and_baseline_writer_options(self):
        real_write = QtGui.QImageWriter.write

        def inspect_write(writer, image):
            self.assertEqual(writer.quality(), 95)
            self.assertFalse(writer.progressiveScanWrite())
            self.assertEqual(Path(writer.fileName()).suffix, ".jpg")
            return real_write(writer, image)

        with patch.object(QtGui.QImageWriter, "write", inspect_write):
            self.assert_properties(self.normalize())

    def test_save_failure_cleans_up_without_png_fallback(self):
        with TemporaryDirectory() as parent:
            with patch.object(
                normalization, "TemporaryDirectory", return_value=TemporaryDirectory(dir=parent)
            ):
                with patch.object(QtGui.QImageWriter, "write", return_value=False) as write:
                    with self.assertRaisesRegex(normalization.ImageNormalizationError, "save"):
                        self.normalize()
                    write.assert_called_once()
            self.assertEqual(list(Path(parent).iterdir()), [])

    def test_saved_file_validation_failures(self):
        real_write = QtGui.QImageWriter.write
        for failure in ("unreadable", "dimensions", "dpi", "profile", "png", "text"):
            with self.subTest(failure=failure):

                def write_invalid(writer, image):
                    if failure == "unreadable":
                        Path(writer.fileName()).write_bytes(b"invalid")
                        return True
                    saved = image.copy()
                    if failure == "dimensions":
                        saved = saved.scaled(16, 12)
                    elif failure == "dpi":
                        saved.setDotsPerMeterX(1000)
                    elif failure == "profile":
                        saved.setColorSpace(QtGui.QColorSpace())
                    elif failure == "png":
                        writer.setFormat(b"PNG")
                    elif failure == "text":
                        saved.setText("Author", "should not be present")
                    return real_write(writer, saved)

                with patch.object(QtGui.QImageWriter, "write", write_invalid):
                    with self.assertRaises(normalization.ImageNormalizationError):
                        self.normalize()

    def test_missing_color_space_or_failed_conversion(self):
        with patch.object(QtGui, "QColorSpace", None):
            with self.assertRaisesRegex(normalization.ImageNormalizationError, "update QGIS"):
                self.normalize()
        self.image.setColorSpace(QtGui.QColorSpace(QtGui.QColorSpace.NamedColorSpace.AdobeRgb))
        with patch.object(QtGui.QImage, "convertToColorSpace", return_value=None):
            with self.assertRaisesRegex(normalization.ImageNormalizationError, "convert"):
                self.normalize()

    def test_upload_http_flow_uses_final_jpeg_metadata_and_bytes(self):
        content = snapshot_bytes(self.image)
        exported = ExportedLayout(
            content, MetadataAssetRequest("map.jpg", "image/jpeg", len(content), 32, 24, 300)
        )
        client = Mock()
        created = Mock()
        created.content_json.return_value = {
            "assetId": "asset-id",
            "signedUploadUrl": "https://storage.test/upload?token=x",
        }
        completed = Mock()
        completed.content_json.return_value = {"message": "completed"}
        client.post.side_effect = [created, completed]
        client.put.return_value.content_json.return_value = {"Key": "map.jpg"}
        self.assertEqual(AssetService(AssetRepository(client)).upload_export(exported), "asset-id")
        uploaded = client.put.call_args.kwargs["data"]
        self.assert_properties(uploaded)
        payload = client.post.call_args_list[0].kwargs["payload"]
        self.assertIsInstance(payload["dpi"], int)
        self.assertEqual(
            payload,
            {
                "filename": "map.jpg",
                "contentType": "image/jpeg",
                "sizeBytes": len(uploaded),
                "widthPx": 32,
                "heightPx": 24,
                "dpi": 300,
            },
        )
        self.assertEqual(
            client.method_calls,
            [
                call.post(endpoint="/functions/v1/assets", payload=payload),
                call.put(
                    endpoint="https://storage.test/upload?token=x",
                    data=uploaded,
                    use_auth=False,
                    content_type="image/jpeg",
                ),
                call.post(endpoint="/functions/v1/assets/asset-id/complete"),
            ],
        )
        self.assertEqual(exported.content, content)

    def test_preparation_failure_prevents_backend_requests(self):
        repository = Mock()
        exported = ExportedLayout(
            b"invalid", MetadataAssetRequest("map.jpg", "image/jpeg", 7, 32, 24, 300)
        )
        with self.assertRaises(normalization.ImageNormalizationError):
            AssetService(repository).upload_export(exported)
        repository.create_metadata_asset.assert_not_called()
        repository.upload_file.assert_not_called()

    def test_oversized_final_jpeg_is_rejected(self):
        oversized = b"x" * (50 * 1024 * 1024 + 1)
        with patch.object(normalization.Path, "read_bytes", return_value=oversized):
            with self.assertRaisesRegex(normalization.ImageNormalizationError, "50 MB"):
                self.normalize()

    def test_upload_failure_does_not_complete_asset(self):
        content = snapshot_bytes(self.image)
        exported = ExportedLayout(
            content, MetadataAssetRequest("map.jpg", "image/jpeg", len(content), 32, 24, 300)
        )
        repository = Mock()
        repository.create_metadata_asset.return_value = Mock(
            error=None, asset_id="asset-id", signed_upload_url="https://storage.test/upload"
        )
        repository.upload_file.return_value.error = Mock(message="Upload rejected")
        with self.assertRaisesRegex(ValueError, "Upload rejected"):
            AssetService(repository).upload_export(exported)
        repository.complete_upload.assert_not_called()

    def test_export_captures_qgis_snapshot_at_layout_dpi(self):
        designer = Mock()
        designer.masterLayout.return_value.name.return_value = "My Map"
        designer.layout.return_value.renderContext.return_value.dpi.return_value = 300
        with patch("core.assets.asset_service.QgsLayoutExporter") as exporter:
            exporter.return_value.renderPageToImage.return_value = self.image
            exported = AssetService(Mock()).export_layout(designer)
            exporter.return_value.renderPageToImage.assert_called_once()
        self.assertEqual(exported.metadata.filename, "My_Map.jpg")
        self.assertEqual(exported.metadata.content_type, "image/jpeg")
        self.assertEqual(exported.metadata.dpi, 300)
        self.assert_properties(self.normalize(exported.content))

    def test_qgis_render_failure_is_clear(self):
        designer = Mock()
        designer.masterLayout.return_value.name.return_value = "My Map"
        designer.layout.return_value.renderContext.return_value.dpi.return_value = 300
        with patch("core.assets.asset_service.QgsLayoutExporter") as exporter:
            exporter.return_value.renderPageToImage.return_value = QtGui.QImage()
            with self.assertRaisesRegex(ValueError, "Could not export"):
                AssetService(Mock()).export_layout(designer)

    def test_success_removes_temporary_artifact(self):
        with TemporaryDirectory() as parent:
            with patch.object(
                normalization, "TemporaryDirectory", return_value=TemporaryDirectory(dir=parent)
            ):
                self.assert_properties(self.normalize())
            self.assertEqual(list(Path(parent).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
