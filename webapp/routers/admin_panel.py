import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.identity import resolve_user_id_from_init_data

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request) -> int:
    settings = get_settings()
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    if not init_data:
        raise HTTPException(status_code=401, detail="Telegram initData required")

    user_id = resolve_user_id_from_init_data(init_data, settings.TOKEN)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid initData")

    if user_id not in settings.admin_ids_set:
        raise HTTPException(status_code=403, detail="Admin only")

    return user_id


class AdminStateResponse(BaseModel):
    is_admin: bool
    auto_post_enabled: bool
    auto_post_channel: str
    auto_post_min_salary: int
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
    auto_post_enabled: bool | None = None
    auto_post_channel: str | None = None
    auto_post_min_salary: int | None = Field(default=None, ge=0)
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


@router.get("/state", response_model=AdminStateResponse)
async def get_admin_state(request: Request, db=Depends(get_db)) -> AdminStateResponse:
    _require_admin(request)
    cursor = await db.execute(
        "SELECT auto_post_enabled, auto_post_channel, auto_post_min_salary, referral_enabled, referral_required_count, "
        "pro_price, referral_reward, pro_min_salary, "
        "resume_target_creation_minutes, resume_target_completion_rate, "
        "resume_target_send_success_rate, resume_target_export_success_rate "
        "FROM webapp_admin_settings WHERE singleton = 1"
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="Settings not initialized")

    return AdminStateResponse(
        is_admin=True,
        auto_post_enabled=bool(int(row["auto_post_enabled"] or 0)),
        auto_post_channel=str(row["auto_post_channel"] or ""),
        auto_post_min_salary=int(row["auto_post_min_salary"] or 0),
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


@router.patch("/state", response_model=AdminStateResponse)
async def patch_admin_state(payload: AdminSettingsPatch, request: Request, db=Depends(get_db)) -> AdminStateResponse:
    _require_admin(request)

    if payload.auto_post_enabled is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET auto_post_enabled = ? WHERE singleton = 1",
            (1 if payload.auto_post_enabled else 0,),
        )
    if payload.auto_post_channel is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET auto_post_channel = ? WHERE singleton = 1",
            (payload.auto_post_channel.strip(),),
        )
    if payload.auto_post_min_salary is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET auto_post_min_salary = ? WHERE singleton = 1",
            (int(payload.auto_post_min_salary),),
        )
    if payload.referral_enabled is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET referral_enabled = ? WHERE singleton = 1",
            (1 if payload.referral_enabled else 0,),
        )
    if payload.referral_required_count is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET referral_required_count = ? WHERE singleton = 1",
            (int(payload.referral_required_count),),
        )
    if payload.pro_price is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET pro_price = ? WHERE singleton = 1",
            (int(payload.pro_price),),
        )
    if payload.referral_reward is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET referral_reward = ? WHERE singleton = 1",
            (int(payload.referral_reward),),
        )
    if payload.pro_min_salary is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET pro_min_salary = ? WHERE singleton = 1",
            (int(payload.pro_min_salary),),
        )
    if payload.resume_target_creation_minutes is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET resume_target_creation_minutes = ? WHERE singleton = 1",
            (float(payload.resume_target_creation_minutes),),
        )
    if payload.resume_target_completion_rate is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET resume_target_completion_rate = ? WHERE singleton = 1",
            (float(payload.resume_target_completion_rate),),
        )
    if payload.resume_target_send_success_rate is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET resume_target_send_success_rate = ? WHERE singleton = 1",
            (float(payload.resume_target_send_success_rate),),
        )
    if payload.resume_target_export_success_rate is not None:
        await db.execute(
            "UPDATE webapp_admin_settings SET resume_target_export_success_rate = ? WHERE singleton = 1",
            (float(payload.resume_target_export_success_rate),),
        )

    await db.commit()
    return await get_admin_state(request, db)


@router.get("/resume-metrics", response_model=AdminResumeMetricsResponse)
async def get_resume_metrics(request: Request, db=Depends(get_db)) -> AdminResumeMetricsResponse:
    _require_admin(request)
    import time

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
async def get_resume_funnel(request: Request, db=Depends(get_db), hours: int = 24) -> AdminFunnelResponse:
    _require_admin(request)
    import time

    window_hours = min(max(int(hours), 1), 168)
    since = int(time.time()) - window_hours * 60 * 60
    steps = ["basic", "experience", "education", "skills", "summary", "template", "final"]

    metrics: list[AdminFunnelStepMetric] = []
    for step in steps:
        entered_cursor = await db.execute(
            """
            SELECT COUNT(DISTINCT user_id) AS c
            FROM resume_events
            WHERE created_at >= ? AND step = ?
            """,
            (since, step),
        )
        entered_row = await entered_cursor.fetchone()
        entered_users = int((entered_row["c"] if entered_row else 0) or 0)

        if step == "final":
            completed_cursor = await db.execute(
                """
                SELECT COUNT(DISTINCT user_id) AS c
                FROM resume_events
                WHERE created_at >= ?
                  AND event_name IN ('send_success','export_success')
                """,
                (since,),
            )
        else:
            completed_cursor = await db.execute(
                """
                SELECT COUNT(DISTINCT user_id) AS c
                FROM resume_events
                WHERE created_at >= ?
                  AND step = ?
                  AND event_name IN ('save_success','autosave_success')
                """,
                (since, step),
            )
        completed_row = await completed_cursor.fetchone()
        completed_users = int((completed_row["c"] if completed_row else 0) or 0)
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
async def inspect_resume_user(user_id: int, request: Request, db=Depends(get_db)) -> AdminResumeUserInspectResponse:
    _require_admin(request)
    cursor = await db.execute(
        "SELECT user_id, first_name, username FROM users WHERE user_id = ?",
        (int(user_id),),
    )
    user_row = await cursor.fetchone()
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

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
async def get_resume_diagnostics(request: Request, db=Depends(get_db), hours: int = 24) -> AdminDiagnosticsResponse:
    _require_admin(request)
    import time

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
async def get_resume_goals(request: Request, db=Depends(get_db), hours: int = 168) -> AdminGoalsResponse:
    _require_admin(request)
    import time

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
