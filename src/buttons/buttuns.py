# ============================================================
# src/buttons/buttuns.py - Aiogram 3.x
# Klaviaturalar til bo'yicha quriladi: har bir funksiya `lang` oladi.
# ============================================================
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from src.functions.admin_roles import has_role
from src.i18n import DEFAULT_LANG, t

# ── Admin callback data ──────────────────────────────────────────────────
# Every admin inline button starts with ``adm:`` and stays far below
# Telegram's 64-byte limit:
#   adm:w:<nonce>:<action>[:<arg>]   wizard steps before a draft exists
#   adm:b:<broadcast_id>:<action>    a draft / queued broadcast card
CB_PREFIX = "adm:"
CB_WIZARD = "adm:w:"
CB_BROADCAST = "adm:b:"

#: Audiences offered by the bot wizard: (segment, label key). Every segment
#: is one ``broadcast_worker.is_valid_segment`` accepts.
BROADCAST_SEGMENTS: tuple[tuple[str, str], ...] = (
    ("all", "bc.seg.all"),
    ("pro", "bc.seg.pro"),
    ("free", "bc.seg.free"),
    ("lang:uz", "bc.seg.lang_uz"),
    ("lang:ru", "bc.seg.lang_ru"),
    ("lang:en", "bc.seg.lang_en"),
    ("active_days:7", "bc.seg.active_7"),
    ("active_days:30", "bc.seg.active_30"),
    ("test_admins", "bc.seg.test_admins"),
)
_SEGMENT_LABELS = dict(BROADCAST_SEGMENTS)


def segment_label(lang: str, segment: str) -> str | None:
    """Localized audience name, or None for a segment the bot does not offer."""
    key = _SEGMENT_LABELS.get(segment)
    return t(lang, key) if key else None


def cb_wizard(nonce: str, action: str, arg: str | None = None) -> str:
    return f"{CB_WIZARD}{nonce}:{action}" + (f":{arg}" if arg else "")


def cb_broadcast(broadcast_id: int, action: str) -> str:
    return f"{CB_BROADCAST}{int(broadcast_id)}:{action}"


def _inline(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


# ── Admin reply keyboards ────────────────────────────────────────────────

def main_btn(lang: str = DEFAULT_LANG, role: str | None = "owner") -> ReplyKeyboardMarkup:
    """Admin panelining bosh menyusi. Broadcasts are shown to admin+ only."""
    rows = [
        [
            KeyboardButton(text=t(lang, "btn.admin.stats")),
            KeyboardButton(text=t(lang, "btn.admin.channels")),
        ]
    ]
    if has_role(role, "admin"):
        rows.append([KeyboardButton(text=t(lang, "btn.admin.ads"))])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def channel_btn(lang: str = DEFAULT_LANG, role: str | None = "owner") -> ReplyKeyboardMarkup:
    """Channel menu; adding and removing channels is admin+ (as in the API)."""
    rows = []
    if has_role(role, "admin"):
        rows.append(
            [
                KeyboardButton(text=t(lang, "btn.admin.channel_add")),
                KeyboardButton(text=t(lang, "btn.admin.channel_del")),
            ]
        )
    rows.append(
        [
            KeyboardButton(text=t(lang, "btn.admin.channel_list")),
            KeyboardButton(text=t(lang, "btn.admin.back")),
        ]
    )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def reklama_btn(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn.admin.bc_new")),
                KeyboardButton(text=t(lang, "btn.admin.bc_list")),
            ],
            [KeyboardButton(text=t(lang, "btn.admin.back"))],
        ],
        resize_keyboard=True,
    )


def back_btn(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, "btn.admin.back"))]],
        resize_keyboard=True,
    )


# ── Admin inline keyboards ───────────────────────────────────────────────

def admin_webapp_kb(lang: str, url: str) -> InlineKeyboardMarkup:
    """Opens the Mini App admin panel (an inline web_app button carries initData)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn.admin.webapp"), web_app=WebAppInfo(url=url))]]
    )


def bc_button_step_kb(lang: str, nonce: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _inline(t(lang, "bc.btn.skip"), cb_wizard(nonce, "skip")),
                _inline(t(lang, "bc.btn.cancel"), cb_wizard(nonce, "x")),
            ]
        ]
    )


def bc_audience_kb(lang: str, nonce: str) -> InlineKeyboardMarkup:
    def seg(segment: str) -> InlineKeyboardButton:
        return _inline(segment_label(lang, segment), cb_wizard(nonce, "seg", segment))

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [seg("all")],
            [seg("pro"), seg("free")],
            [seg("lang:uz"), seg("lang:ru"), seg("lang:en")],
            [seg("active_days:7"), seg("active_days:30")],
            [seg("test_admins")],
            [_inline(t(lang, "bc.btn.cancel"), cb_wizard(nonce, "x"))],
        ]
    )


def bc_preview_kb(lang: str, broadcast_id: int, count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_inline(t(lang, "bc.btn.test"), cb_broadcast(broadcast_id, "test"))],
            [_inline(t(lang, "bc.btn.send", count=count), cb_broadcast(broadcast_id, "send"))],
            [_inline(t(lang, "bc.btn.cancel"), cb_broadcast(broadcast_id, "drop"))],
        ]
    )


def bc_progress_kb(
    lang: str, broadcast_id: int, status: str, *, confirm_stop: bool = False
) -> InlineKeyboardMarkup | None:
    """Controls for a queued/running/paused broadcast; None once it has ended."""
    if status not in ("queued", "running", "paused"):
        return None
    if confirm_stop:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    _inline(t(lang, "bc.btn.stop_yes"), cb_broadcast(broadcast_id, "stopok")),
                    _inline(t(lang, "bc.btn.stop_no"), cb_broadcast(broadcast_id, "view")),
                ]
            ]
        )
    toggle = (
        _inline(t(lang, "bc.btn.resume"), cb_broadcast(broadcast_id, "resume"))
        if status == "paused"
        else _inline(t(lang, "bc.btn.pause"), cb_broadcast(broadcast_id, "pause"))
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [toggle, _inline(t(lang, "bc.btn.stop"), cb_broadcast(broadcast_id, "stop"))],
            [_inline(t(lang, "bc.btn.refresh"), cb_broadcast(broadcast_id, "view"))],
        ]
    )


def bc_list_kb(rows: list[tuple[int, str]]) -> InlineKeyboardMarkup | None:
    """One button per listed broadcast: ``(id, label)``."""
    if not rows:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[_inline(label, cb_broadcast(bid, "open"))] for bid, label in rows]
    )


# ── User keyboard ────────────────────────────────────────────────────────

def user_menu_btn(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    """Foydalanuvchi doimiy klaviaturasi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "menu.laws")),
                KeyboardButton(text=t(lang, "menu.hr")),
            ]
        ],
        resize_keyboard=True,
        is_persistent=True,
    )
