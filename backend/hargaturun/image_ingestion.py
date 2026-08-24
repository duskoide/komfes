"""Fail-closed validation and ephemeral normalization for user images.

Images are decoded before inference, normalized to a metadata-free PNG, and
kept only in a private temporary directory owned by the request. No URL is
retrieved: the API accepts bytes only.
"""

from __future__ import annotations

import base64
import binascii
import io
import ipaddress
import os
import re
import struct
import tempfile
import warnings
import zlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageFile, UnidentifiedImageError
from PIL.Image import DecompressionBombError, DecompressionBombWarning

ImageFile.LOAD_TRUNCATED_IMAGES = False

MAGIC_TYPES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}
SUPPORTED_TYPES = frozenset(MAGIC_TYPES)
_DATA_URI_RE = re.compile(r"^data:([^;,\s]+);base64,([A-Za-z0-9+/=\s]+)$", re.IGNORECASE)


class ImageIngestionError(ValueError):
    """A generic, client-safe image rejection."""


@dataclass(frozen=True)
class ImageLimits:
    max_bytes: int = 5 * 1024 * 1024
    max_pixels: int = 12_000_000
    max_width: int = 6000
    max_height: int = 6000
    max_frames: int = 1
    max_decoded_bytes: int = 48 * 1024 * 1024
    temp_ttl_seconds: int = 300

    @classmethod
    def from_env(cls) -> "ImageLimits":
        return cls(
            max_bytes=_env_int("HARGATURUN_IMAGE_MAX_BYTES", cls.max_bytes, 1),
            max_pixels=_env_int("HARGATURUN_IMAGE_MAX_PIXELS", cls.max_pixels, 1),
            max_width=_env_int("HARGATURUN_IMAGE_MAX_WIDTH", cls.max_width, 1),
            max_height=_env_int("HARGATURUN_IMAGE_MAX_HEIGHT", cls.max_height, 1),
            max_frames=_env_int("HARGATURUN_IMAGE_MAX_FRAMES", cls.max_frames, 1),
            max_decoded_bytes=_env_int(
                "HARGATURUN_IMAGE_MAX_DECODED_BYTES", cls.max_decoded_bytes, 1
            ),
            temp_ttl_seconds=_env_int(
                "HARGATURUN_IMAGE_TEMP_TTL_SECONDS", cls.temp_ttl_seconds, 1
            ),
        )


def _env_int(name: str, default: int, minimum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def reject_remote_url(value: str | None) -> None:
    """Reject URLs (including internal targets) without resolving or fetching."""
    if value is None:
        return
    text = value.strip()
    if not text:
        return
    parsed = urlparse(text)
    if parsed.scheme or parsed.netloc or text.startswith(("//", "\\\\")):
        raise ImageIngestionError("Gambar tidak valid.")


def decode_image_bytes(data: bytes, declared_type: str | None, limits: ImageLimits) -> Image.Image:
    if not isinstance(data, bytes) or not data or len(data) > limits.max_bytes:
        raise ImageIngestionError("Gambar tidak valid.")
    content_type = (declared_type or "").split(";", 1)[0].strip().lower()
    kind = _magic_type(data)
    if kind is None or content_type not in SUPPORTED_TYPES or content_type != kind:
        raise ImageIngestionError("Gambar tidak valid.")
    _validate_container_integrity(data, kind)
    if kind == "image/webp" and (len(data) < 12 or data[8:12] != b"WEBP"):
        raise ImageIngestionError("Gambar tidak valid.")

    # Pillow's bomb protections are process-global; use the stricter request
    # limit and turn warnings into hard failures for this decode.
    old_limit = Image.MAX_IMAGE_PIXELS
    old_filters = ImageFile.LOAD_TRUNCATED_IMAGES
    Image.MAX_IMAGE_PIXELS = limits.max_pixels
    ImageFile.LOAD_TRUNCATED_IMAGES = False
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DecompressionBombWarning)
            with io.BytesIO(data) as stream:
                with Image.open(stream) as source:
                    _check_dimensions(source, limits)
                    frames = getattr(source, "n_frames", 1)
                    if frames != 1 or frames > limits.max_frames:
                        raise ImageIngestionError("Gambar tidak valid.")
                    source.verify()
            with io.BytesIO(data) as stream:
                with Image.open(stream) as source:
                    _check_dimensions(source, limits)
                    image = source.convert("RGB")
                    # Force all compressed pixel data to be consumed before the
                    # source stream is closed, including crafted truncated files.
                    image.load()
                    _check_decoded_memory(image, limits)
                    if data.startswith(b"\x89PNG") and b"IEND\xaeB`\x82" not in data[-32:]:
                        raise ImageIngestionError("Gambar tidak valid.")
                    return image.copy()
    except ImageIngestionError:
        raise
    except (DecompressionBombError, DecompressionBombWarning, UnidentifiedImageError,
            OSError, SyntaxError, ValueError, MemoryError) as error:
        raise ImageIngestionError("Gambar tidak valid.") from error
    finally:
        Image.MAX_IMAGE_PIXELS = old_limit
        ImageFile.LOAD_TRUNCATED_IMAGES = old_filters


