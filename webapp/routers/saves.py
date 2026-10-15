import asyncio
import re

from fastapi import APIRouter, Depends, Query, Request

from src.functions.cache import cache_get, cache_set, make_cache_key
from src.functions.scraping import UpstreamError, get_osonish_detail, parse_osonish_uid
from webapp.core import errors
from webapp.core.auth import current_user
from webapp.core.database import get_db, release_db
from webapp.core.entry_gate import require_entry
from webapp.core.limiter import limiter
from webapp.core.referral_gate import get_referral_gate_state, raise_if_referral_locked
from webapp.models.schemas import SaveActionResponse, SavesResponse

router = APIRouter(prefix="/saves", tags=["saves"], dependencies=[Depends(require_entry)])
DETAIL_CACHE_TTL = 60 * 60
FREE_SAVE_LIMIT = 5
MAX_PARALLEL_DETAIL_FETCHES = 5


def _row_to_raw_id(value: object) -> int | None:
    """saves.save_id is an INTEGER, but tolerate legacy 'osonish_<id>' text rows."""
    s = "" if value is None else str(value).strip()
    if s.startswith("osonish_"):
        s = s.split("_", 1)[1]
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _uid_to_raw_id(uid: str) -> int:
    """Strict: what POST accepts as a new save."""
    raw_id = parse_osonish_uid(uid)
    if raw_id is None:
        raise errors.api_error(400, errors.INVALID_UID, uid=uid[:64])
    return raw_id


_STORED_UID = re.compile(r"osonish_(-?[0-9]{1,19})")
_INT64_MIN, _INT64_MAX = -(2**63), 2**63 - 1


def _stored_uid_to_raw_id(uid: str) -> int:
    """Lenient: any id a row can hold, so DELETE can remove saves made before
    the strict check (``osonish_0``, negative or > 2**53 ids) — the list shows
    them and they count toward ``FREE_SAVE_LIMIT``."""
    match = _STORED_UID.fullmatch(uid)
    raw_id = int(match.group(1)) if match else None
    if raw_id is None or not (_INT64_MIN <= raw_id <= _INT64_MAX):
        raise errors.api_error(400, errors.INVALID_UID, uid=uid[:64])
    return raw_id


@router.get("", response_model=SavesResponse)
@limiter.limit("30/minute")
async def list_saves(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    user=Depends(current_user),
    db=Depends(get_db),
) -> SavesResponse:
    user_id = int(user["user_id"])
    raise_if_referral_locked(await get_referral_gate_state(db, user_id))

    offset = (page - 1) * limit

    cursor = await db.execute(
        "SELECT DISTINCT save_id FROM saves WHERE user_id = ? ORDER BY save_id DESC",
        (user_id,),
    )
    seen: set[int] = set()
    all_ids: list[int] = []
    for row in await cursor.fetchall():
        raw_id = _row_to_raw_id(row[0])
        if raw_id is None or raw_id in seen:
            continue
        seen.add(raw_id)
        all_ids.append(raw_id)
    total = len(all_ids)
    save_ids = all_ids[offset: offset + limit]
    # Up to ``limit`` detail fetches follow; none of them may pin a pool slot.
    await release_db(db)

    semaphore = asyncio.Semaphore(MAX_PARALLEL_DETAIL_FETCHES)

    async def _load_item(save_id: int) -> dict:
        uid = f"osonish_{save_id}"
        cache_key = make_cache_key("detail", uid=uid)
        cached = await cache_get(cache_key)

        if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
            return {"uid": uid, "data": cached["data"]}

        async with semaphore:
            try:
                detail = await get_osonish_detail(save_id)
            except UpstreamError:
                detail = None
        if not isinstance(detail, dict):
            # Gone or upstream down (never cached either way). Keep the row so
            # `items` and `total` always agree.
            return {"uid": uid, "title": None, "unavailable": True, "data": None}

        await cache_set(cache_key, {"source": "osonish", "data": detail}, ttl=DETAIL_CACHE_TTL)
        return {"uid": uid, "data": detail}

    loaded = await asyncio.gather(*[_load_item(save_id) for save_id in save_ids], return_exceptions=True)

    items: list[dict] = []
    for save_id, item in zip(save_ids, loaded):
        if isinstance(item, dict):
            items.append(item)
        else:
            items.append({"uid": f"osonish_{save_id}", "title": None, "unavailable": True, "data": None})

    return SavesResponse(items=items, total=total)


@router.post("/{uid}", response_model=SaveActionResponse)
@limiter.limit("60/minute")
async def add_save(
    request: Request,
    uid: str,
    user=Depends(current_user),
    db=Depends(get_db),
) -> SaveActionResponse:
    user_id = int(user["user_id"])
    raise_if_referral_locked(await get_referral_gate_state(db, user_id))

    raw_id = _uid_to_raw_id(uid)

    if not bool(user.get("is_pro")):
        count_cursor = await db.execute(
            "SELECT COUNT(DISTINCT save_id) FROM saves WHERE user_id = ?", (user_id,)
        )
        current_count = int((await count_cursor.fetchone())[0] or 0)
        if current_count >= FREE_SAVE_LIMIT:
            raise errors.api_error(
                403,
                errors.SAVE_LIMIT_REACHED,
                limit=FREE_SAVE_LIMIT,
                current=current_count,
            )

    await db.execute(
        "INSERT OR IGNORE INTO saves (user_id, save_id) VALUES (?, ?)",
        (user_id, raw_id),
    )
    # Commit and hand the pooled connection back before any network call.
    await db.commit()
    await release_db(db)

    # Warm the detail cache so /saves opens immediately.
    cache_key = make_cache_key("detail", uid=f"osonish_{raw_id}")
    cached = await cache_get(cache_key)
    if not (isinstance(cached, dict) and isinstance(cached.get("data"), dict)):
        try:
            detail = await get_osonish_detail(raw_id)
        except UpstreamError:
            detail = None
        if isinstance(detail, dict):
            await cache_set(cache_key, {"source": "osonish", "data": detail}, ttl=DETAIL_CACHE_TTL)

    return SaveActionResponse(saved=True)


@router.delete("/{uid}", response_model=SaveActionResponse)
async def remove_save(
    request: Request,
    uid: str,
    user=Depends(current_user),
    db=Depends(get_db),
) -> SaveActionResponse:
    user_id = int(user["user_id"])
    raise_if_referral_locked(await get_referral_gate_state(db, user_id))

    raw_id = _stored_uid_to_raw_id(uid)

    # Integer rows, plus legacy 'osonish_<id>' text rows the list also shows.
    await db.execute(
        "DELETE FROM saves WHERE user_id = ? AND save_id IN (?, ?)",
        (user_id, raw_id, f"osonish_{raw_id}"),
    )
    await db.commit()

    return SaveActionResponse(removed=True)
