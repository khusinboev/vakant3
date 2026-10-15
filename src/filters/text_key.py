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
from src.ui.emoji import strip_leading_emoji


def _bare_variants(*keys: str) -> set[str]:
    variants: set[str] = set()
    for key in keys:
        for text in texts_for_key(key):
            bare = strip_leading_emoji(text)
            if bare:
                variants.add(bare.casefold())
    return variants


def text_matches(text: object, *keys: str) -> bool:
    """True when ``text`` is the label of one of ``keys`` in any language,
    leading emoji ignored (see :class:`TextKey`)."""
    if not isinstance(text, str):
        return False
    bare = strip_leading_emoji(text)
    return bool(bare) and bare.casefold() in _bare_variants(*keys)


class TextKey(BaseFilter):
    """Xabar matni berilgan i18n kalitining biror tildagi qiymatiga teng bo'lsa — True."""

    def __init__(self, *keys: str) -> None:
        if not keys:
            raise ValueError("TextKey uchun kamida bitta kalit kerak")
        self.keys = keys
        # Labels compared without their leading emoji: a button with a custom
        # emoji icon sends the bare label, a fallback button "<emoji> label",
        # and keyboards sent before a label change may carry an older emoji.
        self.variants: set[str] = _bare_variants(*keys)

    async def __call__(self, message: Message) -> bool:
        text = message.text
        if not isinstance(text, str):
            return False
        bare = strip_leading_emoji(text)
        return bool(bare) and bare.casefold() in self.variants
