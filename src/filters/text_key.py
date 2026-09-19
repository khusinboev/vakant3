# ============================================================
# src/filters/text_key.py
# Tugma matnini til bo'yicha emas, i18n kaliti bo'yicha routing qilish.
#   @router.message(TextKey("menu.laws"))
# uz/ru/en dagi har qanday variant mos keladi.
# ============================================================
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from src.i18n import texts_for_key


class TextKey(BaseFilter):
    """Xabar matni berilgan i18n kalitining biror tildagi qiymatiga teng bo'lsa — True."""

    def __init__(self, *keys: str) -> None:
        if not keys:
            raise ValueError("TextKey uchun kamida bitta kalit kerak")
        self.keys = keys
        self.variants: set[str] = set()
        for key in keys:
            self.variants.update(texts_for_key(key))

    async def __call__(self, message: Message) -> bool:
        text = message.text
        if not isinstance(text, str):
            return False
        return text.strip() in self.variants
