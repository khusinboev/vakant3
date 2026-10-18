"""API view of the vacancy store (``src/ingest/``): uids, saved sets, list items and detail payloads.

Used by ``webapp/routers/jobs.py`` and ``saves.py``. Every helper here only
reads the database; none does network I/O.

uids are ``<source>_<id>`` (``src/functions/vacancy_format.parse_vacancy_uid``).
``saves.save_id`` holds the bare osonish id as an INTEGER for osonish (as it
always did) and the full uid as TEXT for other sources (``hh_123``).
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Optional

import aiosqlite

from src.functions.scraping import MAX_OSONISH_ID
from src.functions.vacancy_format import (
    SOURCE_LABELS,
    format_salary,
    normalize_store_vacancy,
    osonish_store_detail,
    parse_vacancy_uid,
    store_date,
)
from src.ingest import repo as store
from src.ingest.regions import REGION_SOATO
from webapp.core.i18n import district_name, pro_locked_salary, region_name

#: Mini App page size over the store.
PAGE_SIZE = 20

#: Frontend sort chips (``sort_key``, ``sort_type``) -> ``repo.search`` sort.
SORTS: dict[tuple[str, str], str] = {
    ("published_at", "desc"): "new",
    ("published_at", "asc"): "old",
    ("salary", "desc"): "salary",
}


def parse_uid(uid: str) -> Optional[tuple[str, str]]:
    """``(source, id)`` for a uid the API accepts (osonish ids capped at ``MAX_OSONISH_ID``)."""
    parsed = parse_vacancy_uid(uid)
    if parsed is None:
        return None
    if parsed[0] == "osonish" and int(parsed[1]) > MAX_OSONISH_ID:
        return None
    return parsed


def save_value(uid: str) -> int | str:
    """What ``saves.save_id`` stores for ``uid`` (an INTEGER for osonish, the uid otherwise)."""
    source, source_id = parse_vacancy_uid(uid) or ("", "")
    return int(source_id) if source == "osonish" else uid


def uid_of_save(value: Any) -> Optional[str]:
    """``saves.save_id`` -> uid (INTEGER / legacy ``osonish_<id>`` text / ``hh_<id>``)."""
    text = "" if value is None else str(value).strip()
    if not text:
        return None
    if parse_vacancy_uid(text) is not None:
        return text
    if text.startswith("osonish_"):
        text = text.split("_", 1)[1]
    try:
        return f"osonish_{int(text)}"
    except ValueError:
        return None


async def saved_uids(db, user_id: int) -> set[str]:
    cursor = await db.execute("SELECT save_id FROM saves WHERE user_id = ?", (user_id,))
    return {uid for row in await cursor.fetchall() for uid in [uid_of_save(row[0])] if uid}


async def store_ready(db) -> bool:
    """The store has open vacancies (False before the first ingest or without the table)."""
    try:
        return await store.has_open(db)
    except aiosqlite.OperationalError:
        return False


async def get_row(db, uid: str) -> Optional[dict[str, Any]]:
    try:
        return await store.get(db, uid, with_raw=True)
    except aiosqlite.OperationalError:
        return None


def region_label(soato: str, fallback: str, lang: str) -> str:
    """Localized region for a SOATO code (``fallback`` when unknown)."""
    uz = REGION_SOATO.get(str(soato))
    if not uz:
        return fallback
    return region_name(str(soato), uz, lang)


async def _district_names(db, soatos: Iterable[str]) -> dict[str, str]:
    codes = sorted({s for s in soatos if s})
    if not codes:
        return {}
    marks = ",".join("?" * len(codes))
    try:
        cursor = await db.execute(f"SELECT soato, name_uz FROM districts WHERE soato IN ({marks})", codes)
    except aiosqlite.OperationalError:
        return {}
    return {str(row[0]): str(row[1] or "") for row in await cursor.fetchall()}


def _uzs_max(row: dict[str, Any]) -> int:
    if str(row.get("currency") or "UZS").upper() != "UZS":
        return 0
    return int(row.get("salary_max") or row.get("salary_min") or 0)


def _list_date(ts: Any) -> Optional[str]:
    iso = store_date(ts)
    if not iso:
        return None
    year, month, day = iso.split("-")
    return f"{day}.{month}.{year}"


async def search_page(
    db,
    *,
    lang: str,
    q: str,
    money: int,
    region_soato: str,
    district_soato: str,
    sort_key: str,
    sort_type: str,
    page: int,
    cursor: Optional[str],
    pro_min_salary: int,
    is_pro: bool,
    saved: set[str],
) -> dict[str, Any]:
    """One Mini App page from the store, in the ``JobsSearchResponse`` shape."""
    page = max(1, int(page or 1))
    result = await store.search(
        db,
        query=q or None,
        region_soato=region_soato or None,
        district_soato=district_soato or None,
        min_salary=max(0, int(money or 0)),
        limit=PAGE_SIZE,
        cursor=cursor or None,
        sort=SORTS.get((sort_key or "", (sort_type or "").lower()), "new"),
        offset=0 if cursor else (page - 1) * PAGE_SIZE,
        with_total=True,
    )
    rows = result["items"]
    districts = await _district_names(db, (str(r.get("district_soato") or "") for r in rows))

    items = []
    for row in rows:
        uid = str(row["uid"])
        region = region_label(str(row.get("region_soato") or ""), str(row.get("region_name") or ""), lang)
        dsoato = str(row.get("district_soato") or "")
        district = district_name(dsoato, districts[dsoato], lang) if districts.get(dsoato) else ""
        locked = bool(pro_min_salary) and _uzs_max(row) >= pro_min_salary and not is_pro
        items.append(
            {
                "uid": uid,
                "title": str(row.get("title") or "").strip() or None,
                "company": str(row.get("employer") or "").strip() or None,
                "salary_text": (
                    pro_locked_salary(lang)
                    if locked
                    else format_salary(row.get("salary_min"), row.get("salary_max"), lang, currency=row.get("currency"))
                ),
                "location": ", ".join(p for p in (district, region) if p) or None,
                "district": district or None,
                "posted_at": _list_date(row.get("published_at")),
                "is_saved": uid in saved,
                "is_pro_locked": locked,
                "source": str(row.get("source") or ""),
                "source_label": SOURCE_LABELS.get(str(row.get("source") or ""), str(row.get("source") or "")),
                "url": str(row.get("url") or "") or None,
            }
        )

    total = int(result["total"] or 0)
    next_cursor = result["next_cursor"]
    last_page = max(page + 1, math.ceil(total / PAGE_SIZE)) if next_cursor else page
    return {
        "vacancies": items,
        "page": page,
        "last_page": last_page,
        "total_estimate": total,
        "next_cursor": next_cursor,
    }


def has_full_osonish_detail(row: dict[str, Any]) -> bool:
    """A runner-checked osonish row whose stored payload renders like the live detail."""
    return osonish_store_detail(row) is not None


def detail_payload(row: dict[str, Any], lang: str) -> dict[str, Any]:
    """``VacancyDetailResponse.data`` for a store row.

    osonish rows with the stored detail keep the osonish fields the Mini App
    reads; hh rows carry only our own fields (excerpt + link, no contacts).
    """
    normalized = normalize_store_vacancy(row, lang, region_label=region_label)
    base = osonish_store_detail(row) or {}
    data: dict[str, Any] = {k: v for k, v in base.items() if k != "normalized"}
    data.update(
        {
            "title": normalized["title"],
            "source": normalized["source"],
            "source_label": normalized["source_label"],
            "url": normalized["url"],
            "status": row.get("status"),
            "normalized": normalized,
        }
    )
    if not base:
        data["company"] = {"name": normalized["company"]} if normalized["company"] else None
    return data
