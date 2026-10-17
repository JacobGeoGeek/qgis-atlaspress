from math import isfinite
from pathlib import Path
from tempfile import TemporaryDirectory

from qgis.PyQt import QtGui


class ImageNormalizationError(ValueError):
    """The print asset could not be prepared safely for upload."""


def normalize_print_image(
    content: bytes, width: int, height: int, dpi: float, *, qgis_rgb: bool = False
) -> bytes:
    """Return a clean sRGB JPEG; only known QGIS RGB snapshots may be untagged."""
    color_space_class = getattr(QtGui, "QColorSpace", None)
    if color_space_class is None or not all(
        hasattr(QtGui.QImage, name) for name in ("colorSpace", "setColorSpace")
    ):
        raise ImageNormalizationError(
            "This Qt installation cannot prepare sRGB print images. Please update QGIS."
        )

    try:
        return _normalize_print_image(content, width, height, dpi, color_space_class, qgis_rgb)
    except ImageNormalizationError:
        raise
    except Exception as error:
        raise ImageNormalizationError(
            "Could not normalize the map image for printing. Please retry map preparation."
        ) from error


def _normalize_print_image(content, width, height, dpi, color_space_class, qgis_rgb) -> bytes:
    image = QtGui.QImage.fromData(content, "PNG")
    if image.isNull():
        raise ImageNormalizationError("Could not read the exported map image.")
    if image.width() != width or image.height() != height:
        raise ImageNormalizationError("The exported map dimensions do not match its metadata.")
    if not isfinite(dpi) or dpi <= 0:
        raise ImageNormalizationError("The exported map has invalid DPI metadata.")

    dots_per_meter = (image.dotsPerMeterX(), image.dotsPerMeterY())
    if any(abs(value * 0.0254 - dpi) > 0.1 for value in dots_per_meter):
        raise ImageNormalizationError("The exported map DPI does not match its metadata.")

    named_spaces = getattr(color_space_class, "NamedColorSpace", color_space_class)
    srgb = color_space_class(named_spaces.SRgb)
    source_space = image.colorSpace()
    if not source_space.isValid():
        if not qgis_rgb:
            raise ImageNormalizationError("The map image has no known RGB color profile.")
        image.setColorSpace(srgb)
    elif source_space != srgb:
        if hasattr(image, "convertToColorSpace"):
            image.convertToColorSpace(srgb)
        elif hasattr(image, "convertedToColorSpace"):
            image = image.convertedToColorSpace(srgb)
        else:
            raise ImageNormalizationError(
                "This Qt installation cannot convert print colors to sRGB. Please update QGIS."
            )

    if image.isNull() or not image.colorSpace().isValid() or image.colorSpace() != srgb:
        raise ImageNormalizationError("Could not convert the map image to sRGB.")

    # A new RGB image drops inherited QGIS text metadata and composites alpha on white.
    flattened = QtGui.QImage(width, height, QtGui.QImage.Format.Format_RGB888)
    if flattened.isNull():
        raise ImageNormalizationError("Could not prepare the JPEG map image.")
    flattened.fill(QtGui.QColor("white"))
    flattened.setColorSpace(srgb)
    painter = QtGui.QPainter(flattened)
    if not painter.isActive():
        raise ImageNormalizationError("Could not flatten the map image onto white.")
    try:
        painter.drawImage(0, 0, image)
    finally:
        painter.end()
    flattened.setDotsPerMeterX(dots_per_meter[0])
    flattened.setDotsPerMeterY(dots_per_meter[1])
    with TemporaryDirectory(prefix="atlaspress-print-") as directory:
        path = str(Path(directory) / "layout-srgb.jpg")
        writer = QtGui.QImageWriter(path, b"JPEG")
        writer.setQuality(95)
        writer.setProgressiveScanWrite(False)
        if not writer.write(flattened):
            raise ImageNormalizationError("Could not save the sRGB JPEG map image for upload.")

        reader = QtGui.QImageReader(path)
        if bytes(reader.format()).lower() not in (b"jpeg", b"jpg"):
            raise ImageNormalizationError("The saved map image is not a JPEG.")
        saved = reader.read()
        if saved.isNull():
            raise ImageNormalizationError("Could not read the saved sRGB map image.")
        if saved.width() != width or saved.height() != height:
            raise ImageNormalizationError("The saved sRGB map image dimensions changed.")
        if any(
            # JPEG's JFIF density stores whole DPI values.
            abs(value * 0.0254 - dpi) > 0.51
            for value in (saved.dotsPerMeterX(), saved.dotsPerMeterY())
        ):
            raise ImageNormalizationError("The saved sRGB map image DPI changed.")
        if not saved.colorSpace().isValid() or saved.colorSpace() != srgb:
            raise ImageNormalizationError("The saved map image does not contain an sRGB profile.")
        if saved.hasAlphaChannel() or saved.textKeys():
            raise ImageNormalizationError("The saved JPEG contains unexpected image metadata.")

        normalized = Path(path).read_bytes()
        if not normalized or len(normalized) > 50 * 1024 * 1024:
            raise ImageNormalizationError("The sRGB map image must be smaller than 50 MB.")
        return normalized
