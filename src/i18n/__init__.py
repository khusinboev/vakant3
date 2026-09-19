# ============================================================
# src/i18n/__init__.py
# Bot tomonidagi i18n qatlami (uz / ru / en).
#
# Ommaviy API:
#   LANGS, DEFAULT_LANG
#   normalize_lang(code) -> "uz" | "ru" | "en"
#   t(lang, key, **kw) -> str
#   texts_for_key(key) -> tuple[str, ...]   (barcha tillardagi variantlar)
#   key_for_text(text) -> str | None        (teskari qidiruv, tugma routing uchun)
# ============================================================
from __future__ import annotations

from typing import Any

from src.i18n.en import STRINGS as _EN
from src.i18n.ru import STRINGS as _RU
from src.i18n.uz import STRINGS as _UZ

LANGS: tuple[str, ...] = ("uz", "ru", "en")
DEFAULT_LANG: str = "uz"

_DICTS: dict[str, dict[str, str]] = {
    "uz": _UZ,
    "ru": _RU,
    "en": _EN,
}


def normalize_lang(code: Any) -> str:
    """Har qanday til kodini uz/ru/en ga keltiradi. Noma'lum qiymat -> uz."""
    if not isinstance(code, str):
        return DEFAULT_LANG
    value = code.strip().lower().replace("_", "-").split("-", 1)[0]
    if value.startswith("ru"):
        return "ru"
    if value.startswith("en"):
        return "en"
    return DEFAULT_LANG


def t(lang: Any, key: str, **kw: Any) -> str:
    """Kalit bo'yicha tarjima. Tarjima yo'q bo'lsa uz ga, u ham yo'q bo'lsa kalitga qaytadi."""
    normalized = normalize_lang(lang)
    value = _DICTS[normalized].get(key)
    if value is None:
        value = _DICTS[DEFAULT_LANG].get(key)
    if value is None:
        return key
    if not kw:
        return value
    try:
        return value.format(**kw)
    except (KeyError, IndexError, ValueError):
        return value


def texts_for_key(key: str) -> tuple[str, ...]:
    """Kalitning barcha tillardagi matnlari (takrorlanmas, tartibi LANGS bo'yicha)."""
    seen: list[str] = []
    for lang in LANGS:
        value = _DICTS[lang].get(key)
        if value is not None and value not in seen:
            seen.append(value)
    return tuple(seen)


def _build_reverse_map() -> dict[str, str]:
    reverse: dict[str, str] = {}
    for lang in LANGS:
        for key, value in _DICTS[lang].items():
            reverse.setdefault(value, key)
    return reverse


_REVERSE_MAP: dict[str, str] = _build_reverse_map()


def key_for_text(text: Any) -> str | None:
    """Tugma matnidan i18n kalitini topadi (barcha tillar bo'yicha)."""
    if not isinstance(text, str):
        return None
    return _REVERSE_MAP.get(text.strip())


__all__ = [
    "LANGS",
    "DEFAULT_LANG",
    "normalize_lang",
    "t",
    "texts_for_key",
    "key_for_text",
]
