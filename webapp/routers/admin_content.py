"""Admin CRUD for law articles, HR tips and their categories.

Mounted by the coordinator as ``/admin/content`` under the ``/api`` prefix
(see CONTRACT_P12.md). Every mutation is role-gated (``admin``), rate limited
and written to ``admin_audit_log`` via ``log_admin_action`` before the caller
commits. Reads are role-gated the same way per the m007 contract line
("Role admin") rather than the general viewer/admin split used elsewhere,
since content editing is a single-role area.

HTML in ``full_text``/``summary``/``title``/``source_label``/category
``name`` fields is restricted to a small allowlist
(``<b> <i> <u> <a href> <code> <br>``); anything else — an unknown tag, an
attribute other than ``href`` on ``<a>``, or an unbalanced open/close pair —
is rejected with ``VALIDATION_ERROR``. This is deliberately not a permissive
HTML sanitizer: it is a strict allow-then-reject scanner, so ambiguous input
fails closed.
"""

import html
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from webapp.core import content_repo, errors
from webapp.core.audit import log_admin_action
from webapp.core.auth import require_role
from webapp.core.database import get_db
from webapp.core.limiter import limiter
from webapp.core.request_ip import client_ip as _client_ip

router = APIRouter(prefix="/admin/content", tags=["admin-content"])

CONTENT_NOT_FOUND = "CONTENT_NOT_FOUND"
CONTENT_EXISTS = "CONTENT_EXISTS"
CONTENT_IN_USE = "CONTENT_IN_USE"

SLUG_RE = re.compile(r"^[a-z0-9-]{3,60}$")

# Per-field length caps (chars), applied per language.
FIELD_MAX_LEN: dict[str, int] = {
    "title": 300,
    "summary": 600,
    "full_text": 4000,
    "source_label": 200,
    "name": 100,
}

ALLOWED_TAGS = {"b", "i", "u", "a", "code", "br"}
VOID_TAGS = {"br"}

_TAG_RE = re.compile(
    r"<(?P<closing>/?)(?P<name>[a-zA-Z][a-zA-Z0-9]*)(?P<attrs>(?:\s+[^<>]*?)?)\s*(?P<selfclose>/?)>"
)
_ATTR_RE = re.compile(r'([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(".*?"|\'.*?\')')

#: The only URL schemes an ``<a href>`` may carry. Everything else — most of
#: all ``javascript:`` and ``data:`` — is stored XSS the moment the Mini App
#: renders the article, so it is rejected at write time rather than cleaned at
#: read time (the frontend re-checks as well; see
#: ``webapp/frontend/src/pages/Laws.tsx``).
ALLOWED_HREF_SCHEMES = ("http://", "https://", "tg://", "mailto:")

#: Characters a browser ignores while it works out a URL's scheme. They are the
#: classic ``java\tscript:`` / leading-NUL evasions, so they are removed before
#: the prefix check instead of being allowed to hide one.
_HREF_IGNORED = "".join(chr(c) for c in range(0x21)) + "\x7f"


def href_is_safe(raw: str) -> bool:
    """True only for an absolute URL in :data:`ALLOWED_HREF_SCHEMES`.

    The value is HTML-unescaped first (``&#106;avascript:`` is ``javascript:``
    by the time the browser sees it) and stripped of every character a browser
    skips when parsing a scheme, then matched case-insensitively against the
    allowlist. Relative and scheme-less hrefs fail too: an article link is
    always an outbound source link, so "absolute or nothing" costs nothing and
    removes a whole class of ambiguity.
    """
    value = html.unescape(str(raw or ""))
    collapsed = value.translate({ord(ch): None for ch in _HREF_IGNORED}).lower()
    return collapsed.startswith(ALLOWED_HREF_SCHEMES)


def _html_is_valid(value: str) -> bool:
    """Strict allowlist scanner: unknown tags/attrs or unbalanced tags fail."""
    stack: list[str] = []
    last_end = 0
    for m in _TAG_RE.finditer(value):
        gap = value[last_end:m.start()]
        if "<" in gap or ">" in gap:
            return False
        last_end = m.end()
        name = m.group("name").lower()
        if name not in ALLOWED_TAGS:
            return False
        closing = m.group("closing") == "/"
        selfclose = m.group("selfclose") == "/"
        attrs_raw = (m.group("attrs") or "").strip()
        if closing:
            if attrs_raw or not stack or stack[-1] != name:
                return False
            stack.pop()
            continue
        if name == "a":
            attr_matches = _ATTR_RE.findall(attrs_raw)
            attr_names = {a[0].lower() for a in attr_matches}
            if attr_names - {"href"} or "href" not in attr_names:
                return False
            href = next(a[1] for a in attr_matches if a[0].lower() == "href")[1:-1]
            if not href_is_safe(href):
                return False
        elif attrs_raw:
            return False
        if name not in VOID_TAGS and not selfclose:
            stack.append(name)
    tail = value[last_end:]
    if "<" in tail or ">" in tail:
        return False
    return not stack


