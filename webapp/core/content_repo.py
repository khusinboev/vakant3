"""Async read/write helpers for ``content_articles``/``content_tips``/``content_categories``.

Public readers (used by ``webapp/routers/content.py``) always filter to
``published = 1`` and fall back to the ``uz`` column whenever the requested
language's column is NULL/empty — ``uz`` is the source language for every
dictionary in this repo (see CLAUDE.md), so it is guaranteed to be non-empty
for a well-formed row.

Admin read/write helpers (used by ``webapp/routers/admin_content.py``) see
every row regardless of ``published`` and operate on the raw multilingual
dict shape (``{"uz": ..., "ru": ..., "en": ...}`` per field) so the panel can
edit every language at once.
"""

from typing import Any

LANGS: tuple[str, ...] = ("uz", "ru", "en")
PROSE_FIELDS_ARTICLE: tuple[str, ...] = ("title", "summary", "full_text", "source_label")
PROSE_FIELDS_TIP: tuple[str, ...] = ("title", "summary", "full_text")


def _pick(row: Any, field: str, lang: str) -> str:
    """``{field}_{lang}`` if present/non-empty, else ``{field}_uz``."""
    if lang != "uz":
        value = row[f"{field}_{lang}"] if f"{field}_{lang}" in row.keys() else None
        if value:
            return str(value)
    return str(row[f"{field}_uz"] or "")


