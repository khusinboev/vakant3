"""Resume builder endpoints: profile CRUD, template catalogue, Telegram delivery, events."""

import json
import logging
import time

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from webapp.core import errors
from webapp.core.auth import current_user
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.entry_gate import require_entry
from webapp.core.event_queue import enqueue_event
from webapp.core.i18n import get_lang
from webapp.core.limiter import limiter
from webapp.resume import repository
from webapp.resume.i18n import t
from webapp.resume.normalize import (
    build_resume_document,
    default_profile,
    normalize_color,
    normalize_educations,
    normalize_experiences,
    normalize_items,
    normalize_profile_from_payload,
)
from webapp.resume.photos import fetch_photo_bytes
from webapp.resume.render.pdf import generate_pdf_bytes
from webapp.resume.schemas import (
    ALLOWED_EVENT_NAMES,
    ALLOWED_EVENT_STEPS,
    FREE_TEMPLATES,
    IDEMPOTENCY_RE,
    MAX_PHOTO_URL_CHARS,
    MAX_PROFILE_BYTES,
    ResumeEventRequest,
    ResumeEventResponse,
    ResumeProfileData,
    ResumeProfileResponse,
    ResumeProfileUpsertRequest,
    ResumeSendRequest,
    ResumeSendResponse,
    ResumeTemplatesResponse,
    TEMPLATES,
    template_items,
)

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["resume"], dependencies=[Depends(require_entry)])

TELEGRAM_SEND_TIMEOUT = 25
TELEGRAM_SEND_ATTEMPTS = 2

#: ``X-Idempotency-Key`` prefix the Mini App uses for the periodic autosave.
AUTOSAVE_KEY_PREFIX = "resume_autosave:"


def _require_template(template_id: str) -> str:
    normalized = (template_id or "").strip().lower()
    if normalized not in TEMPLATES:
        raise errors.validation_error("template_id")
    return normalized


def _require_template_access(template_id: str, user: dict) -> None:
    if template_id not in FREE_TEMPLATES and not bool(user.get("is_pro")):
        raise errors.api_error(403, errors.PREMIUM_TEMPLATE, template_id=template_id)


def is_autosave_key(idempotency_key: str) -> bool:
    """True for the Mini App's 15 s autosave, false for an explicit save.

    The wizard builds every key as ``<action>:<epoch_ms>:<random>`` with
    ``action`` either ``resume_save`` (the Save button, retried by the user)
    or ``resume_autosave`` (the timer, never retried) — see
    ``webapp/frontend/src/pages/ResumeStudio/useResumeSync.ts``.
    """
    return idempotency_key.lower().startswith(AUTOSAVE_KEY_PREFIX)


def track_event(
    user_id: int, event_name: str, step: str | None = None, meta_json: str | None = None
) -> None:
    """Record one resume analytics beat (batched; never blocks the request)."""
    enqueue_event(user_id, event_name, step, meta_json)


@router.get("/templates", response_model=ResumeTemplatesResponse)
async def get_templates(lang: str = Depends(get_lang)) -> ResumeTemplatesResponse:
    return ResumeTemplatesResponse(items=template_items(lang))


@router.get("/profile", response_model=ResumeProfileResponse)
@limiter.limit("120/minute")
async def get_profile(
    request: Request,
    user=Depends(current_user),
    db=Depends(get_db),
) -> ResumeProfileResponse:
    user_id = int(user["user_id"])
    row = await repository.load_resume_row(db, user_id)

    if not row:
        return ResumeProfileResponse(
            profile=default_profile(str(user.get("first_name") or "")),
            selected_template="clean",
            accent_color="#0f766e",
            updated_at=None,
        )

    try:
        payload = json.loads(str(row["profile_json"] or "{}"))
    except Exception:
        payload = {}

    selected_template = str(row["selected_template"] or "clean")
    profile = normalize_profile_from_payload(payload, str(user.get("first_name") or ""))
    accent_color = normalize_color(
        payload.get("accent_color") if isinstance(payload, dict) else None,
        selected_template,
    )

    return ResumeProfileResponse(
        profile=profile,
        selected_template=selected_template,
        accent_color=accent_color,
        updated_at=int(row["updated_at"] or 0),
    )


