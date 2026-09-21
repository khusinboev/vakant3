import json
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from webapp.core import errors
from webapp.core.audit import client_ip, log_admin_action
from webapp.core.auth import require_admin, require_role
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from webapp.routers import admin_admins

router = APIRouter(prefix="/admin", tags=["admin"])

# Roster management and confirmation tokens live in their own module but share
# this prefix, so webapp/main.py needs no change.
router.include_router(admin_admins.router)

#: Reading the panel is open to every admin role; changing settings is not.
require_settings_writer = require_role("admin")

TZ_UZB = timezone(timedelta(hours=5))


class AutoPostScheduleItem(BaseModel):
    ts: int
    done: bool
    uid: str | None
    time_str: str  # HH:MM (UTC+5)


class AdminStateResponse(BaseModel):
    is_admin: bool
    role: str
    version: int
    auto_post_enabled: bool
    auto_post_channel: str
    auto_post_min_salary: int
    auto_post_per_day_min: int
    auto_post_per_day_max: int
    channel_lang: str
    referral_enabled: bool
    referral_required_count: int
    pro_price: int
    referral_reward: int
    pro_min_salary: int
    resume_target_creation_minutes: float
    resume_target_completion_rate: float
    resume_target_send_success_rate: float
    resume_target_export_success_rate: float


class AdminResumeMetricsResponse(BaseModel):
    opened_24h: int
    ready_24h: int
    save_success_24h: int
    save_error_24h: int
    send_success_24h: int
    send_error_24h: int
    export_success_24h: int
    export_error_24h: int
    unique_users_24h: int
    avg_ttfi_ms: int
    avg_save_latency_ms: int
    avg_send_latency_ms: int
    avg_export_latency_ms: int


class AdminSettingsPatch(BaseModel):
    #: Optimistic concurrency: when set and stale -> 409 SETTINGS_CONFLICT.
    expected_version: int | None = Field(default=None, ge=0)
    auto_post_enabled: bool | None = None
    auto_post_channel: str | None = None
    auto_post_min_salary: int | None = Field(default=None, ge=0)
    auto_post_per_day_min: int | None = Field(default=None, ge=1, le=24)
    auto_post_per_day_max: int | None = Field(default=None, ge=1, le=24)
    channel_lang: str | None = Field(default=None, pattern="^(uz|ru|en)$")
    referral_enabled: bool | None = None
    referral_required_count: int | None = Field(default=None, ge=0)
    pro_price: int | None = Field(default=None, ge=0)
    referral_reward: int | None = Field(default=None, ge=0)
    pro_min_salary: int | None = Field(default=None, ge=0)
    resume_target_creation_minutes: float | None = Field(default=None, ge=0)
    resume_target_completion_rate: float | None = Field(default=None, ge=0)
    resume_target_send_success_rate: float | None = Field(default=None, ge=0)
    resume_target_export_success_rate: float | None = Field(default=None, ge=0)


class AdminFunnelStepMetric(BaseModel):
    step: str
    entered_users: int
    completed_users: int
    dropoff_users: int
    completion_rate: float


class AdminFunnelResponse(BaseModel):
    window_hours: int
    steps: list[AdminFunnelStepMetric]


class AdminResumeUserEvent(BaseModel):
    event_name: str
    step: str | None = None
    created_at: int


class AdminResumeUserInspectResponse(BaseModel):
    user_id: int
    first_name: str
    username: str
    has_resume: bool
    selected_template: str
    updated_at: int | None = None
    profile_preview: dict
    recent_events: list[AdminResumeUserEvent]


class AdminDiagnosticsItem(BaseModel):
    source: str
    status: str
    error_text: str
    count_24h: int
    last_seen_at: int


class AdminDiagnosticsResponse(BaseModel):
    items: list[AdminDiagnosticsItem]


class AdminGoalsResponse(BaseModel):
    window_hours: int
    opened_users: int
    completed_users: int
    send_attempts: int
    pdf_export_attempts: int
    median_creation_minutes: float
    completion_rate: float
    send_success_rate: float
    pdf_export_success_rate: float
    creation_time_target_minutes: float
    completion_rate_target: float
    send_success_rate_target: float
    pdf_export_success_rate_target: float
    creation_time_ok: bool
    completion_rate_ok: bool
    send_success_rate_ok: bool
    pdf_export_success_rate_ok: bool


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


