"""Admin broadcasts: compose, preview, queue, cancel, inspect.

The API only ever writes rows. Sending is the bot process's job
(``src/functions/broadcast_worker.py``), which is also where the targeting SQL
lives so the bot's own broadcast flow and this router cannot drift apart.

Validation happens here, before anything is queued: Telegram's HTML subset,
the 4096/1024 character limits, and the inline buttons. A broadcast that
Telegram would reject on the first recipient must never reach 50 000 rows.
"""

import base64
import binascii
import html
import json
import logging
import time
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.functions.broadcast_worker import (
    create_broadcast,
    is_valid_segment,
    materialize_targets,
)
from webapp.core import errors
from webapp.core.auth import require_role
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from webapp.core.uploads import (
    MAX_UPLOAD_BYTES,
    UPLOAD_TOO_LARGE,
    resolve_upload_path,
    save_upload,
)

_log = logging.getLogger(__name__)

# Error codes (webapp/core/errors.py is owned by the auth module).
BROADCAST_INVALID = "BROADCAST_INVALID"
BROADCAST_NOT_CANCELLABLE = "BROADCAST_NOT_CANCELLABLE"

MAX_TEXT_LENGTH = 4096
MAX_CAPTION_LENGTH = 1024
MAX_BUTTONS = 6
MAX_RAW_HTML = 16 * 1024
PREVIEW_TIMEOUT_SECONDS = 20.0

#: Telegram's HTML subset (https://core.telegram.org/bots/api#html-style).
ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "a", "code", "pre", "blockquote", "span", "tg-spoiler", "br",
}
VOID_TAGS = {"br"}
ALLOWED_LINK_SCHEMES = {"http", "https", "tg"}


from webapp.core.audit import log_admin_action
from webapp.core.confirm import require_confirmation

router = APIRouter(prefix="/admin", tags=["admin-broadcasts"])
require_broadcast_admin = require_role("admin")
confirm_create = require_confirmation("broadcast.create", ["kind", "segment"])
#: ``/queue`` is the step that actually reaches every user, so it carries its
#: own confirmation bound to the broadcast id. Creating a draft is harmless;
#: queueing it is not, and a token minted for broadcast 7 must not send 8.
confirm_queue = require_confirmation("broadcast.queue", ["broadcast_id"])


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