def normalize_image(data: bytes, declared_type: str | None, limits: ImageLimits) -> "NormalizedImage":
    image = decode_image_bytes(data, declared_type, limits)
    directory = tempfile.TemporaryDirectory(
        prefix="hargaturun-image-", dir=_private_temp_root(limits.temp_ttl_seconds)
    )
    path = Path(directory.name) / "normalized.png"
    try:
        # A fresh RGB image plus PNG save strips EXIF, GPS, ICC and other input
        # metadata. The temp directory is removed by the context manager.
        image.save(path, format="PNG", optimize=False)
        normalized = path.read_bytes()
        if len(normalized) > limits.max_decoded_bytes:
            raise ImageIngestionError("Gambar tidak valid.")
        return NormalizedImage(
            media_type="image/png",
            data=normalized,
            path=path,
            tempdir=directory,
            width=image.width,
            height=image.height,
        )
    except Exception:
        directory.cleanup()
        raise
    finally:
        image.close()


@dataclass
class NormalizedImage:
    media_type: str
    data: bytes
    path: Path
    tempdir: tempfile.TemporaryDirectory
    width: int
    height: int

    def data_uri(self) -> str:
        return f"data:{self.media_type};base64,{base64.b64encode(self.data).decode('ascii')}"

    def cleanup(self) -> None:
        self.tempdir.cleanup()