@router.put("/profile", response_model=ResumeProfileResponse)
@limiter.limit("30/minute")
async def put_profile(
    payload: ResumeProfileUpsertRequest,
    request: Request,
    user=Depends(current_user),
    db=Depends(get_db),
) -> ResumeProfileResponse:
    user_id = int(user["user_id"])

    idempotency_key = (request.headers.get("X-Idempotency-Key") or "").strip()
    if idempotency_key and not IDEMPOTENCY_RE.match(idempotency_key):
        raise errors.validation_error("idempotency_key")
    # An autosave is not replayed by the client, so it gets no idempotency row
    # (see AUTOSAVE_KEY_PREFIX): that is one INSERT + one COMMIT less every
    # 15 s per open wizard. The lookup is skipped too — nothing ever stores a
    # row under an autosave key, so it could only ever miss.
    use_idempotency = bool(idempotency_key) and not is_autosave_key(idempotency_key)
    if use_idempotency:
        cached = await repository.get_idempotent_response(db, user_id, "resume_profile_save", idempotency_key)
        if cached:
            return cached

    template_id = _require_template(payload.selected_template)
    _require_template_access(template_id, user)

    # Cheap size guard before any heavy normalization work.
    photo_url = str(payload.profile.photo_url or "").strip()
    if len(photo_url) > MAX_PHOTO_URL_CHARS:
        raise errors.api_error(413, errors.PAYLOAD_TOO_LARGE)

    normalized_profile = ResumeProfileData(
        full_name=str(payload.profile.full_name or "").strip(),
        position=str(payload.profile.position or "").strip(),
        phone=str(payload.profile.phone or "").strip(),
        email=str(payload.profile.email or "").strip(),
        location=str(payload.profile.location or "").strip(),
        website=str(payload.profile.website or "").strip(),
        summary=str(payload.profile.summary or "").strip(),
        experiences=normalize_experiences(payload.profile.experiences),
        educations=normalize_educations(payload.profile.educations),
        skills=normalize_items(payload.profile.skills),
        languages=normalize_items(payload.profile.languages),
        photo_url=photo_url,
    )

    accent_color = normalize_color(payload.accent_color, template_id)
    now = int(time.time())
    profile_json = json.dumps(
        {**normalized_profile.model_dump(), "accent_color": accent_color},
        ensure_ascii=False,
    )
    if len(profile_json.encode("utf-8")) > MAX_PROFILE_BYTES:
        raise errors.api_error(413, errors.PAYLOAD_TOO_LARGE)

    await repository.save_profile(db, user_id, profile_json, template_id, now)

    response_obj = ResumeProfileResponse(
        profile=normalized_profile,
        selected_template=template_id,
        accent_color=accent_color,
        updated_at=now,
    )
    if use_idempotency:
        await repository.save_idempotent_response(db, user_id, "resume_profile_save", idempotency_key, response_obj)
    await db.commit()

    return response_obj


@router.post("/send-telegram", response_model=ResumeSendResponse)
@limiter.limit("10/minute")
async def send_resume_to_telegram(
    payload: ResumeSendRequest,
    request: Request,
    user=Depends(current_user),
    lang: str = Depends(get_lang),
    db=Depends(get_db),
) -> ResumeSendResponse:
    user_id = int(user["user_id"])
    template_id = _require_template(payload.template_id)
    _require_template_access(template_id, user)

    settings = get_settings()
    if not settings.TOKEN:
        raise errors.api_error(500, errors.SERVER_MISCONFIGURED)

    row = await repository.load_resume_row(db, user_id)
    profile, accent_hex = repository.load_profile_for_generation(
        row, str(user.get("first_name") or ""), template_id
    )

    doc = build_resume_document(profile, lang)
    doc["photo_bytes"] = await fetch_photo_bytes(doc.get("photo_url") or "")

    export_id = await repository.create_export_row(db, user_id, "pdf", template_id, "pending")
    await db.commit()

    # fpdf2 is synchronous and CPU-bound: keep it off the event loop.
    try:
        file_bytes = await run_in_threadpool(
            generate_pdf_bytes, doc, accent_hex, template_id, lang
        )
    except Exception as exc:
        _log.exception("PDF render failed for template=%s: %s", template_id, exc)
        await repository.complete_export_row(db, export_id, "failed", "pdf_render_error")
        await db.commit()
        raise errors.api_error(500, errors.PDF_RENDER_FAILED, template_id=template_id) from exc

    endpoint = f"https://api.telegram.org/bot{settings.TOKEN}/sendDocument"
    file_name = f"resume_{template_id}_{user_id}.pdf"
    caption = t(lang, "caption")

    response = None
    last_error: Exception | None = None
    for _attempt in range(TELEGRAM_SEND_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=TELEGRAM_SEND_TIMEOUT) as client:
                response = await client.post(
                    endpoint,
                    data={"chat_id": str(user_id), "caption": caption},
                    files={"document": (file_name, file_bytes, "application/pdf")},
                )
        except httpx.HTTPError as exc:
            last_error = exc
            response = None
            continue
        if response.status_code < 500:
            break

    if response is None:
        _log.warning("telegram sendDocument failed: %s", last_error)
        await repository.complete_export_row(db, export_id, "failed", "telegram_network_error")
        await db.commit()
        raise errors.api_error(502, errors.TELEGRAM_SEND_FAILED)

    if response.status_code >= 400:
        await repository.complete_export_row(db, export_id, "failed", "telegram_http_error")
        await db.commit()
        raise errors.api_error(502, errors.TELEGRAM_SEND_FAILED)

    body = response.json() if response.content else {}
    if not body.get("ok"):
        await repository.complete_export_row(db, export_id, "failed", "telegram_api_error")
        await db.commit()
        raise errors.api_error(502, errors.TELEGRAM_SEND_FAILED)

    await repository.complete_export_row(db, export_id, "completed")
    await db.commit()

    return ResumeSendResponse(ok=True, status="SENT")


@router.post("/events", response_model=ResumeEventResponse)
@limiter.limit("60/minute")
async def track_resume_event(
    payload: ResumeEventRequest,
    request: Request,
    user=Depends(current_user),
) -> ResumeEventResponse:
    # No ``db`` here on purpose: the event is buffered and written in batches
    # (``webapp.core.event_queue``), so this handler touches SQLite not at all.
    event_name = payload.event_name.strip().lower()
    if event_name not in ALLOWED_EVENT_NAMES:
        raise errors.validation_error("event_name")

    step = (payload.step or "").strip().lower() or None
    if step is not None and step not in ALLOWED_EVENT_STEPS:
        raise errors.validation_error("step")

    track_event(int(user["user_id"]), event_name, step, payload.meta_json)
    return ResumeEventResponse(ok=True)
