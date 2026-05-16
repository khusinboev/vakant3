from fastapi import APIRouter, Depends, Header, HTTPException, Request

from config import bot
from src.functions.cache import cache_get, cache_set, make_cache_key
from src.functions.functions import normalize_osonish_field_id
from src.functions.scraping import fetch_osonish_detail, fetch_osonish_list
from src.functions.vacancy_format import format_vacancy_message_html, normalize_vacancy_detail
from webapp.core.database import get_db
from webapp.core.config import get_settings
from webapp.core.identity import resolve_user_id_from_init_data
from webapp.core.limiter import limiter
from webapp.core.referral_gate import get_referral_gate_state, raise_if_referral_locked
from webapp.core.session import decode_session_token, get_current_user
from webapp.models.schemas import JobsSearchResponse, VacancyDetailResponse, VacancyItem

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _uid_to_raw_id(uid: str) -> int:
    if not uid.startswith("osonish_"):
        raise HTTPException(status_code=404, detail="Only osonish vacancies are supported")
    try:
        return int(uid.split("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid vacancy uid") from exc


async def _get_auth_user_id(authorization: str | None) -> int | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_session_token(token)
        return int(payload.get("uid", 0)) or None
    except Exception:
        return None


def _get_init_data_user_id(request: Request) -> int | None:
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    if not init_data:
        return None
    settings = get_settings()
    return resolve_user_id_from_init_data(init_data, settings.TOKEN)


@router.get("/search", response_model=JobsSearchResponse)
@limiter.limit("30/minute")
async def search_jobs(
    request: Request,
    page: int = 1,
    q: str = "",
    money: int = 0,
    region_soato: str = "",
    district_soato: str = "",
    specs: str = "",
    sort_key: str = "",
    sort_type: str = "",
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> JobsSearchResponse:
    request_user_id = await _get_auth_user_id(authorization) or _get_init_data_user_id(request)
    if request_user_id:
        gate_state = await get_referral_gate_state(db, request_user_id)
        raise_if_referral_locked(gate_state)

    field_id = normalize_osonish_field_id(specs)
    cache_key = make_cache_key(
        "webapp_jobs_search",
        page=page,
        q=q or "",
        money=money or 0,
        region_soato=region_soato or "",
        district_soato=district_soato or "",
        specs=specs or "",
        sort_key=sort_key or "",
        sort_type=sort_type or "",
    )
    cached = await cache_get(cache_key)

    if isinstance(cached, dict) and isinstance(cached.get("items"), list):
        vacancies_raw = cached["items"]
        last_page = int(cached.get("last_page") or 1)
    else:
        vacancies, last_page = await fetch_osonish_list(
            page=page,
            salary=money or 0,
            soato_region=region_soato or "",
            soato_district=district_soato or "",
            mmk_group_field_id=field_id,
            sort_key=sort_key or "",
            sort_type=sort_type or "",
            search=q or "",
        )
        vacancies_raw = [
            {
                "uid": item.uid,
                "title": item.title,
                "company": item.company,
                "salary_text": item.salary_text,
                "location": item.location,
                "district": item.district,
                "posted_at": item.posted_at,
                "max_salary": item.max_salary,
            }
            for item in vacancies
        ]
        await cache_set(cache_key, {"items": vacancies_raw, "last_page": last_page}, ttl=30 * 60)

    user_id = request_user_id
    saved_ids: set[int] = set()
    is_user_pro = False
    pro_min_salary = 8_000_000

    # Fetch pro settings and user status in parallel if user is identified
    if user_id:
        cursor_settings = await db.execute(
            "SELECT pro_min_salary FROM webapp_admin_settings WHERE singleton = 1"
        )
        settings_row = await cursor_settings.fetchone()
        if settings_row:
            pro_min_salary = int(settings_row["pro_min_salary"] or 8_000_000)

        cursor_user = await db.execute(
            "SELECT user_pro FROM users WHERE user_id = ?", (user_id,)
        )
        user_row = await cursor_user.fetchone()
        if user_row:
            is_user_pro = bool(int(user_row["user_pro"] or 0))
    else:
        cursor_settings = await db.execute(
            "SELECT pro_min_salary FROM webapp_admin_settings WHERE singleton = 1"
        )
        settings_row = await cursor_settings.fetchone()
        if settings_row:
            pro_min_salary = int(settings_row["pro_min_salary"] or 8_000_000)
    if user_id and vacancies_raw:
        raw_ids = []
        for vacancy in vacancies_raw:
            uid = str(vacancy.get("uid", ""))
            if uid.startswith("osonish_"):
                try:
                    raw_ids.append(int(uid.split("_", 1)[1]))
                except (IndexError, ValueError):
                    continue

        if raw_ids:
            placeholders = ",".join("?" for _ in raw_ids)
            cursor = await db.execute(
                f"SELECT save_id FROM saves WHERE user_id = ? AND save_id IN ({placeholders})",
                tuple([user_id, *raw_ids]),
            )
            saved_ids = {int(row[0]) for row in await cursor.fetchall()}

    items: list[VacancyItem] = []
    for vacancy in vacancies_raw:
        uid = str(vacancy.get("uid", ""))
        raw_id = None
        if uid.startswith("osonish_"):
            try:
                raw_id = int(uid.split("_", 1)[1])
            except (IndexError, ValueError):
                raw_id = None
        max_sal = int(vacancy.get("max_salary") or 0)
        pro_locked = (max_sal >= pro_min_salary) and not is_user_pro
        items.append(
            VacancyItem(
                uid=uid,
                title=str(vacancy.get("title") or "N/A"),
                company=str(vacancy.get("company") or "N/A"),
                salary_text="🔒 Pro tarif" if pro_locked else str(vacancy.get("salary_text") or "Kelishiladi"),
                location=str(vacancy.get("location") or ""),
                district=str(vacancy.get("district") or ""),
                posted_at=str(vacancy.get("posted_at") or "N/A"),
                is_saved=bool(raw_id in saved_ids),
                is_pro_locked=pro_locked,
            )
        )

    return JobsSearchResponse(
        vacancies=items,
        page=page,
        last_page=int(last_page or 1),
        total_estimate=10 * max(int(last_page or 1), page),
    )


@router.get("/{uid}", response_model=VacancyDetailResponse)
@limiter.limit("60/minute")
async def vacancy_detail(
    uid: str,
    request: Request,
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> VacancyDetailResponse:
    request_user_id = await _get_auth_user_id(authorization) or _get_init_data_user_id(request)
    if request_user_id:
        gate_state = await get_referral_gate_state(db, request_user_id)
        raise_if_referral_locked(gate_state)

    raw_id = _uid_to_raw_id(uid)

    cache_key = make_cache_key("detail", uid=uid)
    cached = await cache_get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
        return VacancyDetailResponse(uid=uid, data=cached["data"])

    detail = await fetch_osonish_detail(raw_id)
    if not isinstance(detail, dict):
        raise HTTPException(status_code=404, detail="Vacancy not found")

    detail_with_normalized = {**detail, "normalized": normalize_vacancy_detail(uid, detail)}
    await cache_set(cache_key, {"source": "osonish", "data": detail_with_normalized}, ttl=60 * 60)
    return VacancyDetailResponse(uid=uid, data=detail_with_normalized)


@router.post("/{uid}/send-telegram")
@limiter.limit("20/minute")
async def send_vacancy_to_telegram(uid: str, request: Request, current=Depends(get_current_user)) -> dict[str, bool]:
    raw_id = _uid_to_raw_id(uid)

    detail = await fetch_osonish_detail(raw_id)
    if not isinstance(detail, dict):
        raise HTTPException(status_code=404, detail="Vacancy not found")

    user_id = int(current["user"]["user_id"])
    message_html = format_vacancy_message_html(uid, detail)
    await bot.send_message(chat_id=user_id, text=message_html, disable_web_page_preview=True)

    return {"ok": True}
