"""Shared harness for the ``test_b3_*`` admin Users tests.

Unlike ``tests/test_admin_users.py`` (one router, dependencies overridden),
these tests run the REAL ``webapp.main.app`` with the real auth chain —
Bearer session rows, ``admins`` roles, ``require_confirmation`` MACs, the entry
gate — because rank checks and session revocation are only meaningful
against the real identity resolution. Only two things are redirected:

* ``get_db`` opens a fresh connection per request on a temp SQLite file
  (separate connections are what make the concurrency tests real);
* ``admin_users.get_export_connector`` opens the CSV stream's connection on
  the same temp file.

All ids are synthetic (>= 900000000000).
"""

from __future__ import annotations

import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from src.db.migrate import run_migrations
from webapp.core import confirm
from webapp.core.config import get_settings
from webapp.core.database import get_db, open_connection
from webapp.core.session import sign_session_payload
from webapp.main import app
from webapp.routers import admin_users

OWNER = 900_000_000_001
OWNER2 = 900_000_000_002
ADMIN = 900_000_000_003
ADMIN2 = 900_000_000_004
MODERATOR = 900_000_000_005
MODERATOR2 = 900_000_000_006
VIEWER = 900_000_000_007
DISABLED_ADMIN = 900_000_000_008
USER = 900_000_000_010
USER2 = 900_000_000_011
#: Listed in ADMIN_IDS but never inserted into ``admins``.
BOOTSTRAP = 900_000_000_020

ROLES_BY_ID = {
    OWNER: "owner",
    OWNER2: "owner",
    ADMIN: "admin",
    ADMIN2: "admin",
    MODERATOR: "moderator",
    MODERATOR2: "moderator",
    VIEWER: "viewer",
}

BOT_OWNED_DDL = (
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, date INTEGER, lang TEXT, region TEXT, district TEXT,
        specs TEXT, money INTEGER, ref_by INTEGER, username TEXT, first_name TEXT,
        photo_url TEXT, user_balance INTEGER DEFAULT 0, user_pro INTEGER DEFAULT 0,
        pref_filters_json TEXT, blocked INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE TABLE IF NOT EXISTS channels (id TEXT PRIMARY KEY)",
    """
    CREATE TABLE IF NOT EXISTS webapp_sessions (
        token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
        created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bot_handoff_tokens (
        token TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
        used INTEGER NOT NULL DEFAULT 0, expires_at INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notification_settings (
        user_id INTEGER PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
        created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
    )
    """,
)


class Harness:
    """The temp database plus the HTTP client against the real app."""

    def __init__(self, path: Path, http: AsyncClient) -> None:
        self.path = path
        self.http = http

    @asynccontextmanager
    async def conn(self):
        conn = await aiosqlite.connect(self.path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            await conn.close()

    async def query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        async with self.conn() as conn:
            cursor = await conn.execute(sql, params)
            return [dict(row) for row in await cursor.fetchall()]

    async def scalar(self, sql: str, params: tuple = ()) -> Any:
        rows = await self.query(sql, params)
        return next(iter(rows[0].values())) if rows else None

    async def execute(self, sql: str, params: tuple = ()) -> None:
        async with self.conn() as conn:
            await conn.execute(sql, params)
            await conn.commit()

    async def add_user(self, user_id: int, **fields: Any) -> None:
        columns: dict[str, Any] = {
            "user_id": user_id,
            "date": fields.pop("date", 1_700_000_000 + user_id % 100_000),
            "lang": fields.pop("lang", "uz"),
            "started_at": fields.pop("started_at", 1_700_000_000),
            "user_balance": fields.pop("user_balance", 0),
            "user_pro": fields.pop("user_pro", 0),
        }
        columns.update(fields)
        names = ", ".join(columns)
        marks = ", ".join("?" for _ in columns)
        await self.execute(
            f"INSERT INTO users ({names}) VALUES ({marks})", tuple(columns.values())
        )

    async def set_admin(self, user_id: int, role: str, disabled: int = 0) -> None:
        await self.execute(
            "INSERT OR REPLACE INTO admins (user_id, role, added_by, added_at, disabled) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, role, OWNER, int(time.time()), disabled),
        )

    async def session(self, user_id: int) -> dict[str, str]:
        """A real session row and the Bearer header that points at it."""
        now = int(time.time())
        exp = now + 3600
        sid = secrets.token_urlsafe(24)
        await self.execute(
            "INSERT INTO webapp_sessions (token, user_id, created_at, expires_at) "
            "VALUES (?, ?, ?, ?)",
            (sid, user_id, now, exp),
        )
        return {"Authorization": f"Bearer {sign_session_payload({'sid': sid, 'exp': exp})}"}

    async def sessions_of(self, user_id: int) -> int:
        return int(
            await self.scalar("SELECT COUNT(*) FROM webapp_sessions WHERE user_id = ?", (user_id,))
        )

    async def audit(self, action: str) -> list[dict[str, Any]]:
        return await self.query(
            "SELECT actor_id, action, target_id, payload_json FROM admin_audit_log "
            "WHERE action = ? ORDER BY id",
            (action,),
        )

    async def ledger_rows(self, user_id: int) -> list[dict[str, Any]]:
        return await self.query(
            "SELECT id, kind, amount, balance_after, actor_id FROM wallet_transactions "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        )

    async def balance(self, user_id: int) -> int:
        return int(
            await self.scalar("SELECT COALESCE(user_balance, 0) FROM users WHERE user_id = ?", (user_id,))
        )


def confirm_header(actor_id: int, action: str, params: dict[str, Any]) -> dict[str, str]:
    """A valid ``X-Confirm-Token`` minted exactly as ``POST /admin/confirm`` mints it."""
    return {"X-Confirm-Token": confirm.issue_confirm_token(actor_id, action, params)}


async def build_schema(path: Path) -> None:
    async with aiosqlite.connect(path) as conn:
        conn.row_factory = aiosqlite.Row
        for ddl in BOT_OWNED_DDL:
            await conn.execute(ddl)
        await conn.commit()
        await run_migrations(conn)
        await conn.execute("INSERT OR IGNORE INTO webapp_admin_settings (singleton) VALUES (1)")
        await conn.commit()


@pytest.fixture
async def harness(tmp_path, monkeypatch):
    path = tmp_path / "b3.sqlite3"
    await build_schema(path)

    async def _get_db():
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
        finally:
            await conn.close()

    def _connector():
        return lambda: open_connection(path)

    monkeypatch.setattr(get_settings(), "ADMIN_IDS", str(BOOTSTRAP), raising=False)
    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[admin_users.get_export_connector] = _connector
    limiter = app.state.limiter
    previously = limiter.enabled
    limiter.enabled = False

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        h = Harness(path, http)
        # One owner exists, so BOOTSTRAP is NOT an owner unless a test removes it.
        for user_id, role in ROLES_BY_ID.items():
            await h.add_user(user_id)
            await h.set_admin(user_id, role)
        await h.add_user(DISABLED_ADMIN)
        await h.set_admin(DISABLED_ADMIN, "admin", disabled=1)
        await h.add_user(USER)
        await h.add_user(USER2)
        await h.add_user(BOOTSTRAP)
        try:
            yield h
        finally:
            app.dependency_overrides.pop(get_db, None)
            app.dependency_overrides.pop(admin_users.get_export_connector, None)
            limiter.enabled = previously