def _validate_localized(field: str, value: dict[str, str | None] | None, *, require_uz: bool) -> dict[str, str]:
    max_len = FIELD_MAX_LEN.get(field, 4000)
    data = dict(value or {})
    uz = str(data.get("uz") or "").strip()
    if require_uz and not uz:
        raise errors.validation_error(field=f"{field}.uz")
    cleaned: dict[str, str] = {}
    for lang in ("uz", "ru", "en"):
        raw = data.get(lang)
        if raw is None:
            continue
        text = str(raw)
        if len(text) > max_len:
            raise errors.validation_error(field=f"{field}.{lang}")
        if text and not _html_is_valid(text):
            raise errors.validation_error(field=f"{field}.{lang}")
        cleaned[lang] = text
    cleaned.setdefault("uz", uz)
    return cleaned




# ── Schemas ─────────────────────────────────────────────────


class LocalizedIn(BaseModel):
    uz: str
    ru: str | None = None
    en: str | None = None


class LocalizedOptionalIn(BaseModel):
    uz: str | None = None
    ru: str | None = None
    en: str | None = None


class ArticleIn(BaseModel):
    category_id: str
    sort_order: int | None = None
    published: bool = True
    source_url: str | None = None
    title: LocalizedIn
    summary: LocalizedIn
    full_text: LocalizedIn
    source_label: LocalizedOptionalIn = Field(default_factory=LocalizedOptionalIn)


class ArticleCreateIn(ArticleIn):
    id: str


class TipIn(BaseModel):
    sort_order: int | None = None
    published: bool = True
    title: LocalizedIn
    summary: LocalizedIn
    full_text: LocalizedIn


class TipCreateIn(TipIn):
    id: str


class CategoryIn(BaseModel):
    sort_order: int | None = None
    name: LocalizedIn


class CategoryCreateIn(CategoryIn):
    id: str


# ── Articles ────────────────────────────────────────────────


@router.get("/articles")
@limiter.limit("60/minute")
async def list_articles(
    request: Request, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, Any]:
    return {"items": await content_repo.list_articles_admin(db)}


@router.get("/articles/{article_id}")
@limiter.limit("60/minute")
async def get_article(
    request: Request, article_id: str, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, Any]:
    article = await content_repo.get_article_admin(db, article_id)
    if not article:
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="article")
    return article


@router.post("/articles")
@limiter.limit("10/minute")
async def create_article(
    request: Request,
    payload: ArticleCreateIn,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    if not SLUG_RE.match(payload.id):
        raise errors.validation_error(field="id")
    if await content_repo.article_exists(db, payload.id):
        raise errors.api_error(409, CONTENT_EXISTS, resource="article", id=payload.id)
    if not await content_repo.category_exists(db, payload.category_id):
        raise errors.validation_error(field="category_id")

    data = _article_data(payload, actor_id=int(admin["user_id"]))
    await content_repo.create_article(db, payload.id, data)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.article.create",
        target_type="article",
        target_id=payload.id,
        payload={"category_id": payload.category_id},
        ip=_client_ip(request),
    )
    await db.commit()
    return await content_repo.get_article_admin(db, payload.id)


@router.put("/articles/{article_id}")
@limiter.limit("10/minute")
async def update_article(
    request: Request,
    article_id: str,
    payload: ArticleIn,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    if not await content_repo.article_exists(db, article_id):
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="article")
    if not await content_repo.category_exists(db, payload.category_id):
        raise errors.validation_error(field="category_id")

    data = _article_data(payload, actor_id=int(admin["user_id"]))
    await content_repo.update_article(db, article_id, data)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.article.update",
        target_type="article",
        target_id=article_id,
        payload={"category_id": payload.category_id, "published": payload.published},
        ip=_client_ip(request),
    )
    await db.commit()
    return await content_repo.get_article_admin(db, article_id)


@router.delete("/articles/{article_id}")
@limiter.limit("10/minute")
async def delete_article(
    request: Request, article_id: str, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, bool]:
    if not await content_repo.article_exists(db, article_id):
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="article")
    await content_repo.delete_article(db, article_id)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.article.delete",
        target_type="article",
        target_id=article_id,
        ip=_client_ip(request),
    )
    await db.commit()
    return {"ok": True}


def _article_data(payload: ArticleIn, *, actor_id: int) -> dict[str, Any]:
    return {
        "category_id": payload.category_id,
        "sort_order": payload.sort_order or 0,
        "published": payload.published,
        "source_url": payload.source_url,
        "title": _validate_localized("title", payload.title.model_dump(), require_uz=True),
        "summary": _validate_localized("summary", payload.summary.model_dump(), require_uz=True),
        "full_text": _validate_localized("full_text", payload.full_text.model_dump(), require_uz=True),
        "source_label": _validate_localized(
            "source_label", payload.source_label.model_dump(), require_uz=False
        ),
        "updated_at": int(time.time()),
        "updated_by": actor_id,
    }


# ── Tips ────────────────────────────────────────────────────


@router.get("/tips")
@limiter.limit("60/minute")
async def list_tips(
    request: Request, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, Any]:
    return {"items": await content_repo.list_tips_admin(db)}


