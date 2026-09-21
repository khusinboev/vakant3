"""Bot-side DB readers for law articles / HR tips (plain SQL, no webapp import).

Mirrors ``webapp/core/content_repo.py`` in behaviour (published-only, lang
fallback to ``uz``) but is independent of it per CLAUDE.md's "bot -> webapp:
none" rule — the bot never imports from ``webapp``.

``src/data/law_articles.py`` and ``src/data/hr_tips.py`` remain the seed data
for migration ``m007_content`` and are otherwise untouched; ``src/handlers/
content.py`` now reads through this module instead of those two directly, so
edits made in the admin panel show up in the bot immediately.
"""

from __future__ import annotations

from typing import Any

from src.db.connection import connect
from src.i18n import DEFAULT_LANG

LANGS: tuple[str, ...] = ("uz", "ru", "en")


def _pick(row: Any, field: str, lang: str) -> str:
    if lang != "uz":
        value = row[f"{field}_{lang}"]
        if value:
            return str(value)
    return str(row[f"{field}_uz"] or "")


def _flatten_article(row: Any, lang: str, category_name: str) -> dict[str, str]:
    return {
        "id": str(row["id"]),
        "category_id": str(row["category_id"]),
        "category": category_name,
        "title": _pick(row, "title", lang),
        "summary": _pick(row, "summary", lang),
        "full_text": _pick(row, "full_text", lang),
        "source_url": str(row["source_url"] or ""),
        "source_label": _pick(row, "source_label", lang),
    }


def _category_name(row: Any, lang: str) -> str:
    cat_uz = row["cat_name_uz"] or row["category_id"]
    if lang == "ru" and row["cat_name_ru"]:
        return str(row["cat_name_ru"])
    if lang == "en" and row["cat_name_en"]:
        return str(row["cat_name_en"])
    return str(cat_uz)


async def get_articles(lang: str = DEFAULT_LANG) -> list[dict[str, str]]:
    """Published articles, localized, in admin-configured sort order."""
    async with connect() as conn:
        cursor = await conn.execute(
            """
            SELECT a.*, c.name_uz AS cat_name_uz, c.name_ru AS cat_name_ru, c.name_en AS cat_name_en
            FROM content_articles a
            LEFT JOIN content_categories c ON c.id = a.category_id
            WHERE a.published = 1
            ORDER BY a.sort_order ASC
            """
        )
        rows = await cursor.fetchall()
    return [_flatten_article(row, lang, _category_name(row, lang)) for row in rows]


async def get_article(article_id: str, lang: str = DEFAULT_LANG) -> dict[str, str] | None:
    async with connect() as conn:
        cursor = await conn.execute(
            """
            SELECT a.*, c.name_uz AS cat_name_uz, c.name_ru AS cat_name_ru, c.name_en AS cat_name_en
            FROM content_articles a
            LEFT JOIN content_categories c ON c.id = a.category_id
            WHERE a.published = 1 AND a.id = ?
            """,
            (article_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return _flatten_article(row, lang, _category_name(row, lang))


def _flatten_tip(row: Any, lang: str) -> dict[str, str]:
    return {
        "id": str(row["id"]),
        "title": _pick(row, "title", lang),
        "summary": _pick(row, "summary", lang),
        "full_text": _pick(row, "full_text", lang),
    }


async def get_tips(lang: str = DEFAULT_LANG) -> list[dict[str, str]]:
    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT * FROM content_tips WHERE published = 1 ORDER BY sort_order ASC"
        )
        rows = await cursor.fetchall()
    return [_flatten_tip(row, lang) for row in rows]


async def get_tip(tip_id: str, lang: str = DEFAULT_LANG) -> dict[str, str] | None:
    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT * FROM content_tips WHERE published = 1 AND id = ?", (tip_id,)
        )
        row = await cursor.fetchone()
    return _flatten_tip(row, lang) if row else None
