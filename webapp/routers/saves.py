import asyncio
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from src.functions.cache import cache_get, cache_set, make_cache_key
from src.functions.scraping import fetch_osonish_detail
from src.functions.vacancy_format import normalize_vacancy_detail
from webapp.core.database import get_db
from webapp.core.identity import require_request_user_id
from webapp.core.limiter import limiter
from webapp.core.referral_gate import get_referral_gate_state, raise_if_referral_locked
from webapp.models.schemas import SaveActionResponse, SavesResponse

router = APIRouter(prefix="/saves", tags=["saves"])
DETAIL_CACHE_TTL = 60 * 60


def _uid_to_raw_id(uid: str) -> int:
    if not uid.startswith("osonish_"):
        raise HTTPException(status_code=400, detail="Only osonish vacancies are supported")
    try:
        return int(uid.split("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid vacancy uid") from exc


@router.get("", response_model=SavesResponse)
async def list_saves(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> SavesResponse:
    user_id = await require_request_user_id(request=request, db=db, authorization=authorization)
    gate_state = await get_referral_gate_state(db, user_id)
    raise_if_referral_locked(gate_state)

    offset = (page - 1) * limit

    cursor = await db.execute("SELECT COUNT(*) FROM saves WHERE user_id = ?", (user_id,))
    total = int((await cursor.fetchone())[0] or 0)

    cursor = await db.execute(
        "SELECT save_id FROM saves WHERE user_id = ? ORDER BY save_id DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    )
    rows = await cursor.fetchall()

    async def _load_item(save_id: int) -> dict | None:
        uid = f"osonish_{save_id}"
        cache_key = make_cache_key("detail", uid=uid)
        cached = await cache_get(cache_key)

        if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
            cached_data = dict(cached["data"])
            if "normalized" not in cached_data:
                cached_data["normalized"] = normalize_vacancy_detail(uid, cached_data)
            return {"uid": uid, "data": cached_data}

        detail = await fetch_osonish_detail(save_id)
        if not isinstance(detail, dict):
            return None

        detail_with_normalized = {**detail, "normalized": normalize_vacancy_detail(uid, detail)}
        await cache_set(
            cache_key,
            {"source": "osonish", "data": detail_with_normalized},
            ttl=DETAIL_CACHE_TTL,
        )
        return {"uid": uid, "data": detail_with_normalized}

    save_ids = [int(row[0]) for row in rows]
    loaded = await asyncio.gather(*[_load_item(save_id) for save_id in save_ids], return_exceptions=True)

    items: list[dict] = []
    for item in loaded:
        if isinstance(item, dict):
            items.append(item)

    return SavesResponse(items=items, total=total)


@router.post("/{uid}", response_model=SaveActionResponse)
@limiter.limit("60/minute")
async def add_save(
    request: Request,
    uid: str,
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> SaveActionResponse:
    user_id = await require_request_user_id(request=request, db=db, authorization=authorization)
    gate_state = await get_referral_gate_state(db, user_id)
    raise_if_referral_locked(gate_state)

    raw_id = _uid_to_raw_id(uid)

    # Ensure user exists even when the request is identified by Telegram initData.
    now = int(time.time())
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, ?)",
        (user_id, now, "uz"),
    )

    await db.execute(
        "INSERT OR IGNORE INTO saves (user_id, save_id) VALUES (?, ?)",
        (user_id, raw_id),
    )

    # Warm the detail cache on save so /saves opens immediately.
    uid = f"osonish_{raw_id}"
    cache_key = make_cache_key("detail", uid=uid)
    cached = await cache_get(cache_key)
    if not (isinstance(cached, dict) and isinstance(cached.get("data"), dict)):
        detail = await fetch_osonish_detail(raw_id)
        if isinstance(detail, dict):
            detail_with_normalized = {**detail, "normalized": normalize_vacancy_detail(uid, detail)}
            await cache_set(
                cache_key,
                {"source": "osonish", "data": detail_with_normalized},
                ttl=DETAIL_CACHE_TTL,
            )

    await db.commit()

    return SaveActionResponse(saved=True)


@router.delete("/{uid}", response_model=SaveActionResponse)
async def remove_save(
    request: Request,
    uid: str,
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
) -> SaveActionResponse:
    user_id = await require_request_user_id(request=request, db=db, authorization=authorization)
    gate_state = await get_referral_gate_state(db, user_id)
    raise_if_referral_locked(gate_state)

    raw_id = _uid_to_raw_id(uid)

    await db.execute(
        "DELETE FROM saves WHERE user_id = ? AND save_id = ?",
        (user_id, raw_id),
    )
    await db.commit()

    return SaveActionResponse(removed=True)
