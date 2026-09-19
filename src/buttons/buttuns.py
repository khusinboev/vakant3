# ============================================================
# src/buttons/buttuns.py - Aiogram 3.x
# Klaviaturalar til bo'yicha quriladi: har bir funksiya `lang` oladi.
# ============================================================
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from src.i18n import DEFAULT_LANG, t


def main_btn(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    """Admin panelining bosh menyusi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn.admin.stats")),
                KeyboardButton(text=t(lang, "btn.admin.channels")),
            ],
            [KeyboardButton(text=t(lang, "btn.admin.ads"))],
        ],
        resize_keyboard=True,
    )


def channel_btn(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn.admin.channel_add")),
                KeyboardButton(text=t(lang, "btn.admin.channel_del")),
            ],
            [
                KeyboardButton(text=t(lang, "btn.admin.channel_list")),
                KeyboardButton(text=t(lang, "btn.admin.back")),
            ],
        ],
        resize_keyboard=True,
    )


def reklama_btn(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn.admin.forward")),
                KeyboardButton(text=t(lang, "btn.admin.copy")),
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
