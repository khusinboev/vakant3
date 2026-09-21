"""Broadcast media uploads.

Rules (the client is never trusted):

* the file name that arrives with the multipart part is discarded — the stored
  name is ``<uuid4>.<ext>`` and the extension comes from the sniffed content;
* the type is decided by magic bytes, not by the ``Content-Type`` header
  (a ``.jpg`` that is really a script is rejected);
* the body is streamed and aborted as soon as it passes the size cap, so an
  oversized upload never lands on disk in full;
* everything is written under ``<DB dir>/uploads/<yyyymm>/`` and the public
  value is a path relative to the DB directory, resolved back through
  ``resolve_upload_path`` (which refuses anything escaping the root).
"""

from __future__ import annotations

import os
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from webapp.core.config import DB_PATH
from webapp.core.errors import api_error

# Error codes (errors.py itself is owned by the auth module).
UPLOAD_TOO_LARGE = "UPLOAD_TOO_LARGE"
UPLOAD_TYPE_NOT_ALLOWED = "UPLOAD_TYPE_NOT_ALLOWED"
UPLOAD_EMPTY = "UPLOAD_EMPTY"

MAX_UPLOAD_BYTES = 20 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
#: Enough for every signature below (mp4 needs byte 4..12).
SNIFF_BYTES = 64

UPLOADS_DIRNAME = "uploads"

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@dataclass(frozen=True)
class MediaType:
    mime: str
    ext: str
    kind: str  # photo | video | document


#: Sniffed type -> what the broadcast worker may send it as.
JPEG = MediaType("image/jpeg", "jpg", "photo")
PNG = MediaType("image/png", "png", "photo")
WEBP = MediaType("image/webp", "webp", "photo")
MP4 = MediaType("video/mp4", "mp4", "video")
PDF = MediaType("application/pdf", "pdf", "document")
DOCX = MediaType(DOCX_MIME, "docx", "document")

ALLOWED_TYPES: tuple[MediaType, ...] = (JPEG, PNG, WEBP, MP4, PDF, DOCX)
#: Which sniffed kinds a broadcast of a given kind accepts.
KIND_FOR_BROADCAST = {"photo": "photo", "video": "video", "document": "document"}


def sniff_media_type(head: bytes) -> MediaType | None:
    """Detect an allowed type from the first bytes, or None."""
    if len(head) < 8:
        return None
    if head[:3] == b"\xff\xd8\xff":
        return JPEG
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return PNG
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return WEBP
    if head[4:8] == b"ftyp":
        return MP4
    if head[:5] == b"%PDF-":
        return PDF
    if head[:4] == b"PK\x03\x04":
        # A zip container: only Word documents are allowed through, and that is
        # decided by looking inside (see _is_docx), not by the file name.
        return DOCX
    return None


def _is_docx(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, OSError):
        return False
    return "word/document.xml" in names and "[Content_Types].xml" in names


def uploads_root() -> Path:
    """``<DB dir>/uploads`` — beside the SQLite file, not inside the repo."""
    return Path(DB_PATH).resolve().parent / UPLOADS_DIRNAME


def resolve_upload_path(relative: str) -> Path:
    """Map a stored ``uploads/...`` value back to an absolute path.

    Raises ``ValueError`` for anything that escapes the uploads root, so a
    crafted ``media_path`` in the DB can never make the worker read ``/etc``.
    """
    raw = str(relative or "").strip()
    if not raw:
        raise ValueError("empty upload path")
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        root_parent = uploads_root().parent
        resolved = (root_parent / candidate).resolve()
    root = uploads_root()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"upload path outside the uploads root: {relative}")
    return resolved


def _relative(path: Path) -> str:
    """The value stored in the DB: ``uploads/<yyyymm>/<uuid>.<ext>``."""
    return str(path.relative_to(uploads_root().parent)).replace(os.sep, "/")


async def save_upload_stream(
    chunks: AsyncIterator[bytes],
    *,
    max_bytes: int = MAX_UPLOAD_BYTES,
    now=None,
) -> dict:
    """Stream ``chunks`` to disk with the validation described in the module doc."""
    import time

    stamp = time.strftime("%Y%m", time.localtime(now if now is not None else time.time()))
    directory = uploads_root() / stamp
    directory.mkdir(parents=True, exist_ok=True)
    temp_path = directory / f".tmp-{uuid.uuid4().hex}"

    size = 0
    head = b""
    try:
        with open(temp_path, "wb") as handle:
            async for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise api_error(413, UPLOAD_TOO_LARGE, max_bytes=max_bytes)
                if len(head) < SNIFF_BYTES:
                    head += chunk[: SNIFF_BYTES - len(head)]
                handle.write(chunk)

        if size == 0:
            raise api_error(400, UPLOAD_EMPTY)

        media = sniff_media_type(head)
        if media is None or (media is DOCX and not _is_docx(temp_path)):
            raise api_error(415, UPLOAD_TYPE_NOT_ALLOWED)

        final_path = directory / f"{uuid.uuid4().hex}.{media.ext}"
        os.replace(temp_path, final_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise

    return {
        "path": _relative(final_path),
        "mime": media.mime,
        "size": size,
        "kind": media.kind,
    }


async def save_upload(file, *, max_bytes: int = MAX_UPLOAD_BYTES) -> dict:
    """Validate and store a ``fastapi.UploadFile``; the client name is ignored."""

    async def _chunks() -> AsyncIterator[bytes]:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            yield chunk

    try:
        return await save_upload_stream(_chunks(), max_bytes=max_bytes)
    finally:
        try:
            await file.close()
        except Exception:  # pragma: no cover - already-closed spooled file
            pass