class _TelegramHTMLValidator(HTMLParser):
    """Checks the tag allowlist, nesting and link schemes; measures visible text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.text_length = 0
        self.error: str | None = None

    def _fail(self, reason: str) -> None:
        if self.error is None:
            self.error = reason

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in ALLOWED_TAGS:
            return self._fail(f"tag_not_allowed:{tag}")
        attributes = dict(attrs)
        if tag == "a":
            href = (attributes.get("href") or "").strip()
            if not _is_allowed_link(href):
                return self._fail("bad_link")
        elif tag == "span":
            if (attributes.get("class") or "").strip() != "tg-spoiler":
                return self._fail("span_requires_tg_spoiler")
        elif tag == "code" or tag == "pre":
            pass
        elif attributes:
            return self._fail(f"attributes_not_allowed:{tag}")
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in VOID_TAGS:
            return self._fail(f"tag_not_allowed:{tag}")

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID_TAGS:
            return
        if tag not in ALLOWED_TAGS:
            return self._fail(f"tag_not_allowed:{tag}")
        if not self.stack or self.stack.pop() != tag:
            self._fail(f"unbalanced:{tag}")

    def handle_data(self, data: str) -> None:
        self.text_length += len(data)

    def handle_entityref(self, name: str) -> None:  # convert_charrefs handles most
        self.text_length += 1

    def handle_charref(self, name: str) -> None:
        self.text_length += 1


def _is_allowed_link(href: str) -> bool:
    if not href:
        return False
    parsed = urlparse(href)
    if parsed.scheme.lower() not in ALLOWED_LINK_SCHEMES:
        return False
    if parsed.scheme.lower() == "tg":
        return bool(parsed.netloc or parsed.path)
    return bool(parsed.netloc)


def validate_html_text(text: str | None, *, limit: int, field: str = "text") -> str | None:
    """Telegram-HTML validation. Raises BROADCAST_INVALID{field, reason}."""
    if text is None:
        return None
    raw = str(text)
    if len(raw) > MAX_RAW_HTML:
        raise errors.api_error(400, BROADCAST_INVALID, field=field, reason="too_long")
    validator = _TelegramHTMLValidator()
    validator.feed(raw)
    validator.close()
    if validator.error:
        raise errors.api_error(400, BROADCAST_INVALID, field=field, reason=validator.error)
    if validator.stack:
        raise errors.api_error(
            400, BROADCAST_INVALID, field=field, reason=f"unclosed:{validator.stack[-1]}"
        )
    if validator.text_length > limit:
        raise errors.api_error(
            400, BROADCAST_INVALID, field=field, reason="too_long", limit=limit
        )
    return raw


def validate_buttons(buttons: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """At most six one-per-row URL buttons pointing at http(s)/t.me/tg."""
    items = list(buttons or [])
    if len(items) > MAX_BUTTONS:
        raise errors.api_error(400, BROADCAST_INVALID, field="buttons", reason="too_many")
    cleaned: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise errors.api_error(400, BROADCAST_INVALID, field=f"buttons[{index}]", reason="shape")
        label = str(item.get("text") or "").strip()
        url = str(item.get("url") or "").strip()
        if not 1 <= len(label) <= 64:
            raise errors.api_error(
                400, BROADCAST_INVALID, field=f"buttons[{index}].text", reason="length"
            )
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https", "tg"} or not (
            parsed.netloc or parsed.path
        ):
            raise errors.api_error(
                400, BROADCAST_INVALID, field=f"buttons[{index}].url", reason="scheme"
            )
        cleaned.append({"text": label, "url": url})
    return cleaned


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

class ButtonIn(BaseModel):
    text: str
    url: str


class BroadcastCreateIn(BaseModel):
    kind: Literal["text", "photo", "video", "document", "forward"]
    text: str | None = None
    buttons: list[ButtonIn] = Field(default_factory=list)
    media_path: str | None = None
    forward_chat_id: int | None = None
    forward_message_id: int | None = None
    segment: str = "all"
    exclude_blocked: bool = True


class BroadcastQueueIn(BaseModel):
    """Body of ``/queue``. ``broadcast_id`` repeats the path id because the
    confirmation token is bound to JSON body fields (see
    ``webapp/core/confirm.py``); the two must match."""

    broadcast_id: int


def _invalid(field: str, reason: str):
    return errors.api_error(400, BROADCAST_INVALID, field=field, reason=reason)


def _validate_payload(body: BroadcastCreateIn) -> tuple[str | None, list[dict[str, str]]]:
    if not is_valid_segment(body.segment):
        raise _invalid("segment", "unknown")

    if body.kind == "forward":
        if not body.forward_chat_id or not body.forward_message_id:
            raise _invalid("forward_message_id", "required")
        return None, []

    buttons = validate_buttons([b.model_dump() for b in body.buttons])

    if body.kind == "text":
        text = validate_html_text(body.text, limit=MAX_TEXT_LENGTH)
        if not (text or "").strip():
            raise _invalid("text", "required")
        return text, buttons

    if not body.media_path:
        raise _invalid("media_path", "required")
    try:
        path = resolve_upload_path(body.media_path)
    except ValueError:
        raise _invalid("media_path", "outside_root") from None
    if not path.is_file():
        raise _invalid("media_path", "missing")
    caption = validate_html_text(body.text, limit=MAX_CAPTION_LENGTH, field="caption")
    return caption, buttons


# --------------------------------------------------------------------------
# Telegram (preview only; real sending happens in the bot process)
# --------------------------------------------------------------------------

async def telegram_call(method: str, data: dict[str, Any], files: dict | None = None) -> dict:
    token = get_settings().TOKEN
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        async with httpx.AsyncClient(timeout=PREVIEW_TIMEOUT_SECONDS) as client:
            response = await client.post(url, data=data, files=files)
    except httpx.HTTPError as exc:
        _log.warning("telegram %s failed: %s", method, exc)
        raise errors.api_error(502, errors.UPSTREAM_ERROR) from exc
    payload = {}
    try:
        payload = response.json()
    except ValueError:
        pass
    if not payload.get("ok"):
        raise errors.api_error(
            502, errors.TELEGRAM_SEND_FAILED, description=str(payload.get("description") or "")[:200]
        )
    return payload.get("result") or {}


def _reply_markup(buttons_json: str | None) -> str | None:
    try:
        buttons = json.loads(buttons_json or "[]")
    except json.JSONDecodeError:
        return None
    if not buttons:
        return None
    return json.dumps({"inline_keyboard": [[b] for b in buttons]})


async def _send_preview(job: dict[str, Any], chat_id: int) -> dict:
    data: dict[str, Any] = {"chat_id": str(chat_id)}
    markup = _reply_markup(job["buttons_json"])
    if markup:
        data["reply_markup"] = markup

    if job["kind"] == "forward":
        return await telegram_call(
            "forwardMessage",
            {
                "chat_id": str(chat_id),
                "from_chat_id": str(job["forward_chat_id"]),
                "message_id": str(job["forward_message_id"]),
            },
        )
    if job["kind"] == "text":
        data.update({"text": job["text"] or "", "parse_mode": "HTML"})
        return await telegram_call("sendMessage", data)

    method, field = {
        "photo": ("sendPhoto", "photo"),
        "video": ("sendVideo", "video"),
        "document": ("sendDocument", "document"),
    }[job["kind"]]
    if job["text"]:
        data.update({"caption": job["text"], "parse_mode": "HTML"})
    if job["media_file_id"]:
        data[field] = job["media_file_id"]
        return await telegram_call(method, data)
    path = resolve_upload_path(job["media_path"] or "")
    with open(path, "rb") as handle:
        return await telegram_call(method, data, files={field: (path.name, handle.read())})


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _encode_cursor(value: int) -> str:
    return base64.urlsafe_b64encode(str(value).encode()).decode().rstrip("=")


def _decode_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        return int(base64.urlsafe_b64decode(padded.encode()).decode())
    except (ValueError, binascii.Error):
        raise errors.validation_error("cursor") from None


def _row_to_dict(row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["buttons"] = json.loads(data.pop("buttons_json", "[]") or "[]")
    except json.JSONDecodeError:
        data["buttons"] = []
    try:
        data["target"] = json.loads(data.pop("target_json", "{}") or "{}")
    except json.JSONDecodeError:
        data["target"] = {}
    return data


async def _fetch(db, broadcast_id: int) -> dict[str, Any]:
    cursor = await db.execute("SELECT * FROM broadcasts WHERE id = ?", (broadcast_id,))
    row = await cursor.fetchone()
    if row is None:
        raise errors.not_found("broadcast")
    return dict(row)


async def _admin_ids(db) -> list[int]:
    """Recipients of a ``test_admins`` broadcast: the admins table plus env."""
    ids = set(get_settings().admin_ids_set)
    try:
        cursor = await db.execute("SELECT user_id FROM admins WHERE COALESCE(disabled, 0) = 0")
        ids.update(int(row[0]) for row in await cursor.fetchall())
    except Exception:  # pragma: no cover - table lands with the auth migration
        pass
    return sorted(ids)


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

#: Slack over ``MAX_UPLOAD_BYTES`` for multipart framing (boundaries, part
#: headers, the trailing CRLF). A body larger than file + slack cannot hold a
#: file within the cap, so it is refused on the ``Content-Length`` alone.
UPLOAD_ENVELOPE_SLACK = 64 * 1024

MAX_REQUEST_BYTES = MAX_UPLOAD_BYTES + UPLOAD_ENVELOPE_SLACK


def _too_large():
    return errors.api_error(413, UPLOAD_TOO_LARGE, max_bytes=MAX_UPLOAD_BYTES)


async def _capped_stream(request: Request):
    """``request.stream()`` that gives up the moment the body passes the cap.

    The size limit used to be enforced only by ``save_upload``, i.e. *after*
    Starlette had already buffered the whole multipart body (to memory, then to
    a temp file). An oversize body was therefore written out in full before
    being rejected. Counting here means the connection is dropped mid-body.
    """
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_REQUEST_BYTES:
            raise _too_large()
        yield chunk


@router.post("/uploads")
@limiter.limit("10/minute")
async def upload_media(
    request: Request,
    admin=Depends(require_broadcast_admin),
    db=Depends(get_db),
):
    """Store one media file. The type is decided by magic bytes, not by name.

    The multipart body is parsed by hand rather than through a
    ``file: UploadFile = File(...)`` parameter: FastAPI parses declared bodies
    *before* dependencies run, so with that signature an anonymous caller could
    make the server buffer 2 GB before ``require_role`` ever rejected them.
    Here the role check and the ``Content-Length`` check both come first.
    """
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > MAX_REQUEST_BYTES:
                raise _too_large()
        except ValueError:
            raise _invalid("file", "malformed") from None

    try:
        form = await MultiPartParser(
            request.headers, _capped_stream(request), max_files=1, max_fields=4
        ).parse()
    except MultiPartException:
        raise _invalid("file", "malformed") from None

    try:
        file = form.get("file")
        if not isinstance(file, StarletteUploadFile):
            raise _invalid("file", "required")
        saved = await save_upload(file)
    finally:
        await form.close()
    await log_admin_action(
        db,
        actor_id=admin["user_id"],
        action="broadcast.upload",
        target_type="upload",
        target_id=saved["path"],
        payload={"mime": saved["mime"], "size": saved["size"]},
    )
    await db.commit()
    return saved


@router.post("/broadcasts")
@limiter.limit("10/minute")
async def create(
    request: Request,
    body: BroadcastCreateIn,
    admin=Depends(require_broadcast_admin),
    _confirmed=Depends(confirm_create),
    db=Depends(get_db),
):
    """Create a draft. Nothing is sent until ``/queue``."""
    text, buttons = _validate_payload(body)
    target = {"segment": body.segment, "exclude_blocked": bool(body.exclude_blocked)}
    broadcast_id = await create_broadcast(
        db,
        actor_id=admin["user_id"],
        kind=body.kind,
        text=text,
        buttons=buttons,
        media_path=body.media_path,
        forward_chat_id=body.forward_chat_id,
        forward_message_id=body.forward_message_id,
        target=target,
        status="draft",
    )
    await log_admin_action(
        db,
        actor_id=admin["user_id"],
        action="broadcast.create",
        target_type="broadcast",
        target_id=str(broadcast_id),
        payload={"kind": body.kind, "segment": body.segment, "buttons": len(buttons)},
    )
    await db.commit()
    return _row_to_dict(await _fetch(db, broadcast_id))


@router.post("/broadcasts/{broadcast_id}/preview")
@limiter.limit("10/minute")
async def preview(
    request: Request,
    broadcast_id: int,
    admin=Depends(require_broadcast_admin),
    db=Depends(get_db),
):
    """Send the composed message to the acting admin only."""
    job = await _fetch(db, broadcast_id)
    result = await _send_preview(job, int(admin["user_id"]))
    await log_admin_action(
        db,
        actor_id=admin["user_id"],
        action="broadcast.preview",
        target_type="broadcast",
        target_id=str(broadcast_id),
    )
    await db.commit()
    return {"ok": True, "message_id": result.get("message_id")}


@router.post("/broadcasts/{broadcast_id}/queue")
@limiter.limit("10/minute")
async def queue(
    request: Request,
    broadcast_id: int,
    body: BroadcastQueueIn,
    admin=Depends(require_broadcast_admin),
    _confirmed=Depends(confirm_queue),
    db=Depends(get_db),
):
    """Materialize the targets (one INSERT...SELECT) and hand the job to the bot."""
    if int(body.broadcast_id) != int(broadcast_id):
        raise errors.validation_error("broadcast_id")
    job = await _fetch(db, broadcast_id)
    if job["status"] != "draft":
        raise errors.api_error(409, BROADCAST_INVALID, field="status", reason=job["status"])
    try:
        target = json.loads(job["target_json"] or "{}")
    except json.JSONDecodeError:
        target = {}
    total = await materialize_targets(db, broadcast_id, target, await _admin_ids(db))
    if total == 0:
        raise _invalid("segment", "empty")
    await db.execute(
        "UPDATE broadcasts SET status = 'queued', total = ?, error = NULL "
        "WHERE id = ? AND status = 'draft'",
        (total, broadcast_id),
    )
    await log_admin_action(
        db,
        actor_id=admin["user_id"],
        action="broadcast.queue",
        target_type="broadcast",
        target_id=str(broadcast_id),
        payload={"total": total, "segment": target.get("segment")},
    )
    await db.commit()
    return {"id": broadcast_id, "status": "queued", "total": total}


@router.post("/broadcasts/{broadcast_id}/cancel")
@limiter.limit("10/minute")
async def cancel(
    request: Request,
    broadcast_id: int,
    admin=Depends(require_broadcast_admin),
    db=Depends(get_db),
):
    """Stop a queued or running broadcast at the next batch boundary."""
    job = await _fetch(db, broadcast_id)
    if job["status"] not in {"draft", "queued", "running", "paused"}:
        raise errors.api_error(409, BROADCAST_NOT_CANCELLABLE, status=job["status"])
    await db.execute(
        "UPDATE broadcasts SET status = 'cancelled', finished_at = ? WHERE id = ?",
        (int(time.time()), broadcast_id),
    )
    await log_admin_action(
        db,
        actor_id=admin["user_id"],
        action="broadcast.cancel",
        target_type="broadcast",
        target_id=str(broadcast_id),
        payload={"from": job["status"]},
    )
    await db.commit()
    return {"id": broadcast_id, "status": "cancelled"}


@router.get("/broadcasts")
@limiter.limit("60/minute")
async def list_broadcasts(
    request: Request,
    limit: int = 20,
    cursor: str | None = None,
    admin=Depends(require_broadcast_admin),
    db=Depends(get_db),
):
    """Newest first, cursor = the last id of the previous page."""
    limit = max(1, min(100, int(limit)))
    before_id = _decode_cursor(cursor)
    sql = "SELECT * FROM broadcasts"
    params: list[Any] = []
    if before_id is not None:
        sql += " WHERE id < ?"
        params.append(before_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit + 1)
    result = await db.execute(sql, params)
    rows = [_row_to_dict(row) for row in await result.fetchall()]
    next_cursor = _encode_cursor(rows[limit - 1]["id"]) if len(rows) > limit else None
    counted = await db.execute("SELECT COUNT(*) FROM broadcasts")
    total = int((await counted.fetchone())[0])
    return {"items": rows[:limit], "next_cursor": next_cursor, "total": total}


@router.get("/broadcasts/{broadcast_id}")
@limiter.limit("60/minute")
async def detail(
    request: Request,
    broadcast_id: int,
    admin=Depends(require_broadcast_admin),
    db=Depends(get_db),
):
    """Counters plus the last 20 per-user errors."""
    job = _row_to_dict(await _fetch(db, broadcast_id))
    cursor = await db.execute(
        "SELECT user_id, status, error, sent_at FROM broadcast_targets "
        "WHERE broadcast_id = ? AND status IN ('failed', 'blocked') "
        "ORDER BY sent_at DESC, user_id DESC LIMIT 20",
        (broadcast_id,),
    )
    job["errors"] = [dict(row) for row in await cursor.fetchall()]
    cursor = await db.execute(
        "SELECT status, COUNT(*) AS count FROM broadcast_targets WHERE broadcast_id = ? GROUP BY status",
        (broadcast_id,),
    )
    job["targets"] = {row[0]: int(row[1]) for row in await cursor.fetchall()}
    job["text_preview"] = html.unescape(str(job.get("text") or ""))[:200]
    return job
