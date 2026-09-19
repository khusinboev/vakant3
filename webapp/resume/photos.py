"""Profile photo handling: data URIs, an allowlisted remote fetch, and masking."""

import base64
import io
import logging
import re
from urllib.parse import urlparse

import httpx

_log = logging.getLogger(__name__)

try:
    from PIL import Image as _PILImage, ImageDraw as _PILImageDraw  # type: ignore[import]
    PILLOW_AVAILABLE = True
except ImportError:  # pragma: no cover - Pillow is optional
    PILLOW_AVAILABLE = False

MIN_PHOTO_BYTES = 500
MAX_PHOTO_BYTES = 5 * 1024 * 1024
MAX_DATA_URI_BYTES = 10 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 3.0

# Only Telegram-hosted images may be fetched server-side; anything else is skipped.
ALLOWED_HOST_RE = re.compile(
    r"^(?:[a-z0-9-]+\.)*(?:t\.me|telegram\.org|telegram\.me|telesco\.pe)$",
    re.IGNORECASE,
)


def is_allowed_photo_host(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    return bool(ALLOWED_HOST_RE.match(parsed.hostname))


def _decode_data_uri(url: str) -> bytes | None:
    try:
        _, encoded = url.split(",", 1)
        data = base64.b64decode(encoded)
    except Exception:
        return None
    if MIN_PHOTO_BYTES < len(data) < MAX_DATA_URI_BYTES:
        return data
    return None


async def fetch_photo_bytes(url: str) -> bytes | None:
    """Return raw photo bytes for a data URI or an allowlisted https URL, else None."""
    url = str(url or "").strip()
    if not url:
        return None

    if url.startswith("data:image/"):
        return _decode_data_uri(url)

    if not is_allowed_photo_host(url):
        _log.info("resume photo skipped: host not allowlisted")
        return None

    try:
        async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=False) as client:
            response = await client.get(url, headers={"User-Agent": "VakantResume/1.0"})
    except Exception as exc:
        _log.info("resume photo fetch failed: %s", exc)
        return None

    if response.status_code == 200 and MIN_PHOTO_BYTES < len(response.content) < MAX_PHOTO_BYTES:
        return response.content
    return None


def clip_photo(img_bytes: bytes, shape: str = "square", size_px: int = 220) -> bytes:
    """Centre-crop and mask a photo. Returns JPEG (square) or PNG (masked) bytes."""
    if not PILLOW_AVAILABLE:
        return img_bytes

    img = _PILImage.open(io.BytesIO(img_bytes)).convert("RGBA")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((size_px, size_px), _PILImage.LANCZOS)

    if shape == "square":
        out = io.BytesIO()
        img.convert("RGB").save(out, format="JPEG", quality=88)
        return out.getvalue()

    mask = _PILImage.new("L", (size_px, size_px), 0)
    draw = _PILImageDraw.Draw(mask)
    if shape == "circle":
        draw.ellipse((0, 0, size_px - 1, size_px - 1), fill=255)
    elif shape == "rounded":
        radius = size_px // 6
        draw.rounded_rectangle((0, 0, size_px - 1, size_px - 1), radius=radius, fill=255)
    else:
        draw.rectangle((0, 0, size_px - 1, size_px - 1), fill=255)

    img.putalpha(mask)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()
