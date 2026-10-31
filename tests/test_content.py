"""Tests for the m007 content migration + read/write paths.

Per CONTRACT_P12.md this file builds a MINIMAL app with only
``webapp/routers/content.py`` (public) and ``webapp/routers/admin_content.py``
(admin) mounted, independent of the other Phase 0/2 agents' files.
``get_db`` is overridden onto a temp SQLite file that has had every
migration applied (so ``content_*`` is seeded exactly like a real fresh DB);
``require_role`` is monkeypatched to a stub admin actor before the routers
are (re)imported, matching the pattern in ``tests/test_admin_finance.py``.

The bot-side reader (``src/data/content_repo.py``) is tested separately by
patching its ``connect`` name (like ``tests/test_weekly_stats.py`` does for
its own module) to point at the same seeded temp DB.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from contextlib import asynccontextmanager
from unittest.mock import patch

import aiosqlite
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.data.hr_tips import HR_TIPS
from src.data.law_articles import ARTICLES
from src.db.migrate import run_migrations
from webapp.core import auth as auth_module
from webapp.core.database import get_db
from webapp.core.limiter import limiter

ACTOR_ID = 990002


# --------------------------------------------------------------------------
# Seeded DB (full migration chain, so content_* matches a real fresh install)
# --------------------------------------------------------------------------


async def _build_schema(path: str) -> None:
    conn = await aiosqlite.connect(path)
    try:
        await run_migrations(conn)
    finally:
        await conn.close()


@pytest.fixture
def db_path(tmp_path) -> str:
    path = str(tmp_path / "content_test.sqlite3")
    asyncio.run(_build_schema(path))
    return path


# --------------------------------------------------------------------------
# Minimal app: content + admin_content routers only, require_role stubbed
# --------------------------------------------------------------------------


@pytest.fixture
def client(db_path, monkeypatch):
    def _fake_require_role(min_role: str):
        async def _dep() -> dict:
            return {"user_id": ACTOR_ID, "role": "admin", "user": {"user_id": ACTOR_ID}}

        return _dep

    monkeypatch.setattr(auth_module, "require_role", _fake_require_role)

    # Force fresh imports so `Depends(require_role("admin"))` is built against
    # the stub above rather than a previously-imported real dependency.
    sys.modules.pop("webapp.routers.content", None)
    sys.modules.pop("webapp.routers.admin_content", None)
    content = importlib.import_module("webapp.routers.content")
    admin_content = importlib.import_module("webapp.routers.admin_content")

    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    async def _rate_limited(request, exc):  # pragma: no cover - not expected to trigger
        raise exc

    app.add_exception_handler(RateLimitExceeded, _rate_limited)
    app.include_router(content.router, prefix="/api")
    app.include_router(admin_content.router, prefix="/api")

    async def _override_get_db():
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    app.dependency_overrides[get_db] = _override_get_db
    limiter.enabled = False
    try:
        yield TestClient(app)
    finally:
        limiter.enabled = True
        app.dependency_overrides.pop(get_db, None)
        sys.modules.pop("webapp.routers.content", None)
        sys.modules.pop("webapp.routers.admin_content", None)


# --------------------------------------------------------------------------
# Migration seeding
# --------------------------------------------------------------------------


def test_migration_seeds_articles_and_tips_matching_source_counts(db_path):
    async def _counts():
        conn = await aiosqlite.connect(db_path)
        try:
            conn.row_factory = aiosqlite.Row
            n_articles = (await (await conn.execute("SELECT COUNT(*) AS n FROM content_articles")).fetchone())["n"]
            n_tips = (await (await conn.execute("SELECT COUNT(*) AS n FROM content_tips")).fetchone())["n"]
            n_categories = (
                await (await conn.execute("SELECT COUNT(*) AS n FROM content_categories")).fetchone()
            )["n"]
            return n_articles, n_tips, n_categories
        finally:
            await conn.close()

    n_articles, n_tips, n_categories = asyncio.run(_counts())
    assert n_articles == len(ARTICLES)
    assert n_tips == len(HR_TIPS)
    expected_categories = len({a["category_id"] for a in ARTICLES})
    assert n_categories == expected_categories


def test_migration_is_idempotent_and_does_not_duplicate_rows(db_path):
    async def _rerun_and_count():
        conn = await aiosqlite.connect(db_path)
        try:
            await run_migrations(conn)  # second run: everything already applied/seeded
            conn.row_factory = aiosqlite.Row
            return (await (await conn.execute("SELECT COUNT(*) AS n FROM content_articles")).fetchone())["n"]
        finally:
            await conn.close()

    assert asyncio.run(_rerun_and_count()) == len(ARTICLES)


# --------------------------------------------------------------------------
# Public endpoint: same titles as the old src.data-backed implementation
# --------------------------------------------------------------------------


@pytest.mark.parametrize("lang", ["uz", "ru", "en"])
def test_public_laws_endpoint_matches_source_titles(client, lang):
    resp = client.get(f"/api/content/laws?lang={lang}")
    assert resp.status_code == 200
    body = resp.json()

    from src.data.law_articles import get_articles as source_get_articles

    expected_titles = {a["title"] for a in source_get_articles(lang)}
    actual_titles = {a["title"] for a in body["articles"]}
    assert actual_titles == expected_titles
    assert len(body["articles"]) == len(ARTICLES)


def test_public_law_detail_matches_source(client):
    from src.data.law_articles import get_article as source_get_article

    article_id = ARTICLES[0]["id"]
    resp = client.get(f"/api/content/laws/{article_id}?lang=ru")
    assert resp.status_code == 200
    expected = source_get_article(article_id, "ru")
    body = resp.json()
    assert body["title"] == expected["title"]
    assert body["full_text"] == expected["full_text"]


def test_public_law_detail_404_for_unknown_id(client):
    resp = client.get("/api/content/laws/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["detail"]["code"] == "NOT_FOUND"


# --------------------------------------------------------------------------
# Unpublished: hidden from public, visible to admin
# --------------------------------------------------------------------------


def test_unpublished_article_hidden_from_public_but_visible_to_admin(client, db_path):
    article_id = ARTICLES[0]["id"]

    async def _unpublish():
        conn = await aiosqlite.connect(db_path)
        try:
            await conn.execute("UPDATE content_articles SET published = 0 WHERE id = ?", (article_id,))
            await conn.commit()
        finally:
            await conn.close()

    asyncio.run(_unpublish())

    public_resp = client.get(f"/api/content/laws/{article_id}")
    assert public_resp.status_code == 404

    public_list = client.get("/api/content/laws").json()
    assert article_id not in {a["id"] for a in public_list["articles"]}

    admin_resp = client.get(f"/api/admin/content/articles/{article_id}")
    assert admin_resp.status_code == 200
    assert admin_resp.json()["published"] is False


# --------------------------------------------------------------------------
# Admin PUT: HTML allowlist + per-lang length validation
# --------------------------------------------------------------------------


def _valid_article_payload(category_id: str) -> dict:
    return {
        "category_id": category_id,
        "published": True,
        "source_url": "https://lex.uz/uz/docs/5401895",
        "title": {"uz": "Yangi sarlavha", "ru": "Новый заголовок", "en": "New title"},
        "summary": {"uz": "Qisqa mazmun", "ru": "Краткое содержание", "en": "Short summary"},
        "full_text": {"uz": "<b>To'liq</b> matn.", "ru": "<b>Полный</b> текст.", "en": "<b>Full</b> text."},
        "source_label": {"uz": "Manba"},
    }


def test_put_article_rejects_disallowed_html_tag(client, db_path):
    article_id = ARTICLES[0]["id"]
    category_id = ARTICLES[0]["category_id"]
    payload = _valid_article_payload(category_id)
    payload["full_text"]["uz"] = "<script>alert(1)</script>"

    resp = client.put(f"/api/admin/content/articles/{article_id}", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_put_article_rejects_unbalanced_tags(client, db_path):
    article_id = ARTICLES[0]["id"]
    category_id = ARTICLES[0]["category_id"]
    payload = _valid_article_payload(category_id)
    payload["full_text"]["uz"] = "<b>ochilmagan"

    resp = client.put(f"/api/admin/content/articles/{article_id}", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_put_article_rejects_field_over_length_cap(client, db_path):
    article_id = ARTICLES[0]["id"]
    category_id = ARTICLES[0]["category_id"]
    payload = _valid_article_payload(category_id)
    payload["full_text"]["uz"] = "x" * 4001  # cap is 4000

    resp = client.put(f"/api/admin/content/articles/{article_id}", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_put_article_accepts_valid_html_and_persists(client, db_path):
    article_id = ARTICLES[0]["id"]
    category_id = ARTICLES[0]["category_id"]
    payload = _valid_article_payload(category_id)

    resp = client.put(f"/api/admin/content/articles/{article_id}", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"]["uz"] == "Yangi sarlavha"
    assert body["full_text"]["ru"] == "<b>Полный</b> текст."

    # Persisted: a fresh read (own connection) sees the update too.
    again = client.get(f"/api/admin/content/articles/{article_id}")
    assert again.json()["title"]["en"] == "New title"


def test_admin_create_article_validates_slug(client):
    payload = _valid_article_payload(ARTICLES[0]["category_id"])
    payload["id"] = "Not A Slug!"
    resp = client.post("/api/admin/content/articles", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_admin_create_and_delete_article_roundtrip(client):
    payload = _valid_article_payload(ARTICLES[0]["category_id"])
    payload["id"] = "brand-new-article"
    create_resp = client.post("/api/admin/content/articles", json=payload)
    assert create_resp.status_code == 200

    list_resp = client.get("/api/admin/content/articles")
    assert "brand-new-article" in {a["id"] for a in list_resp.json()["items"]}

    delete_resp = client.delete("/api/admin/content/articles/brand-new-article")
    assert delete_resp.status_code == 200

    list_resp2 = client.get("/api/admin/content/articles")
    assert "brand-new-article" not in {a["id"] for a in list_resp2.json()["items"]}


# --------------------------------------------------------------------------
# Bot-side reader: lang fallback to uz when ru is missing
# --------------------------------------------------------------------------


def test_bot_reader_falls_back_to_uz_when_ru_missing(db_path):
    import src.data.content_repo as bot_content_repo

    article_id = ARTICLES[0]["id"]

    async def _clear_ru():
        conn = await aiosqlite.connect(db_path)
        try:
            await conn.execute(
                "UPDATE content_articles SET title_ru = NULL WHERE id = ?", (article_id,)
            )
            await conn.commit()
        finally:
            await conn.close()

    asyncio.run(_clear_ru())

    @asynccontextmanager
    async def fake_connect(*args, **kwargs):
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def _fetch():
        with patch("src.data.content_repo.connect", fake_connect):
            return await bot_content_repo.get_article(article_id, "ru")

    result = asyncio.run(_fetch())
    assert result is not None
    # ru title was cleared -> falls back to the uz title.
    assert result["title"] == ARTICLES[0]["title"]["uz"]


def test_bot_reader_get_tips_and_articles_list(db_path):
    import src.data.content_repo as bot_content_repo

    @asynccontextmanager
    async def fake_connect(*args, **kwargs):
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    async def _fetch():
        with patch("src.data.content_repo.connect", fake_connect):
            articles = await bot_content_repo.get_articles("uz")
            tips = await bot_content_repo.get_tips("uz")
            return articles, tips

    articles, tips = asyncio.run(_fetch())
    assert len(articles) == len(ARTICLES)
    assert len(tips) == len(HR_TIPS)
