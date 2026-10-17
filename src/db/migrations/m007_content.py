"""Move law articles and HR tips from Python modules into the DB.

Creates ``content_categories``, ``content_articles`` and ``content_tips`` and
seeds them from ``src/data/law_articles.py`` (``ARTICLES``, whose per-field
values are already ``{"uz": ..., "ru": ..., "en": ...}`` dicts, plus
``CATEGORY_TRANSLATIONS``) and ``src/data/hr_tips.py`` (``HR_TIPS``) the first
time each table is empty. Those two source modules stay untouched — they are
now the seed only, never read at request time again.

Idempotent: seeding is skipped once a table has any row, so a second run (or
an admin who has since edited/deleted rows) is never overwritten.
"""

import time

from src.data.hr_tips import HR_TIPS
from src.data.law_articles import ARTICLES, CATEGORY_TRANSLATIONS

ID = "m007_content"


async def _table_empty(conn, table: str) -> bool:
    cursor = await conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
    return await cursor.fetchone() is None


def _lang_value(localized: dict, lang: str) -> str | None:
    value = localized.get(lang) if isinstance(localized, dict) else None
    return value if isinstance(value, str) and value.strip() else None


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS content_categories (
            id TEXT PRIMARY KEY,
            sort_order INTEGER NOT NULL DEFAULT 0,
            name_uz TEXT NOT NULL DEFAULT '',
            name_ru TEXT,
            name_en TEXT
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS content_articles (
            id TEXT PRIMARY KEY,
            category_id TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            published INTEGER NOT NULL DEFAULT 1,
            source_url TEXT,
            title_uz TEXT NOT NULL DEFAULT '',
            title_ru TEXT,
            title_en TEXT,
            summary_uz TEXT NOT NULL DEFAULT '',
            summary_ru TEXT,
            summary_en TEXT,
            full_text_uz TEXT NOT NULL DEFAULT '',
            full_text_ru TEXT,
            full_text_en TEXT,
            source_label_uz TEXT NOT NULL DEFAULT '',
            source_label_ru TEXT,
            source_label_en TEXT,
            updated_at INTEGER NOT NULL,
            updated_by INTEGER
        )
        """
    )
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS content_tips (
            id TEXT PRIMARY KEY,
            sort_order INTEGER NOT NULL DEFAULT 0,
            published INTEGER NOT NULL DEFAULT 1,
            title_uz TEXT NOT NULL DEFAULT '',
            title_ru TEXT,
            title_en TEXT,
            summary_uz TEXT NOT NULL DEFAULT '',
            summary_ru TEXT,
            summary_en TEXT,
            full_text_uz TEXT NOT NULL DEFAULT '',
            full_text_ru TEXT,
            full_text_en TEXT,
            updated_at INTEGER NOT NULL,
            updated_by INTEGER
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_articles_category ON content_articles(category_id)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_articles_published ON content_articles(published, sort_order)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_content_tips_published ON content_tips(published, sort_order)"
    )

    now = int(time.time())

    if await _table_empty(conn, "content_categories"):
        seen: list[str] = []
        for article in ARTICLES:
            category_id = str(article["category_id"])
            if category_id not in seen:
                seen.append(category_id)
        for order, category_id in enumerate(seen):
            names = CATEGORY_TRANSLATIONS.get(category_id, {})
            await conn.execute(
                "INSERT INTO content_categories (id, sort_order, name_uz, name_ru, name_en) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    category_id,
                    order,
                    names.get("uz") or category_id,
                    names.get("ru"),
                    names.get("en"),
                ),
            )

    if await _table_empty(conn, "content_articles"):
        for order, article in enumerate(ARTICLES):
            title = article["title"]
            summary = article["summary"]
            full_text = article["full_text"]
            source_label = article["source_label"]
            await conn.execute(
                """
                INSERT INTO content_articles (
                    id, category_id, sort_order, published, source_url,
                    title_uz, title_ru, title_en,
                    summary_uz, summary_ru, summary_en,
                    full_text_uz, full_text_ru, full_text_en,
                    source_label_uz, source_label_ru, source_label_en,
                    updated_at, updated_by
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    str(article["id"]),
                    str(article["category_id"]),
                    order,
                    article.get("source_url"),
                    _lang_value(title, "uz") or "",
                    _lang_value(title, "ru"),
                    _lang_value(title, "en"),
                    _lang_value(summary, "uz") or "",
                    _lang_value(summary, "ru"),
                    _lang_value(summary, "en"),
                    _lang_value(full_text, "uz") or "",
                    _lang_value(full_text, "ru"),
                    _lang_value(full_text, "en"),
                    _lang_value(source_label, "uz") or "",
                    _lang_value(source_label, "ru"),
                    _lang_value(source_label, "en"),
                    now,
                ),
            )

    if await _table_empty(conn, "content_tips"):
        for order, tip in enumerate(HR_TIPS):
            title = tip["title"]
            summary = tip["summary"]
            full_text = tip["full_text"]
            await conn.execute(
                """
                INSERT INTO content_tips (
                    id, sort_order, published,
                    title_uz, title_ru, title_en,
                    summary_uz, summary_ru, summary_en,
                    full_text_uz, full_text_ru, full_text_en,
                    updated_at, updated_by
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    str(tip["id"]),
                    order,
                    _lang_value(title, "uz") or "",
                    _lang_value(title, "ru"),
                    _lang_value(title, "en"),
                    _lang_value(summary, "uz") or "",
                    _lang_value(summary, "ru"),
                    _lang_value(summary, "en"),
                    _lang_value(full_text, "uz") or "",
                    _lang_value(full_text, "ru"),
                    _lang_value(full_text, "en"),
                    now,
                ),
            )