def decode_data_uri(value: str, limits: ImageLimits) -> tuple[bytes, str]:
    match = _DATA_URI_RE.fullmatch(value.strip()) if isinstance(value, str) else None
    if not match:
        reject_remote_url(value if isinstance(value, str) else None)
        raise ImageIngestionError("Gambar tidak valid.")
    media_type, encoded = match.groups()
    media_type = media_type.lower()
    if media_type not in SUPPORTED_TYPES:
        raise ImageIngestionError("Gambar tidak valid.")
    try:
        data = base64.b64decode("".join(encoded.split()), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ImageIngestionError("Gambar tidak valid.") from error
    return data, media_type


def _validate_container_integrity(data: bytes, kind: str) -> None:
    """Require the complete container, not merely a decodable prefix."""
    try:
        if kind == "image/jpeg":
            _validate_jpeg(data)
        elif kind == "image/png":
            _validate_png(data)
        elif kind == "image/webp":
            _validate_webp(data)
    except (IndexError, OverflowError, struct.error):
        raise ImageIngestionError("Gambar tidak valid.") from None


def _validate_jpeg(data: bytes) -> None:
    """Walk JPEG markers and require EOI to be the final two bytes."""
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        raise ImageIngestionError("Gambar tidak valid.")
    pos = 2
    while pos < len(data):
        if data[pos] != 0xFF:
            raise ImageIngestionError("Gambar tidak valid.")
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            raise ImageIngestionError("Gambar tidak valid.")
        marker = data[pos]
        pos += 1
        if marker == 0xD9:
            if pos != len(data):
                raise ImageIngestionError("Gambar tidak valid.")
            return
        if marker == 0x00 or marker == 0xD8:
            raise ImageIngestionError("Gambar tidak valid.")
        if marker == 0xDA:  # SOS: scan entropy data until its next marker.
            pos = _jpeg_segment_end(data, pos)
            while pos < len(data):
                if data[pos] != 0xFF:
                    pos += 1
                    continue
                marker_start = pos
                pos += 1
                while pos < len(data) and data[pos] == 0xFF:
                    pos += 1
                if pos >= len(data):
                    raise ImageIngestionError("Gambar tidak valid.")
                next_marker = data[pos]
                if next_marker == 0x00:
                    pos += 1  # stuffed 0xFF data byte
                    continue
                if 0xD0 <= next_marker <= 0xD7:
                    pos += 1  # restart marker within entropy data
                    continue
                pos = marker_start
                break
            continue
        if marker in {0x01, *range(0xD0, 0xD9)}:
            continue
        pos = _jpeg_segment_end(data, pos)
    raise ImageIngestionError("Gambar tidak valid.")


def _jpeg_segment_end(data: bytes, marker_pos: int) -> int:
    if marker_pos + 2 > len(data):
        raise ImageIngestionError("Gambar tidak valid.")
    length = int.from_bytes(data[marker_pos:marker_pos + 2], "big")
    if length < 2 or marker_pos + length > len(data):
        raise ImageIngestionError("Gambar tidak valid.")
    return marker_pos + length


def _validate_png(data: bytes) -> None:
    if len(data) < 8 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ImageIngestionError("Gambar tidak valid.")
    pos = 8
    while pos < len(data):
        if pos + 12 > len(data):
            raise ImageIngestionError("Gambar tidak valid.")
        length = int.from_bytes(data[pos:pos + 4], "big")
        chunk_type = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            raise ImageIngestionError("Gambar tidak valid.")
        payload_end = pos + 8 + length
        expected_crc = int.from_bytes(data[payload_end:payload_end + 4], "big")
        actual_crc = zlib.crc32(data[pos + 4:payload_end]) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ImageIngestionError("Gambar tidak valid.")
        pos = end
        if chunk_type == b"IEND":
            if length != 0 or pos != len(data):
                raise ImageIngestionError("Gambar tidak valid.")
            return
    raise ImageIngestionError("Gambar tidak valid.")


def _validate_webp(data: bytes) -> None:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ImageIngestionError("Gambar tidak valid.")
    riff_size = int.from_bytes(data[4:8], "little")
    if riff_size != len(data) - 8:
        raise ImageIngestionError("Gambar tidak valid.")
    pos = 12
    while pos < len(data):
        if pos + 8 > len(data):
            raise ImageIngestionError("Gambar tidak valid.")
        chunk_size = int.from_bytes(data[pos + 4:pos + 8], "little")
        end = pos + 8 + chunk_size + (chunk_size & 1)
        if end > len(data):
            raise ImageIngestionError("Gambar tidak valid.")
        pos = end
    if pos != len(data):
        raise ImageIngestionError("Gambar tidak valid.")

def _magic_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _check_dimensions(image: Image.Image, limits: ImageLimits) -> None:
    width, height = image.size
    if (
        width < 1 or height < 1 or width > limits.max_width or height > limits.max_height
        or width * height > limits.max_pixels
    ):
        raise ImageIngestionError("Gambar tidak valid.")


def _check_decoded_memory(image: Image.Image, limits: ImageLimits) -> None:
    # RGB is the only accepted normalized representation, so this is exact for
    # the in-memory pixels passed into inference.
    if image.width * image.height * len(image.getbands()) > limits.max_decoded_bytes:
        raise ImageIngestionError("Gambar tidak valid.")


def _private_temp_root(ttl_seconds: int) -> str | None:
    # TemporaryDirectory creates mode 0700 dirs. HARGATURUN_IMAGE_TEMP_DIR is
    # an operator-controlled path only; user input never influences it.
    configured = os.getenv("HARGATURUN_IMAGE_TEMP_DIR")
    if configured:
        path = Path(configured)
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except OSError:
            pass
        _cleanup_expired(path, ttl_seconds)
        return str(path)
    return None


def _cleanup_expired(root: Path, ttl_seconds: int) -> None:
    """Remove abandoned request directories without following symlinks."""
    cutoff = __import__("time").time() - ttl_seconds
    for entry in root.iterdir():
        if not entry.name.startswith("hargaturun-image-") or entry.is_symlink():
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                import shutil
                shutil.rmtree(entry)
        except OSError:
            continue


__all__ = [
    "ImageIngestionError",
    "ImageLimits",
    "NormalizedImage",
    "decode_data_uri",
    "decode_image_bytes",
    "normalize_image",
    "reject_remote_url",
]
