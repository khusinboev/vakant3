# ============================================
# src/buttons/buttuns.py - Aiogram 3.x
# ============================================
import hashlib
import hmac

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

from config import TOKEN, WEBAPP_URL


def _resolve_public_webapp_base() -> str:
    raw = (WEBAPP_URL or "").strip().rstrip("/")
    if raw.startswith("https://"):
        return raw
    # Telegram WebApp buttons require a public HTTPS URL.
    return "https://abitur24.uz"

# Admin panel
main_btn = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊Statistika"), KeyboardButton(text="🔧Kanallar")],
        [KeyboardButton(text="📤Reklama")]
    ],
    resize_keyboard=True
)

channel_btn = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕Kanal qo'shish"), KeyboardButton(text="❌Kanalni olib tashlash")],
        [KeyboardButton(text="📋 Kanallar ro'yxati"), KeyboardButton(text="🔙Orqaga qaytish")]
    ],
    resize_keyboard=True
)

reklama_btn = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📨Forward xabar yuborish"), KeyboardButton(text="📬Oddiy xabar yuborish")],
        [KeyboardButton(text="🔙Orqaga qaytish")]
    ],
    resize_keyboard=True
)

def build_webapp_url(user_id: int, target: str = "home") -> str:
    base_url = _resolve_public_webapp_base() + "/app"
    payload = f"{user_id}:{target}"
    signature = hmac.new(TOKEN.encode(), payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{base_url}?go={target}&uid={user_id}&sig={signature}"


def build_user_menu(user_id: int) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="💼 Ish qidirish", web_app=WebAppInfo(url=build_webapp_url(user_id, "home"))),
                KeyboardButton(text="👤 Profil", web_app=WebAppInfo(url=build_webapp_url(user_id, "profile"))),
            ],
            [
                KeyboardButton(text="🗂 Saqlanganlar", web_app=WebAppInfo(url=build_webapp_url(user_id, "saves"))),
            ],
        ],
        resize_keyboard=True,
    )

# Orqaga qaytish
back_btn = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🔙Orqaga qaytish")]],
    resize_keyboard=True
)
