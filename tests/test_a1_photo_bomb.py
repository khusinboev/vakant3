"""clip_photo refuses decompression bombs before decoding them.

The bomb PNGs are hand-built headers (a valid IHDR plus a tiny, truncated
IDAT), so they are a few dozen bytes on disk and the test never allocates the
declared pixels. If the guard were skipped, ``convert()`` would hit the
truncated data and raise ``OSError`` instead of :class:`PhotoRejected`, so the
exception type proves the refusal happened before any decode.
"""

import io
import struct
import zlib

import pytest

pytest.importorskip("PIL.Image")

from PIL import Image  # noqa: E402

from webapp.resume import photos  # noqa: E402
from webapp.resume.photos import MAX_PHOTO_PIXELS, PhotoRejected, clip_photo  # noqa: E402


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _bomb_png(width: int, height: int) -> bytes:
    """PNG header declaring ``width x height`` RGB pixels, with almost no data."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00" * 64)  # far fewer bytes than the declared image
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _real_png(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (40, 90, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "width,height",
    [
        (6000, 6000),     # 36 MP: above our cap, below Pillow's own warning
        (5001, 5000),     # just above 25 MP
        (20000, 2),       # absurd side, tiny pixel count
        (2, 20000),
        (20000, 20000),   # 400 MP: Pillow's DecompressionBombError, normalised
    ],
)
@pytest.mark.parametrize("shape", ["square", "circle"])
def test_bomb_is_rejected_without_decoding(width, height, shape):
    data = _bomb_png(width, height)
    assert len(data) < 200
    with pytest.raises(PhotoRejected):
        clip_photo(data, shape=shape)


def test_header_fixture_would_fail_differently_if_decoded():
    """Sanity check of the fixture: decoding it fails with a non-guard error."""
    data = _bomb_png(100, 100)
    with pytest.raises(OSError):
        Image.open(io.BytesIO(data)).convert("RGBA")


def test_limit_boundary_is_inclusive(monkeypatch):
    # Shrink the cap so the boundary is testable with a small real image.
    monkeypatch.setattr(photos, "MAX_PHOTO_PIXELS", 400 * 300)
    assert clip_photo(_real_png(400, 300), shape="square")[:2] == b"\xff\xd8"
    with pytest.raises(PhotoRejected):
        clip_photo(_real_png(401, 300), shape="square")


def test_normal_photo_still_clips():
    out = clip_photo(_real_png(240, 300), shape="circle", size_px=120)
    assert Image.open(io.BytesIO(out)).size == (120, 120)
    assert MAX_PHOTO_PIXELS == 25_000_000


@pytest.mark.parametrize("template_id", ["photo_classic", "photo_sidebar", "europass"])
def test_pdf_falls_back_to_placeholder_for_a_bomb(template_id):
    from webapp.resume.normalize import build_resume_document
    from webapp.resume.render.pdf import generate_pdf_bytes
    from webapp.resume.schemas import ResumeProfileData

    doc = build_resume_document(ResumeProfileData(name="Test User", position="QA"))
    doc["photo_url"] = "https://t.me/i/userpic/320/test.jpg"
    doc["photo_bytes"] = _bomb_png(6000, 6000)
    assert generate_pdf_bytes(doc, template_id=template_id).startswith(b"%PDF-")