#: patch field -> (column, coercion). The column list is the whole editable
#: surface of the settings singleton; PATCH writes it in ONE statement.
_SETTING_FIELDS: dict[str, object] = {
    "auto_post_enabled": lambda v: 1 if v else 0,
    "auto_post_channel": lambda v: str(v).strip(),
    "auto_post_min_salary": lambda v: int(v),
    "auto_post_per_day_min": lambda v: max(1, min(24, int(v))),
    "auto_post_per_day_max": lambda v: max(1, min(24, int(v))),
    "channel_lang": lambda v: str(v),
    "referral_enabled": lambda v: 1 if v else 0,
    "referral_required_count": lambda v: int(v),
    "pro_price": lambda v: int(v),
    "referral_reward": lambda v: int(v),
    "pro_min_salary": lambda v: int(v),
    "resume_target_creation_minutes": lambda v: float(v),
    "resume_target_completion_rate": lambda v: float(v),
    "resume_target_send_success_rate": lambda v: float(v),
    "resume_target_export_success_rate": lambda v: float(v),
}

_STATE_COLUMNS = ", ".join([*_SETTING_FIELDS.keys(), "version"])


async def _settings_row(db):
    cursor = await db.execute(
        f"SELECT {_STATE_COLUMNS} FROM webapp_admin_settings WHERE singleton = 1"
    )
    row = await cursor.fetchone()
    if not row:
        raise errors.api_error(500, errors.SERVER_MISCONFIGURED)
    return row


def _state_response(row, role: str) -> AdminStateResponse:
    return AdminStateResponse(
        is_admin=True,
        role=role,
        version=int(row["version"] or 0),
        auto_post_enabled=bool(int(row["auto_post_enabled"] or 0)),
        auto_post_channel=str(row["auto_post_channel"] or ""),
        auto_post_min_salary=int(row["auto_post_min_salary"] or 0),
        auto_post_per_day_min=int(row["auto_post_per_day_min"] or 4),
        auto_post_per_day_max=int(row["auto_post_per_day_max"] or 8),
        channel_lang=str(row["channel_lang"] or "uz"),
        referral_enabled=bool(int(row["referral_enabled"] or 0)),
        referral_required_count=int(row["referral_required_count"] or 0),
        pro_price=int(row["pro_price"] or 10000),
        referral_reward=int(row["referral_reward"] or 2000),
        pro_min_salary=int(row["pro_min_salary"] or 8000000),
        resume_target_creation_minutes=float(row["resume_target_creation_minutes"] or 8),
        resume_target_completion_rate=float(row["resume_target_completion_rate"] or 60),
        resume_target_send_success_rate=float(row["resume_target_send_success_rate"] or 98),
        resume_target_export_success_rate=float(row["resume_target_export_success_rate"] or 99),
    )


@router.get("/state", response_model=AdminStateResponse)
@limiter.limit("60/minute")
async def get_admin_state(
    request: Request,
    admin=Depends(require_admin),
    db=Depends(get_db),
) -> AdminStateResponse:
    return _state_response(await _settings_row(db), str(admin["role"]))


@router.patch("/state", response_model=AdminStateResponse)
@limiter.limit("10/minute")
async def patch_admin_state(
    request: Request,
    payload: AdminSettingsPatch,
    admin=Depends(require_settings_writer),
    db=Depends(get_db),
) -> AdminStateResponse:
    """Write every changed field in one UPDATE guarded by ``version``.

    Two admins editing the panel at once used to silently overwrite each
    other: the old handler issued one UPDATE per field with no read-modify
    guard. Now the row carries a ``version`` that the UPDATE both matches on
    and increments, so the loser gets 409 SETTINGS_CONFLICT with the current
    version instead of a half-applied merge. The bot uses the same counter to
    drop its 60 s settings cache.
    """
    current = await _settings_row(db)
    version = int(current["version"] or 0)
    if payload.expected_version is not None and int(payload.expected_version) != version:
        raise errors.api_error(409, errors.SETTINGS_CONFLICT, version=version)

    provided = payload.model_dump(exclude_unset=True)
    provided.pop("expected_version", None)

    # auto_post_per_day_min must stay <= max, otherwise the bot's random.randint() raises.
    if provided.get("auto_post_per_day_min") is not None or provided.get("auto_post_per_day_max") is not None:
        new_min = int(provided.get("auto_post_per_day_min") or current["auto_post_per_day_min"] or 4)
        new_max = int(provided.get("auto_post_per_day_max") or current["auto_post_per_day_max"] or 8)
        if new_min > new_max:
            raise errors.validation_error("auto_post_per_day_min")

    updates: dict[str, object] = {}
    diff: dict[str, list] = {}
    for field, coerce in _SETTING_FIELDS.items():
        value = provided.get(field)
        if value is None:
            continue
        new_value = coerce(value)  # type: ignore[operator]
        updates[field] = new_value
        old_value = current[field]
        if isinstance(new_value, float):
            changed = abs(float(old_value or 0) - new_value) > 1e-9
        else:
            changed = old_value != new_value
        if changed:
            diff[field] = [old_value, new_value]

    if not updates:
        return _state_response(current, str(admin["role"]))

    assignments = ", ".join(f"{column} = ?" for column in updates)
    cursor = await db.execute(
        f"UPDATE webapp_admin_settings SET {assignments}, version = version + 1 "
        "WHERE singleton = 1 AND version = ?",
        (*updates.values(), version),
    )
    if cursor.rowcount == 0:
        raise errors.api_error(409, errors.SETTINGS_CONFLICT, version=int((await _settings_row(db))["version"] or 0))

    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="settings.patch",
        target_type="settings",
        target_id="1",
        payload={"diff": diff, "version": version + 1},
        ip=client_ip(request),
    )
    await db.commit()

    return _state_response(await _settings_row(db), str(admin["role"]))


