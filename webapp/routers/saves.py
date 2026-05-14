import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.functions.cache import cache_get, cache_set, make_cache_key
from src.functions.scraping import fetch_osonish_detail
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from webapp.core.session import get_optional_current_user
from webapp.core.telegram_auth import verify_webapp_init_data
from webapp.models.schemas import SaveActionResponse, SavesResponse

router = APIRouter(prefix="/saves", tags=["saves"])


def _uid_to_raw_id(uid: str) -> int:
    if not uid.startswith("osonish_"):
        raise HTTPException(status_code=400, detail="Only osonish vacancies are supported")
    try:
        return int(uid.split("_", 1)[1])
    except (IndexError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid vacancy uid") from exc


def _resolve_user_id(request: Request, current: dict | None) -> int:
    if current and current.get("user"):
        return int(current["user"]["user_id"])

    init_data = request.headers.get("X-Telegram-Init-Data", "").strip()
    if not init_data:
        raise HTTPException(status_code=401, detail="Unauthorized")

    settings = get_settings()
    if not settings.TOKEN:
        raise HTTPException(status_code=500, detail="TOKEN not configured")

    user_data = verify_webapp_init_data(init_data, settings.TOKEN)
    if not user_data or not user_data.get("id"):
        raise HTTPException(status_code=401, detail="Invalid initData")

    return int(user_data["id"])


@router.get("", response_model=SavesResponse)
async def list_saves(
    request: Request,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    current=Depends(get_optional_current_user),
    db=Depends(get_db),
) -> SavesResponse:
    user_id = _resolve_user_id(request, current)
    offset = (page - 1) * limit

    cursor = await db.execute("SELECT COUNT(*) FROM saves WHERE user_id = ?", (user_id,))
    total = int((await cursor.fetchone())[0] or 0)

    cursor = await db.execute(
        "SELECT save_id FROM saves WHERE user_id = ? ORDER BY save_id DESC LIMIT ? OFFSET ?",
        (user_id, limit, offset),
    )
    rows = await cursor.fetchall()

    items: list[dict] = []
    for row in rows:
        save_id = int(row[0])
        uid = f"osonish_{save_id}"
        cache_key = make_cache_key("detail", uid=uid)
        cached = await cache_get(cache_key)

        if isinstance(cached, dict) and isinstance(cached.get("data"), dict):
            detail = cached["data"]
        else:
            detail = await fetch_osonish_detail(save_id)
            if not isinstance(detail, dict):
                continue
            await cache_set(cache_key, {"source": "osonish", "data": detail}, ttl=60 * 60)

        items.append({"uid": uid, "data": detail})

    return SavesResponse(items=items, total=total)


@router.post("/{uid}", response_model=SaveActionResponse)
@limiter.limit("60/minute")
async def add_save(
    request: Request,
    uid: str,
    current=Depends(get_optional_current_user),
    db=Depends(get_db),
) -> SaveActionResponse:
    user_id = _resolve_user_id(request, current)
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
    await db.commit()

    return SaveActionResponse(saved=True)


@router.delete("/{uid}", response_model=SaveActionResponse)
async def remove_save(
    request: Request,
    uid: str,
    current=Depends(get_optional_current_user),
    db=Depends(get_db),
) -> SaveActionResponse:
    user_id = _resolve_user_id(request, current)
    raw_id = _uid_to_raw_id(uid)

    await db.execute(
        "DELETE FROM saves WHERE user_id = ? AND save_id = ?",
        (user_id, raw_id),
    )
    await db.commit()

    return SaveActionResponse(removed=True)
