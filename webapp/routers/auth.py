from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.functions.webapp_link import is_revoked, verify_bot_link

from webapp.core import errors
from webapp.core.auth import current_user
from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.entry_gate import evaluate_entry
from webapp.core.i18n import normalize_lang
from webapp.core.limiter import limiter
from webapp.core.session import create_session
from webapp.core.telegram_auth import verify_webapp_init_data
from webapp.core.users import USER_COLUMNS, ensure_user
from webapp.models.schemas import AuthResponse, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_profile(row: dict) -> UserProfile:
    return UserProfile(
        user_id=int(row["user_id"]),
        first_name=str(row.get("first_name") or ""),
        username=row.get("username"),
        photo_url=row.get("photo_url"),
        lang=normalize_lang(row.get("lang")),
    )


@router.get("/me", response_model=UserProfile)
async def me(user=Depends(current_user)) -> UserProfile:
    return _to_profile(user)


class TgWebAppRequest(BaseModel):
    init_data: str


@router.post("/tg-webapp", response_model=AuthResponse)
@limiter.limit("30/minute")
async def tg_webapp_login(request: Request, payload: TgWebAppRequest, db=Depends(get_db)) -> AuthResponse:
    """Authenticate via Telegram.WebApp.initData (HMAC-verified)."""
    settings = get_settings()
    if not settings.TOKEN:
        raise errors.api_error(500, errors.SERVER_MISCONFIGURED)

    user_data = verify_webapp_init_data(payload.init_data, settings.TOKEN)
    if not user_data or not user_data.get("id"):
        raise errors.api_error(401, errors.INVALID_INIT_DATA)

    try:
        user_id = int(user_data["id"])
    except (TypeError, ValueError):
        raise errors.api_error(401, errors.INVALID_INIT_DATA) from None

    row = await ensure_user(
        db,
        user_id,
        lang=normalize_lang(user_data.get("language_code")),
        first_name=user_data.get("first_name"),
        username=user_data.get("username"),
        photo_url=user_data.get("photo_url"),
    )
    if not row:
        raise errors.not_found("user")

    session_token, _exp = await create_session(db, user_id)
    await db.commit()

    return AuthResponse(session_token=session_token, user=_to_profile(row))


class BotLinkRequest(BaseModel):
    # Generous cap: a real token is 39 characters; anything else is refused
    # below with BOT_LINK_INVALID rather than a 422.
    token: str = Field(max_length=256)
    # Ignored. Builds before Oct 2026 sent ``confirm`` (false first, then true
    # after a «Kirish» popup); it is still accepted so those requests validate.
    confirm: bool | None = None


@router.post("/bot-link", response_model=AuthResponse)
@limiter.limit("20/minute")
async def bot_link_login(request: Request, payload: BotLinkRequest, db=Depends(get_db)) -> AuthResponse:
    """Exchange a signed bot keyboard link (``?bt=``) for a Bearer session.

    A reply-keyboard ``web_app`` button opens the Mini App with empty initData;
    the bot puts a personal token into its URL (``src/functions/webapp_link.py``).

    A valid link signs in directly, with no confirmation step: the owner's rule
    is that the Mini App always opens as the current Telegram account. The
    client replaces any cached session with the one returned here.

    Identity rules match the initData login: the user must exist (the bot
    created the row at /start), a ban is not refused here — the entry gate
    answers ``USER_BANNED`` on every gated route. A link issued at or before
    the user's revocation watermark (a ban or an admin "revoke sessions") is
    dead. Every failure is one code, 401 ``BOT_LINK_INVALID``. Normal logins
    are not audited. The token is a credential and is never logged.
    """
    settings = get_settings()
    link = verify_bot_link(payload.token, secret=settings.WEBAPP_SECRET)
    if link is None:
        raise errors.api_error(401, errors.BOT_LINK_INVALID)

    cursor = await db.execute(
        f"SELECT {USER_COLUMNS}, bot_links_before FROM users WHERE user_id = ?",
        (link.user_id,),
    )
    row = await cursor.fetchone()
    if row is None or is_revoked(link, row["bot_links_before"]):
        raise errors.api_error(401, errors.BOT_LINK_INVALID)
    user = dict(row)

    session_token, _exp = await create_session(db, link.user_id)
    await db.commit()
    return AuthResponse(session_token=session_token, user=_to_profile(user))


# ── Entry gate ──────────────────────────────────────────────────────────────
# One call the Mini App makes on launch to decide between the app and the lock
# screen. It is deliberately NOT behind ``require_entry``: it is the endpoint
# that reports the gate, so a locked user must be able to read it.


@router.get("/gate")
@limiter.limit("60/minute")
async def entry_gate_state(
    request: Request, user=Depends(current_user), db=Depends(get_db)
) -> dict:
    state = await evaluate_entry(db, int(user["user_id"]))
    await db.commit()
    return state


@router.post("/gate/recheck")
@limiter.limit("6/minute")
async def entry_gate_recheck(
    request: Request, user=Depends(current_user), db=Depends(get_db)
) -> dict:
    """Drop the cached subscription verdict and ask Telegram again.

    This is the only way to bypass the per-user TTL, hence the tight limit:
    without it a lock screen with an eager "check again" button would turn into
    one Telegram round trip per tap per user.
    """
    state = await evaluate_entry(db, int(user["user_id"]), force=True)
    await db.commit()
    return state