@router.get("/tips/{tip_id}")
@limiter.limit("60/minute")
async def get_tip(
    request: Request, tip_id: str, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, Any]:
    tip = await content_repo.get_tip_admin(db, tip_id)
    if not tip:
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="tip")
    return tip


@router.post("/tips")
@limiter.limit("10/minute")
async def create_tip(
    request: Request,
    payload: TipCreateIn,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    if not SLUG_RE.match(payload.id):
        raise errors.validation_error(field="id")
    if await content_repo.tip_exists(db, payload.id):
        raise errors.api_error(409, CONTENT_EXISTS, resource="tip", id=payload.id)

    data = _tip_data(payload, actor_id=int(admin["user_id"]))
    await content_repo.create_tip(db, payload.id, data)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.tip.create",
        target_type="tip",
        target_id=payload.id,
        ip=_client_ip(request),
    )
    await db.commit()
    return await content_repo.get_tip_admin(db, payload.id)


@router.put("/tips/{tip_id}")
@limiter.limit("10/minute")
async def update_tip(
    request: Request,
    tip_id: str,
    payload: TipIn,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    if not await content_repo.tip_exists(db, tip_id):
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="tip")

    data = _tip_data(payload, actor_id=int(admin["user_id"]))
    await content_repo.update_tip(db, tip_id, data)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.tip.update",
        target_type="tip",
        target_id=tip_id,
        payload={"published": payload.published},
        ip=_client_ip(request),
    )
    await db.commit()
    return await content_repo.get_tip_admin(db, tip_id)


@router.delete("/tips/{tip_id}")
@limiter.limit("10/minute")
async def delete_tip(
    request: Request, tip_id: str, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, bool]:
    if not await content_repo.tip_exists(db, tip_id):
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="tip")
    await content_repo.delete_tip(db, tip_id)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.tip.delete",
        target_type="tip",
        target_id=tip_id,
        ip=_client_ip(request),
    )
    await db.commit()
    return {"ok": True}


def _tip_data(payload: TipIn, *, actor_id: int) -> dict[str, Any]:
    return {
        "sort_order": payload.sort_order or 0,
        "published": payload.published,
        "title": _validate_localized("title", payload.title.model_dump(), require_uz=True),
        "summary": _validate_localized("summary", payload.summary.model_dump(), require_uz=True),
        "full_text": _validate_localized("full_text", payload.full_text.model_dump(), require_uz=True),
        "updated_at": int(time.time()),
        "updated_by": actor_id,
    }


# ── Categories ──────────────────────────────────────────────


@router.get("/categories")
@limiter.limit("60/minute")
async def list_categories(
    request: Request, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, Any]:
    return {"items": await content_repo.list_categories_admin(db)}


@router.get("/categories/{category_id}")
@limiter.limit("60/minute")
async def get_category(
    request: Request, category_id: str, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, Any]:
    category = await content_repo.get_category_admin(db, category_id)
    if not category:
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="category")
    return category


@router.post("/categories")
@limiter.limit("10/minute")
async def create_category(
    request: Request,
    payload: CategoryCreateIn,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    if not SLUG_RE.match(payload.id):
        raise errors.validation_error(field="id")
    if await content_repo.category_exists(db, payload.id):
        raise errors.api_error(409, CONTENT_EXISTS, resource="category", id=payload.id)

    name = _validate_localized("name", payload.name.model_dump(), require_uz=True)
    await content_repo.create_category(db, payload.id, name, payload.sort_order or 0)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.category.create",
        target_type="category",
        target_id=payload.id,
        ip=_client_ip(request),
    )
    await db.commit()
    return await content_repo.get_category_admin(db, payload.id)


@router.put("/categories/{category_id}")
@limiter.limit("10/minute")
async def update_category(
    request: Request,
    category_id: str,
    payload: CategoryIn,
    admin=Depends(require_role("admin")),
    db=Depends(get_db),
) -> dict[str, Any]:
    if not await content_repo.category_exists(db, category_id):
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="category")

    name = _validate_localized("name", payload.name.model_dump(), require_uz=True)
    await content_repo.update_category(db, category_id, name, payload.sort_order or 0)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.category.update",
        target_type="category",
        target_id=category_id,
        ip=_client_ip(request),
    )
    await db.commit()
    return await content_repo.get_category_admin(db, category_id)


@router.delete("/categories/{category_id}")
@limiter.limit("10/minute")
async def delete_category(
    request: Request, category_id: str, admin=Depends(require_role("admin")), db=Depends(get_db)
) -> dict[str, bool]:
    if not await content_repo.category_exists(db, category_id):
        raise errors.api_error(404, CONTENT_NOT_FOUND, resource="category")
    cursor = await db.execute(
        "SELECT COUNT(*) AS n FROM content_articles WHERE category_id = ?", (category_id,)
    )
    row = await cursor.fetchone()
    if row and int(row["n"]) > 0:
        raise errors.api_error(409, CONTENT_IN_USE, resource="category", id=category_id)
    await content_repo.delete_category(db, category_id)
    await log_admin_action(
        db,
        actor_id=int(admin["user_id"]),
        action="content.category.delete",
        target_type="category",
        target_id=category_id,
        ip=_client_ip(request),
    )
    await db.commit()
    return {"ok": True}
