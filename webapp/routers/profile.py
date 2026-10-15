import json

from fastapi import APIRouter, Depends
from pydantic import Field

from webapp.core import errors
from webapp.core.auth import current_user
from webapp.core.database import get_db
from webapp.core.entry_gate import require_entry
from webapp.core.i18n import LANGS, normalize_lang
from webapp.core.users import set_user_lang
from webapp.models.schemas import (
    LangPatchRequest,
    LangResponse,
    ProfileFiltersPatchRequest,
    UpdateResultResponse,
)

#: Upper bound for the salary filter (so'm). Far above any real salary and far
#: below SQLite's 64-bit INTEGER, which an unbounded int would overflow (500).
MAX_FILTER_MONEY = 10**12


class FiltersPatch(ProfileFiltersPatchRequest):
    """The shared request schema plus the bounds this endpoint enforces (422 otherwise)."""

    region: str | None = Field(default=None, max_length=32)
    district: str | None = Field(default=None, max_length=32)
    specs: str | None = Field(default=None, max_length=256)
    money: int | None = Field(default=None, ge=0, le=MAX_FILTER_MONEY)


router = APIRouter(prefix="/profile", tags=["profile"], dependencies=[Depends(require_entry)])

# Column allowlist: the patch body can only touch these, and the SQL fragment
# is taken from this mapping (never interpolated from user input).
FILTER_COLUMNS: dict[str, str] = {
    "region": "region = ?",
    "district": "district = ?",
    "specs": "specs = ?",
    "money": "money = ?",
}


@router.patch("/lang", response_model=LangResponse)
async def patch_lang(
    payload: LangPatchRequest,
    user=Depends(current_user),
    db=Depends(get_db),
) -> LangResponse:
    raw = str(payload.lang or "").strip().lower()
    if raw not in LANGS:
        raise errors.validation_error("lang")
    lang = normalize_lang(raw)
    await set_user_lang(db, int(user["user_id"]), lang)
    return LangResponse(ok=True, lang=lang)


@router.patch("/filters", response_model=UpdateResultResponse)
async def patch_filters(
    payload: FiltersPatch,
    user=Depends(current_user),
    db=Depends(get_db),
) -> UpdateResultResponse:
    user_id = int(user["user_id"])
    data = payload.model_dump(exclude_unset=True)

    fields: list[str] = []
    values: list = []
    for key, value in data.items():
        fragment = FILTER_COLUMNS.get(key)
        if fragment:
            fields.append(fragment)
            values.append(value)

    if not fields:
        return UpdateResultResponse(updated=True)

    # Auto-build pref_filters_json for the bot's notification scheduler.
    cursor = await db.execute(
        "SELECT region, money, specs FROM users WHERE user_id = ?", (user_id,)
    )
    row = await cursor.fetchone()
    region = data.get("region") if "region" in data else (row["region"] if row else None)
    money = data.get("money") if "money" in data else (row["money"] if row else None)
    specs = data.get("specs") if "specs" in data else (row["specs"] if row else None)

    pref_filters: dict = {}
    if region:
        pref_filters["region_soato"] = str(region)
    if money:
        pref_filters["min_salary"] = int(money)
    if specs:
        pref_filters["specs"] = str(specs)

    # Always rewritten, so clearing every filter also clears what the
    # notification scheduler matches on (NULL = no filters, same as '{}').
    fields.append("pref_filters_json = ?")
    values.append(json.dumps(pref_filters, ensure_ascii=False) if pref_filters else None)

    values.append(user_id)
    await db.execute(f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?", tuple(values))
    await db.commit()

    return UpdateResultResponse(updated=True)
