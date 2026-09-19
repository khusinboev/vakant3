from typing import Any

from fastapi import APIRouter, Depends, Request

from src.functions.cache import cache_get, cache_set, make_cache_key
from src.functions.functions import normalize_osonish_field_id
from src.functions.scraping import fetch_osonish_detail, fetch_osonish_list
from src.functions.vacancy_format import normalize_vacancy_detail
from webapp.core import errors
from webapp.core.admin_settings import get_admin_settings
from webapp.core.auth import current_user
from webapp.core.database import get_db
from webapp.core.i18n import get_lang, localize_salary_text, pro_locked_salary
from webapp.core.limiter import limiter
from webapp.core.referral_gate import get_referral_gate_state, raise_if_referral_locked
from webapp.models.schemas import JobsSearchResponse, VacancyDetailResponse, VacancyItem

router = APIRouter(prefix="/jobs", tags=["jobs"])

_CODE_FIELDS = {
    "gender": "gender",
    "work_type": "work_type",
    "busyness_type": "busyness_type",
    "payment_type": "payment_type",
    "education": "min_education",
    "experience": "work_experiance",
}


def _to_raw_id(value: object) -> int | None:
    s = str(value or "").strip()
    if not s:
        return None
    if s.startswith("osonish_"):
        s = s.split("_", 1)[1]
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _uid_to_raw_id(uid: str) -> int:
    raw_id = _to_raw_id(uid) if uid.startswith("osonish_") else None
    if raw_id is None:
        raise errors.api_error(400, errors.INVALID_UID, uid=uid)
    return raw_id


def _normalize_detail(uid: str, detail: dict[str, Any], lang: str) -> dict[str, Any]:
    """Localized normalized view of a vacancy plus the raw integer ``codes``."""
    normalized = dict(normalize_vacancy_detail(uid, detail, lang=lang))
    normalized.setdefault("uid", uid)
    return normalized


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
    user=Depends(current_user),
    lang: str = Depends(get_lang),
    db=Depends(get_db),
) -> JobsSearchResponse:
    user_id = int(user["user_id"])
    raise_if_referral_locked(await get_referral_gate_state(db, user_id))

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
        try:
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
        except Exception as exc:
            raise errors.api_error(502, errors.UPSTREAM_ERROR) from exc
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

    admin_settings = await get_admin_settings(db)
    pro_min_salary = int(admin_settings["pro_min_salary"] or 8_000_000)
    is_user_pro = bool(user.get("is_pro"))

    saved_ids: set[int] = set()
    raw_ids = [raw for raw in (_to_raw_id(v.get("uid")) for v in vacancies_raw) if raw is not None]
    if raw_ids:
        placeholders = ",".join("?" for _ in raw_ids)
        cursor = await db.execute(
            f"SELECT save_id FROM saves WHERE user_id = ? AND save_id IN ({placeholders})",
            tuple([user_id, *raw_ids]),
        )
        saved_ids = {
            raw for row in await cursor.fetchall()
            for raw in [_to_raw_id(row[0])]
            if raw is not None
        }

    items: list[VacancyItem] = []
    for vacancy in vacancies_raw:
        uid = str(vacancy.get("uid") or "")
        raw_id = _to_raw_id(uid)
        max_sal = int(vacancy.get("max_salary") or 0)
        pro_locked = (max_sal >= pro_min_salary) and not is_user_pro
        title = str(vacancy.get("title") or "").strip()
        company = str(vacancy.get("company") or "").strip()
        posted_at = str(vacancy.get("posted_at") or "").strip()
        items.append(
            VacancyItem(
                uid=uid,
                title=title if title and title != "N/A" else None,
                company=company if company and company != "N/A" else None,
                salary_text=(
                    pro_locked_salary(lang)
                    if pro_locked
                    else localize_salary_text(vacancy.get("salary_text"), lang)
                ),
                location=str(vacancy.get("location") or "") or None,
                district=str(vacancy.get("district") or "") or None,
                posted_at=posted_at if posted_at and posted_at != "N/A" else None,
                is_saved=raw_id is not None and raw_id in saved_ids,
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
    user=Depends(current_user),
    lang: str = Depends(get_lang),
    db=Depends(get_db),
) -> VacancyDetailResponse:
    raise_if_referral_locked(await get_referral_gate_state(db, int(user["user_id"])))

    raw_id = _uid_to_raw_id(uid)

    cache_key = make_cache_key("detail", uid=uid)
    cached = await cache_get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
        detail = dict(cached["data"])
    else:
        try:
            fetched = await fetch_osonish_detail(raw_id)
        except Exception as exc:
            raise errors.api_error(502, errors.UPSTREAM_ERROR) from exc
        if not isinstance(fetched, dict):
            raise errors.not_found("vacancy")
        detail = fetched
        await cache_set(cache_key, {"source": "osonish", "data": detail}, ttl=60 * 60)

    detail.pop("normalized", None)
    data = {**detail, "normalized": _normalize_detail(uid, detail, lang)}
    return VacancyDetailResponse(uid=uid, data=data)