def _localized_dict(row: Any, field: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for lang in LANGS:
        key = f"{field}_{lang}"
        value = row[key] if key in row.keys() else None
        if value:
            out[lang] = str(value)
    out.setdefault("uz", str(row[f"{field}_uz"] or ""))
    return out


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def list_categories_public(db, lang: str) -> list[dict[str, str]]:
    cursor = await db.execute(
        "SELECT id, name_uz, name_ru, name_en FROM content_categories ORDER BY sort_order ASC"
    )
    rows = await cursor.fetchall()
    return [{"id": str(r["id"]), "name": _pick(r, "name", lang)} for r in rows]


async def list_categories_admin(db) -> list[dict[str, Any]]:
    cursor = await db.execute(
        "SELECT id, sort_order, name_uz, name_ru, name_en FROM content_categories ORDER BY sort_order ASC"
    )
    rows = await cursor.fetchall()
    return [
        {
            "id": str(r["id"]),
            "sort_order": int(r["sort_order"]),
            "name": _localized_dict(r, "name"),
        }
        for r in rows
    ]


async def get_category_admin(db, category_id: str) -> dict[str, Any] | None:
    cursor = await db.execute(
        "SELECT id, sort_order, name_uz, name_ru, name_en FROM content_categories WHERE id = ?",
        (category_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return {"id": str(row["id"]), "sort_order": int(row["sort_order"]), "name": _localized_dict(row, "name")}


async def category_exists(db, category_id: str) -> bool:
    cursor = await db.execute("SELECT 1 FROM content_categories WHERE id = ?", (category_id,))
    return await cursor.fetchone() is not None


async def create_category(db, category_id: str, name: dict[str, str], sort_order: int) -> None:
    await db.execute(
        "INSERT INTO content_categories (id, sort_order, name_uz, name_ru, name_en) VALUES (?, ?, ?, ?, ?)",
        (category_id, sort_order, name.get("uz") or "", name.get("ru"), name.get("en")),
    )


async def update_category(db, category_id: str, name: dict[str, str], sort_order: int) -> None:
    await db.execute(
        "UPDATE content_categories SET sort_order = ?, name_uz = ?, name_ru = ?, name_en = ? WHERE id = ?",
        (sort_order, name.get("uz") or "", name.get("ru"), name.get("en"), category_id),
    )


async def delete_category(db, category_id: str) -> None:
    await db.execute("DELETE FROM content_categories WHERE id = ?", (category_id,))


# ---------------------------------------------------------------------------
# Articles
# ---------------------------------------------------------------------------


def _flatten_article_public(row: Any, lang: str, category_name: str) -> dict[str, str]:
    return {
        "id": str(row["id"]),
        "category": category_name,
        "title": _pick(row, "title", lang),
        "summary": _pick(row, "summary", lang),
        "full_text": _pick(row, "full_text", lang),
        "source_url": str(row["source_url"] or ""),
        "source_label": _pick(row, "source_label", lang),
    }


async def list_articles_public(db, lang: str) -> list[dict[str, str]]:
    cursor = await db.execute(
        """
        SELECT a.*, c.name_uz AS cat_name_uz, c.name_ru AS cat_name_ru, c.name_en AS cat_name_en
        FROM content_articles a
        LEFT JOIN content_categories c ON c.id = a.category_id
        WHERE a.published = 1
        ORDER BY a.sort_order ASC
        """
    )
    rows = await cursor.fetchall()
    out = []
    for row in rows:
        cat_uz = row["cat_name_uz"] or row["category_id"]
        cat_ru = row["cat_name_ru"]
        cat_en = row["cat_name_en"]
        if lang == "ru" and cat_ru:
            cat_name = cat_ru
        elif lang == "en" and cat_en:
            cat_name = cat_en
        else:
            cat_name = cat_uz
        out.append(_flatten_article_public(row, lang, cat_name))
    return out


async def get_article_public(db, article_id: str, lang: str) -> dict[str, str] | None:
    cursor = await db.execute(
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
    cat_uz = row["cat_name_uz"] or row["category_id"]
    cat_ru = row["cat_name_ru"]
    cat_en = row["cat_name_en"]
    if lang == "ru" and cat_ru:
        cat_name = cat_ru
    elif lang == "en" and cat_en:
        cat_name = cat_en
    else:
        cat_name = cat_uz
    return _flatten_article_public(row, lang, cat_name)


async def list_articles_admin(db) -> list[dict[str, Any]]:
    cursor = await db.execute("SELECT * FROM content_articles ORDER BY sort_order ASC")
    rows = await cursor.fetchall()
    return [_article_admin_shape(r) for r in rows]


async def get_article_admin(db, article_id: str) -> dict[str, Any] | None:
    cursor = await db.execute("SELECT * FROM content_articles WHERE id = ?", (article_id,))
    row = await cursor.fetchone()
    return _article_admin_shape(row) if row else None


def _article_admin_shape(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "category_id": str(row["category_id"]),
        "sort_order": int(row["sort_order"]),
        "published": bool(int(row["published"])),
        "source_url": row["source_url"] or "",
        "title": _localized_dict(row, "title"),
        "summary": _localized_dict(row, "summary"),
        "full_text": _localized_dict(row, "full_text"),
        "source_label": _localized_dict(row, "source_label"),
    }


async def article_exists(db, article_id: str) -> bool:
    cursor = await db.execute("SELECT 1 FROM content_articles WHERE id = ?", (article_id,))
    return await cursor.fetchone() is not None


async def create_article(db, article_id: str, data: dict[str, Any]) -> None:
    await db.execute(
        """
        INSERT INTO content_articles (
            id, category_id, sort_order, published, source_url,
            title_uz, title_ru, title_en,
            summary_uz, summary_ru, summary_en,
            full_text_uz, full_text_ru, full_text_en,
            source_label_uz, source_label_ru, source_label_en,
            updated_at, updated_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _article_params(article_id, data),
    )


async def update_article(db, article_id: str, data: dict[str, Any]) -> None:
    params = _article_params(article_id, data)
    # Move id (first param) to the end for the WHERE clause.
    await db.execute(
        """
        UPDATE content_articles SET
            category_id = ?, sort_order = ?, published = ?, source_url = ?,
            title_uz = ?, title_ru = ?, title_en = ?,
            summary_uz = ?, summary_ru = ?, summary_en = ?,
            full_text_uz = ?, full_text_ru = ?, full_text_en = ?,
            source_label_uz = ?, source_label_ru = ?, source_label_en = ?,
            updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        params[1:] + (article_id,),
    )


def _article_params(article_id: str, data: dict[str, Any]) -> tuple:
    title = data.get("title") or {}
    summary = data.get("summary") or {}
    full_text = data.get("full_text") or {}
    source_label = data.get("source_label") or {}
    return (
        article_id,
        str(data.get("category_id") or ""),
        int(data.get("sort_order") or 0),
        1 if data.get("published", True) else 0,
        data.get("source_url") or None,
        title.get("uz") or "",
        title.get("ru"),
        title.get("en"),
        summary.get("uz") or "",
        summary.get("ru"),
        summary.get("en"),
        full_text.get("uz") or "",
        full_text.get("ru"),
        full_text.get("en"),
        source_label.get("uz") or "",
        source_label.get("ru"),
        source_label.get("en"),
        int(data.get("updated_at")),
        data.get("updated_by"),
    )


async def delete_article(db, article_id: str) -> None:
    await db.execute("DELETE FROM content_articles WHERE id = ?", (article_id,))


# ---------------------------------------------------------------------------
# Tips
# ---------------------------------------------------------------------------


def _flatten_tip_public(row: Any, lang: str) -> dict[str, str]:
    return {
        "id": str(row["id"]),
        "title": _pick(row, "title", lang),
        "summary": _pick(row, "summary", lang),
        "full_text": _pick(row, "full_text", lang),
    }


async def list_tips_public(db, lang: str) -> list[dict[str, str]]:
    cursor = await db.execute(
        "SELECT * FROM content_tips WHERE published = 1 ORDER BY sort_order ASC"
    )
    rows = await cursor.fetchall()
    return [_flatten_tip_public(r, lang) for r in rows]


async def get_tip_public(db, tip_id: str, lang: str) -> dict[str, str] | None:
    cursor = await db.execute(
        "SELECT * FROM content_tips WHERE published = 1 AND id = ?", (tip_id,)
    )
    row = await cursor.fetchone()
    return _flatten_tip_public(row, lang) if row else None


def _tip_admin_shape(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "sort_order": int(row["sort_order"]),
        "published": bool(int(row["published"])),
        "title": _localized_dict(row, "title"),
        "summary": _localized_dict(row, "summary"),
        "full_text": _localized_dict(row, "full_text"),
    }


async def list_tips_admin(db) -> list[dict[str, Any]]:
    cursor = await db.execute("SELECT * FROM content_tips ORDER BY sort_order ASC")
    rows = await cursor.fetchall()
    return [_tip_admin_shape(r) for r in rows]


async def get_tip_admin(db, tip_id: str) -> dict[str, Any] | None:
    cursor = await db.execute("SELECT * FROM content_tips WHERE id = ?", (tip_id,))
    row = await cursor.fetchone()
    return _tip_admin_shape(row) if row else None


async def tip_exists(db, tip_id: str) -> bool:
    cursor = await db.execute("SELECT 1 FROM content_tips WHERE id = ?", (tip_id,))
    return await cursor.fetchone() is not None


def _tip_params(tip_id: str, data: dict[str, Any]) -> tuple:
    title = data.get("title") or {}
    summary = data.get("summary") or {}
    full_text = data.get("full_text") or {}
    return (
        tip_id,
        int(data.get("sort_order") or 0),
        1 if data.get("published", True) else 0,
        title.get("uz") or "",
        title.get("ru"),
        title.get("en"),
        summary.get("uz") or "",
        summary.get("ru"),
        summary.get("en"),
        full_text.get("uz") or "",
        full_text.get("ru"),
        full_text.get("en"),
        int(data.get("updated_at")),
        data.get("updated_by"),
    )


async def create_tip(db, tip_id: str, data: dict[str, Any]) -> None:
    await db.execute(
        """
        INSERT INTO content_tips (
            id, sort_order, published,
            title_uz, title_ru, title_en,
            summary_uz, summary_ru, summary_en,
            full_text_uz, full_text_ru, full_text_en,
            updated_at, updated_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        _tip_params(tip_id, data),
    )


async def update_tip(db, tip_id: str, data: dict[str, Any]) -> None:
    params = _tip_params(tip_id, data)
    await db.execute(
        """
        UPDATE content_tips SET
            sort_order = ?, published = ?,
            title_uz = ?, title_ru = ?, title_en = ?,
            summary_uz = ?, summary_ru = ?, summary_en = ?,
            full_text_uz = ?, full_text_ru = ?, full_text_en = ?,
            updated_at = ?, updated_by = ?
        WHERE id = ?
        """,
        params[1:] + (tip_id,),
    )


async def delete_tip(db, tip_id: str) -> None:
    await db.execute("DELETE FROM content_tips WHERE id = ?", (tip_id,))
