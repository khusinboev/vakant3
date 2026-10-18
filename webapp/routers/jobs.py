"""Mini App vacancy list and detail.

Source of truth is the vacancy store (``src/ingest/``, osonish + hh.uz, see
``webapp/core/vacancy_store.py``):

* ``/jobs/search`` reads the store (FTS ``q``, region, district, UZS salary
  floor, sort, cursor pagination). Two cases keep the live osonish.uz search:
  a category filter (``specs`` = osonish field id; the store has no osonish
  field ids and hh roles are not mapped to our categories, so hh items appear
  only without a category filter) and a store with no open rows yet.
* ``/jobs/{uid}`` accepts any ``<source>_<id>``. hh rows come from the store
  only (excerpt + link, hh.uz terms). osonish rows use the stored detail when
  the ingest runner has checked them, else the cached live detail; the store
  row is the fallback when osonish does not answer.
"""
from typing import Any

from fastapi import APIRouter, Depends, Request

from src.functions.cache import cache_get, cache_set, make_cache_key
from src.functions.functions import normalize_osonish_field_id
from src.functions.scraping import UpstreamError, fetch_osonish_list, get_osonish_detail, parse_osonish_uid
from src.functions.vacancy_format import normalize_vacancy_detail
from webapp.core import errors
from webapp.core.admin_settings import get_admin_settings
from webapp.core import vacancy_store
from webapp.core.auth import current_user
from webapp.core.database import get_db, release_db
from webapp.core.entry_gate import require_entry
from webapp.core.i18n import get_lang, localize_salary_text, pro_locked_salary
from webapp.core.limiter import limiter
from webapp.core.referral_gate import get_referral_gate_state, raise_if_referral_locked
from webapp.models.schemas import JobsSearchResponse, VacancyDetailResponse, VacancyItem

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(require_entry)])

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
    raw_id = parse_osonish_uid(uid)
    if raw_id is None:
        raise errors.api_error(400, errors.INVALID_UID, uid=uid)
    return raw_id


def _parse_uid(uid: str) -> tuple[str, str]:
    parsed = vacancy_store.parse_uid(uid)
    if parsed is None:
        raise errors.api_error(400, errors.INVALID_UID, uid=uid[:64])
    return parsed


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
    cursor: str = "",
    user=Depends(current_user),
    lang: str = Depends(get_lang),
    db=Depends(get_db),
) -> JobsSearchResponse:
    user_id = int(user["user_id"])
    raise_if_referral_locked(await get_referral_gate_state(db, user_id))

    # DB phase: everything this request reads, before any upstream call.
    admin_settings = await get_admin_settings(db)
    pro_min_salary = int(admin_settings["pro_min_salary"] or 8_000_000)
    is_user_pro = bool(user.get("is_pro"))
    saved_uids = await vacancy_store.saved_uids(db, user_id)
    field_id = normalize_osonish_field_id(specs)

    if field_id is None and await vacancy_store.store_ready(db):
        page_data = await vacancy_store.search_page(
            db,
            lang=lang,
            q=q,
            money=money,
            region_soato=region_soato,
            district_soato=district_soato,
            sort_key=sort_key,
            sort_type=sort_type,
            page=page,
            cursor=cursor or None,
            pro_min_salary=pro_min_salary,
            is_pro=is_user_pro,
            saved=saved_uids,
        )
        await release_db(db)
        return JobsSearchResponse(
            vacancies=[VacancyItem(**item) for item in page_data.pop("vacancies")], **page_data
        )
    await release_db(db)

    # Live osonish fallback. Network phase: no pooled connection is held from here on.
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
        except UpstreamError as exc:
            # Never cached: the next request retries osonish instead of
            # serving an outage as "no vacancies" for 30 minutes.
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

    items: list[VacancyItem] = []
    for vacancy in vacancies_raw:
        uid = str(vacancy.get("uid") or "")
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
                is_saved=uid in saved_uids,
                is_pro_locked=pro_locked,
                source="osonish",
                source_label="osonish.uz",
                url=(f"https://osonish.uz/vacancies/{_to_raw_id(uid)}" if _to_raw_id(uid) else None),
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
    source, _ = _parse_uid(uid)
    row = await vacancy_store.get_row(db, uid)
    await release_db(db)

    if source != "osonish":
        if row is None:
            raise errors.not_found("vacancy")
        return VacancyDetailResponse(uid=uid, data=vacancy_store.detail_payload(row, lang))

    if row is not None and row.get("status") == "open" and vacancy_store.has_full_osonish_detail(row):
        return VacancyDetailResponse(uid=uid, data=vacancy_store.detail_payload(row, lang))

    raw_id = _uid_to_raw_id(uid)
    fallback = row if row is not None and row.get("status") == "open" else None

    cache_key = make_cache_key("detail", uid=uid)
    cached = await cache_get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
        detail = dict(cached["data"])
    else:
        try:
            fetched = await get_osonish_detail(raw_id)
        except UpstreamError as exc:
            if fallback is not None:
                return VacancyDetailResponse(uid=uid, data=vacancy_store.detail_payload(fallback, lang))
            raise errors.api_error(502, errors.UPSTREAM_ERROR) from exc
        if not isinstance(fetched, dict):  # osonish answered "no such vacancy"
            raise errors.not_found("vacancy")
        detail = fetched
        await cache_set(cache_key, {"source": "osonish", "data": detail}, ttl=60 * 60)

    detail.pop("normalized", None)
    normalized = _normalize_detail(uid, detail, lang)
    normalized.update({"source": "osonish", "source_label": "osonish.uz", "url": normalized.get("source_url")})
    data = {
        **detail,
        "source": "osonish",
        "source_label": "osonish.uz",
        "url": normalized.get("source_url"),
        "normalized": normalized,
    }
    return VacancyDetailResponse(uid=uid, data=data)