class AutoPostScheduleResponse(BaseModel):
    schedule: list[AutoPostScheduleItem]
    posted_today: int
    total_today: int


@router.get("/auto-post-schedule", response_model=AutoPostScheduleResponse)
@limiter.limit("60/minute")
async def get_auto_post_schedule(
    request: Request,
    admin=Depends(require_admin),
    db=Depends(get_db),
) -> AutoPostScheduleResponse:
    cursor = await db.execute(
        "SELECT auto_post_scheduled_times_json FROM webapp_admin_settings WHERE singleton = 1"
    )
    row = await cursor.fetchone()
    raw = str(row["auto_post_scheduled_times_json"] or "[]") if row else "[]"
    try:
        items: list[dict] = json.loads(raw)
    except Exception:
        items = []

    now_uzb = datetime.now(TZ_UZB)
    today_start = int(now_uzb.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    today_items = [item for item in items if int(item.get("ts", 0)) >= today_start]

    result: list[AutoPostScheduleItem] = []
    for item in today_items:
        ts = int(item.get("ts", 0))
        dt = datetime.fromtimestamp(ts, tz=TZ_UZB)
        result.append(AutoPostScheduleItem(
            ts=ts,
            done=bool(item.get("done", False)),
            uid=item.get("uid") or None,
            time_str=dt.strftime("%H:%M"),
        ))

    posted_today = sum(1 for r in result if r.done and r.uid)
    return AutoPostScheduleResponse(
        schedule=result,
        posted_today=posted_today,
        total_today=len(result),
    )


@router.get("/resume-metrics", response_model=AdminResumeMetricsResponse)
@limiter.limit("60/minute")
async def get_resume_metrics(
    request: Request,
    admin=Depends(require_admin),
    db=Depends(get_db),
) -> AdminResumeMetricsResponse:
    since = int(time.time()) - 24 * 60 * 60
    cursor = await db.execute(
        """
        SELECT
            SUM(CASE WHEN event_name = 'builder_opened' THEN 1 ELSE 0 END) AS opened_24h,
            SUM(CASE WHEN event_name = 'builder_ready' THEN 1 ELSE 0 END) AS ready_24h,
            SUM(CASE WHEN event_name = 'save_success' THEN 1 ELSE 0 END) AS save_success_24h,
            SUM(CASE WHEN event_name = 'save_error' THEN 1 ELSE 0 END) AS save_error_24h,
            SUM(CASE WHEN event_name = 'send_success' THEN 1 ELSE 0 END) AS send_success_24h,
            SUM(CASE WHEN event_name = 'send_error' THEN 1 ELSE 0 END) AS send_error_24h,
            SUM(CASE WHEN event_name = 'export_success' THEN 1 ELSE 0 END) AS export_success_24h,
            SUM(CASE WHEN event_name = 'export_error' THEN 1 ELSE 0 END) AS export_error_24h,
            AVG(CASE WHEN event_name = 'builder_ready' THEN CAST(json_extract(meta_json, '$.ttfi_ms') AS REAL) END) AS avg_ttfi_ms,
            AVG(CASE WHEN event_name IN ('save_success','save_error') THEN CAST(json_extract(meta_json, '$.latency_ms') AS REAL) END) AS avg_save_latency_ms,
            AVG(CASE WHEN event_name IN ('send_success','send_error') THEN CAST(json_extract(meta_json, '$.latency_ms') AS REAL) END) AS avg_send_latency_ms,
            AVG(CASE WHEN event_name IN ('export_success','export_error') THEN CAST(json_extract(meta_json, '$.latency_ms') AS REAL) END) AS avg_export_latency_ms,
            COUNT(DISTINCT user_id) AS unique_users_24h
        FROM resume_events
        WHERE created_at >= ?
        """,
        (since,),
    )
    row = await cursor.fetchone()
    return AdminResumeMetricsResponse(
        opened_24h=int((row["opened_24h"] if row else 0) or 0),
        ready_24h=int((row["ready_24h"] if row else 0) or 0),
        save_success_24h=int((row["save_success_24h"] if row else 0) or 0),
        save_error_24h=int((row["save_error_24h"] if row else 0) or 0),
        send_success_24h=int((row["send_success_24h"] if row else 0) or 0),
        send_error_24h=int((row["send_error_24h"] if row else 0) or 0),
        export_success_24h=int((row["export_success_24h"] if row else 0) or 0),
        export_error_24h=int((row["export_error_24h"] if row else 0) or 0),
        unique_users_24h=int((row["unique_users_24h"] if row else 0) or 0),
        avg_ttfi_ms=int((row["avg_ttfi_ms"] if row else 0) or 0),
        avg_save_latency_ms=int((row["avg_save_latency_ms"] if row else 0) or 0),
        avg_send_latency_ms=int((row["avg_send_latency_ms"] if row else 0) or 0),
        avg_export_latency_ms=int((row["avg_export_latency_ms"] if row else 0) or 0),
    )


@router.get("/resume-funnel", response_model=AdminFunnelResponse)
@limiter.limit("60/minute")
async def get_resume_funnel(
    request: Request,
    admin=Depends(require_admin),
    db=Depends(get_db),
    hours: int = 24,
) -> AdminFunnelResponse:
    window_hours = min(max(int(hours), 1), 168)
    since = int(time.time()) - window_hours * 60 * 60
    steps = ["basic", "experience", "education", "skills", "summary", "template", "final"]

    # One pass over the window instead of two queries per step.
    per_step_cursor = await db.execute(
        """
        SELECT
            step,
            COUNT(DISTINCT user_id) AS entered_users,
            COUNT(DISTINCT CASE
                WHEN event_name IN ('save_success','autosave_success') THEN user_id
            END) AS completed_users
        FROM resume_events
        WHERE created_at >= ? AND step IS NOT NULL
        GROUP BY step
        """,
        (since,),
    )
    per_step = {
        str(row["step"]): (int(row["entered_users"] or 0), int(row["completed_users"] or 0))
        for row in await per_step_cursor.fetchall()
    }

    final_cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT user_id) AS c
        FROM resume_events
        WHERE created_at >= ? AND event_name IN ('send_success','export_success')
        """,
        (since,),
    )
    final_row = await final_cursor.fetchone()
    final_completed = int((final_row["c"] if final_row else 0) or 0)

    metrics: list[AdminFunnelStepMetric] = []
    for step in steps:
        entered_users, completed_users = per_step.get(step, (0, 0))
        if step == "final":
            completed_users = final_completed
        dropoff_users = max(entered_users - completed_users, 0)
        completion_rate = round((completed_users / entered_users) * 100.0, 2) if entered_users else 0.0

        metrics.append(
            AdminFunnelStepMetric(
                step=step,
                entered_users=entered_users,
                completed_users=completed_users,
                dropoff_users=dropoff_users,
                completion_rate=completion_rate,
            )
        )

    return AdminFunnelResponse(window_hours=window_hours, steps=metrics)


@router.get("/resume-user/{user_id}", response_model=AdminResumeUserInspectResponse)
@limiter.limit("60/minute")
async def inspect_resume_user(
    request: Request,
    user_id: int,
    admin=Depends(require_admin),
    db=Depends(get_db),
) -> AdminResumeUserInspectResponse:
    cursor = await db.execute(
        "SELECT user_id, first_name, username FROM users WHERE user_id = ?",
        (int(user_id),),
    )
    user_row = await cursor.fetchone()
    if not user_row:
        raise errors.not_found("user")

    profile_cursor = await db.execute(
        "SELECT profile_json, selected_template, updated_at FROM resume_profiles WHERE user_id = ?",
        (int(user_id),),
    )
    profile_row = await profile_cursor.fetchone()

    has_resume = profile_row is not None
    selected_template = str(profile_row["selected_template"] or "clean") if profile_row else "clean"
    updated_at = int(profile_row["updated_at"] or 0) if profile_row else None
    profile_preview: dict = {}
    if profile_row:
        try:
            raw = profile_row["profile_json"]
            parsed = raw if isinstance(raw, dict) else json.loads(str(raw or "{}"))
            profile_preview = {
                "full_name": str(parsed.get("full_name") or ""),
                "position": str(parsed.get("position") or ""),
                "skills_count": len(parsed.get("skills") or []),
                "languages_count": len(parsed.get("languages") or []),
                "experiences_count": len(parsed.get("experiences") or []),
                "educations_count": len(parsed.get("educations") or []),
                "summary_length": len(str(parsed.get("summary") or "")),
            }
        except Exception:
            profile_preview = {}

    events_cursor = await db.execute(
        """
        SELECT event_name, step, created_at
        FROM resume_events
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 20
        """,
        (int(user_id),),
    )
    events_rows = await events_cursor.fetchall()

    return AdminResumeUserInspectResponse(
        user_id=int(user_row["user_id"]),
        first_name=str(user_row["first_name"] or ""),
        username=str(user_row["username"] or ""),
        has_resume=has_resume,
        selected_template=selected_template,
        updated_at=updated_at,
        profile_preview=profile_preview,
        recent_events=[
            AdminResumeUserEvent(
                event_name=str(row["event_name"] or ""),
                step=str(row["step"] or "") or None,
                created_at=int(row["created_at"] or 0),
            )
            for row in events_rows
        ],
    )


@router.get("/resume-diagnostics", response_model=AdminDiagnosticsResponse)
@limiter.limit("60/minute")
async def get_resume_diagnostics(
    request: Request,
    admin=Depends(require_admin),
    db=Depends(get_db),
    hours: int = 24,
) -> AdminDiagnosticsResponse:
    window_hours = min(max(int(hours), 1), 168)
    since = int(time.time()) - window_hours * 60 * 60

    exports_cursor = await db.execute(
        """
        SELECT
            'export' AS source,
            status,
            COALESCE(error_text, 'unknown') AS error_text,
            COUNT(*) AS count_24h,
            MAX(COALESCE(completed_at, created_at)) AS last_seen_at
        FROM resume_exports
        WHERE created_at >= ?
          AND status = 'failed'
        GROUP BY status, COALESCE(error_text, 'unknown')
        ORDER BY count_24h DESC
        """,
        (since,),
    )
    export_rows = await exports_cursor.fetchall()

    events_cursor = await db.execute(
        """
        SELECT
            CASE
                WHEN event_name LIKE 'send_%' THEN 'send'
                WHEN event_name LIKE 'export_%' THEN 'export'
                ELSE 'event'
            END AS source,
            'failed' AS status,
            event_name AS error_text,
            COUNT(*) AS count_24h,
            MAX(created_at) AS last_seen_at
        FROM resume_events
        WHERE created_at >= ?
          AND event_name IN ('send_error','export_error')
        GROUP BY event_name
        ORDER BY count_24h DESC
        """,
        (since,),
    )
    event_rows = await events_cursor.fetchall()

    items = [
        AdminDiagnosticsItem(
            source=str(row["source"] or ""),
            status=str(row["status"] or "failed"),
            error_text=str(row["error_text"] or "unknown"),
            count_24h=int(row["count_24h"] or 0),
            last_seen_at=int(row["last_seen_at"] or 0),
        )
        for row in [*export_rows, *event_rows]
    ]
    items.sort(key=lambda x: (x.count_24h, x.last_seen_at), reverse=True)
    return AdminDiagnosticsResponse(items=items)


@router.get("/resume-goals", response_model=AdminGoalsResponse)
@limiter.limit("60/minute")
async def get_resume_goals(
    request: Request,
    admin=Depends(require_admin),
    db=Depends(get_db),
    hours: int = 168,
) -> AdminGoalsResponse:
    window_hours = min(max(int(hours), 24), 24 * 30)
    since = int(time.time()) - window_hours * 60 * 60

    settings_cursor = await db.execute(
        """
        SELECT
            resume_target_creation_minutes,
            resume_target_completion_rate,
            resume_target_send_success_rate,
            resume_target_export_success_rate
        FROM webapp_admin_settings
        WHERE singleton = 1
        """
    )
    settings_row = await settings_cursor.fetchone()

    target_creation_minutes = float((settings_row["resume_target_creation_minutes"] if settings_row else 8) or 8)
    target_completion_rate = float((settings_row["resume_target_completion_rate"] if settings_row else 60) or 60)
    target_send_success_rate = float((settings_row["resume_target_send_success_rate"] if settings_row else 98) or 98)
    target_export_success_rate = float((settings_row["resume_target_export_success_rate"] if settings_row else 99) or 99)

    opened_cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT user_id) AS c
        FROM resume_events
        WHERE created_at >= ? AND event_name = 'builder_opened'
        """,
        (since,),
    )
    opened_row = await opened_cursor.fetchone()
    opened_users = int((opened_row["c"] if opened_row else 0) or 0)

    completed_cursor = await db.execute(
        """
        SELECT COUNT(DISTINCT user_id) AS c
        FROM resume_events
        WHERE created_at >= ?
          AND (
            (step = 'template' AND event_name IN ('save_success','autosave_success'))
            OR event_name IN ('send_success','export_success')
          )
        """,
        (since,),
    )
    completed_row = await completed_cursor.fetchone()
    completed_users = int((completed_row["c"] if completed_row else 0) or 0)

    send_cursor = await db.execute(
        """
        SELECT
            SUM(CASE WHEN event_name = 'send_success' THEN 1 ELSE 0 END) AS send_success,
            SUM(CASE WHEN event_name = 'send_error' THEN 1 ELSE 0 END) AS send_error
        FROM resume_events
        WHERE created_at >= ?
        """,
        (since,),
    )
    send_row = await send_cursor.fetchone()
    send_success = int((send_row["send_success"] if send_row else 0) or 0)
    send_error = int((send_row["send_error"] if send_row else 0) or 0)
    send_attempts = send_success + send_error

    export_cursor = await db.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS export_success,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS export_failed
        FROM resume_exports
        WHERE created_at >= ?
          AND fmt = 'pdf'
        """,
        (since,),
    )
    export_row = await export_cursor.fetchone()
    export_success = int((export_row["export_success"] if export_row else 0) or 0)
    export_failed = int((export_row["export_failed"] if export_row else 0) or 0)
    pdf_export_attempts = export_success + export_failed

    timings_cursor = await db.execute(
        """
        SELECT
            user_id,
            MIN(CASE WHEN event_name = 'builder_opened' THEN created_at END) AS opened_at,
            MIN(CASE WHEN event_name IN ('save_success','autosave_success','send_success','export_success') THEN created_at END) AS done_at
        FROM resume_events
        WHERE created_at >= ?
        GROUP BY user_id
        """,
        (since,),
    )
    timing_rows = await timings_cursor.fetchall()
    durations_minutes: list[float] = []
    for row in timing_rows:
        opened_at = int(row["opened_at"] or 0)
        done_at = int(row["done_at"] or 0)
        if opened_at > 0 and done_at >= opened_at:
            durations_minutes.append((done_at - opened_at) / 60.0)

    median_creation_minutes = round(_median(durations_minutes), 2)
    completion_rate = round((completed_users / opened_users) * 100.0, 2) if opened_users else 0.0
    send_success_rate = round((send_success / send_attempts) * 100.0, 2) if send_attempts else 0.0
    pdf_export_success_rate = round((export_success / pdf_export_attempts) * 100.0, 2) if pdf_export_attempts else 0.0

    return AdminGoalsResponse(
        window_hours=window_hours,
        opened_users=opened_users,
        completed_users=completed_users,
        send_attempts=send_attempts,
        pdf_export_attempts=pdf_export_attempts,
        median_creation_minutes=median_creation_minutes,
        completion_rate=completion_rate,
        send_success_rate=send_success_rate,
        pdf_export_success_rate=pdf_export_success_rate,
        creation_time_target_minutes=target_creation_minutes,
        completion_rate_target=target_completion_rate,
        send_success_rate_target=target_send_success_rate,
        pdf_export_success_rate_target=target_export_success_rate,
        creation_time_ok=median_creation_minutes > 0 and median_creation_minutes <= target_creation_minutes,
        completion_rate_ok=completion_rate >= target_completion_rate,
        send_success_rate_ok=send_success_rate >= target_send_success_rate,
        pdf_export_success_rate_ok=pdf_export_success_rate >= target_export_success_rate,
    )
