"""Admin API for auto-post history and manual "post now" control.

History reads ``auto_post_log`` (one row per attempt, written by
``src/functions/auto_post_scheduler.py``). "Post now" does not touch Telegram
itself — it enqueues a ``bot_jobs`` row (kind ``auto_post.post_now``) that the
bot's ``bot_jobs_loop`` picks up, because only the bot process holds the
aiogram ``Bot`` instance. ``GET /admin/jobs/{id}`` lets the panel poll that
job to completion.

The existing ``GET/PATCH /api/admin/state`` (schedule settings) stay in
``admin_panel.py`` — this router only owns history/post-now/job status.
"""
import base64
import json

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from src.functions.bot_jobs import enqueue_job, find_pending_job
from webapp.core import errors
from webapp.core.audit import log_admin_action, client_ip
from webapp.core.auth import require_role
from webapp.core.confirm import require_confirmation
from webapp.core.database import get_db
from webapp.core.limiter import limiter

router = APIRouter(prefix="/admin", tags=["admin-autopost"])

#: Returned when a ``post_now`` is already waiting for the bot to pick it up.
JOB_ALREADY_QUEUED = "JOB_ALREADY_QUEUED"

POST_NOW_KIND = "auto_post.post_now"


class AutoPostLogItem(BaseModel):
    id: int
    uid: str | None = None
    channel: str | None = None
    message_id: int | None = None
    status: str
    error: str | None = None
    posted_at: int


class AutoPostHistoryResponse(BaseModel):
    items: list[AutoPostLogItem]
    next_cursor: str | None = None
    total: int | None = None


class PostNowRequest(BaseModel):
    uid: str | None = Field(default=None, max_length=64)


class PostNowResponse(BaseModel):
    job_id: int
    status: str = "queued"


class JobStatusResponse(BaseModel):
    id: int
    kind: str
    status: str
    result: dict | None = None
    error: str | None = None
    created_at: int
    started_at: int | None = None
    finished_at: int | None = None


def _encode_cursor(last_id: int) -> str:
    return base64.urlsafe_b64encode(str(int(last_id)).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception as exc:
        raise errors.validation_error("cursor") from exc


@router.get("/auto-post/history", response_model=AutoPostHistoryResponse)
@limiter.limit("60/minute")
async def auto_post_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    status: str | None = Query(default=None),
    admin=Depends(require_role("viewer")),
    db=Depends(get_db),
) -> AutoPostHistoryResponse:
    clauses: list[str] = []
    params: list = []
    if cursor:
        clauses.append("id < ?")
        params.append(_decode_cursor(cursor))
    if channel:
        clauses.append("channel = ?")
        params.append(channel)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    cursor_result = await db.execute(
        f"SELECT id, uid, channel, message_id, status, error, posted_at "
        f"FROM auto_post_log {where} ORDER BY id DESC LIMIT ?",
        (*params, limit),
    )
    rows = await cursor_result.fetchall()

    items = [
        AutoPostLogItem(
            id=int(row["id"]),
            uid=row["uid"],
            channel=row["channel"],
            message_id=row["message_id"],
            status=str(row["status"]),
            error=row["error"],
            posted_at=int(row["posted_at"]),
        )
        for row in rows
    ]
    next_cursor = _encode_cursor(items[-1].id) if len(items) == limit else None
    return AutoPostHistoryResponse(items=items, next_cursor=next_cursor, total=None)


@router.post("/auto-post/post-now", response_model=PostNowResponse)
@limiter.limit("10/minute")
async def post_now(
    request: Request,
    payload: PostNowRequest,
    admin=Depends(require_role("admin")),
    _confirmed=Depends(require_confirmation("autopost.post_now", [])),
    db=Depends(get_db),
) -> PostNowResponse:
    """Queue an immediate post; the bot process executes it via ``bot_jobs``."""
    actor_id = int(admin["user_id"])
    job_payload = {"uid": payload.uid} if payload.uid else {}

    # The bot polls every 5 s, so an impatient second click (or two admins at
    # once) would otherwise queue a second post and put two vacancies in the
    # channel back to back.
    existing = await find_pending_job(db, POST_NOW_KIND)
    if existing is not None:
        raise errors.api_error(409, JOB_ALREADY_QUEUED, job_id=existing)

    job_id = await enqueue_job(db, POST_NOW_KIND, job_payload, created_by=actor_id)

    await log_admin_action(
        db,
        actor_id=actor_id,
        action="autopost.post_now",
        target_type="bot_job",
        target_id=str(job_id),
        payload=job_payload,
        ip=client_ip(request),
    )
    await db.commit()
    return PostNowResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
@limiter.limit("60/minute")
async def job_status(
    request: Request,
    job_id: int,
    admin=Depends(require_role("viewer")),
    db=Depends(get_db),
) -> JobStatusResponse:
    cursor = await db.execute(
        "SELECT id, kind, status, result_json, error, created_at, started_at, finished_at "
        "FROM bot_jobs WHERE id = ?",
        (job_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise errors.not_found("job")

    result: dict | None = None
    if row["result_json"]:
        try:
            parsed = json.loads(row["result_json"])
            if isinstance(parsed, dict):
                result = parsed
        except Exception:
            result = None

    return JobStatusResponse(
        id=int(row["id"]),
        kind=str(row["kind"]),
        status=str(row["status"]),
        result=result,
        error=row["error"],
        created_at=int(row["created_at"]),
        started_at=row["started_at"],
        finished_at=row["finished_at"],
    )
