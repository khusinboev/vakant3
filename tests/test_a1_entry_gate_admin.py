"""Entry-gate admin bypass follows the same ADMIN_IDS rule as auth.

``ADMIN_IDS`` is bootstrap only: an env id is an owner while no enabled owner
exists. After an owner exists, an admin deleted from the ``admins`` table must
lose the gate bypass even though the server .env still lists them, matching
``webapp.core.auth.resolve_admin_role``.
"""

import sqlite3
import time

import aiosqlite
import pytest

from src.db.migrate import run_migrations
from webapp.core import entry_gate
from webapp.core.auth import resolve_admin_role
from webapp.core.config import get_settings
from webapp.core.entry_gate import evaluate_entry, raise_for_state

OWNER = 900000000201
ENV_ADMIN = 900000000202
NOW = int(time.time())


@pytest.fixture(autouse=True)
def _fresh_column_cache():
    entry_gate.reset_users_columns_cache()
    yield
    entry_gate.reset_users_columns_cache()


@pytest.fixture
def env_admins(monkeypatch):
    monkeypatch.setattr(get_settings(), "ADMIN_IDS", f"{OWNER},{ENV_ADMIN}", raising=False)


@pytest.fixture
async def db(tmp_path):
    conn = await aiosqlite.connect(tmp_path / "gate_admin.sqlite3")
    conn.row_factory = aiosqlite.Row
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS webapp_admin_settings (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            referral_enabled INTEGER NOT NULL DEFAULT 0,
            referral_required_count INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await conn.execute("INSERT OR REPLACE INTO webapp_admin_settings (singleton) VALUES (1)")
    await run_migrations(conn)
    await conn.execute("ALTER TABLE users ADD COLUMN ref_by INTEGER")
    # ENV_ADMIN never pressed /start: only an admin bypass lets them through.
    await conn.execute(
        "INSERT INTO users (user_id, date, lang, started_at) VALUES (?, ?, 'uz', NULL)",
        (ENV_ADMIN, NOW),
    )
    await conn.commit()
    yield conn
    await conn.close()


async def _admin_rows(db) -> list[tuple]:
    cursor = await db.execute("SELECT user_id, role, disabled FROM admins ORDER BY user_id")
    return [tuple(row) for row in await cursor.fetchall()]


async def _add_admin(db, user_id: int, role: str, disabled: int = 0) -> None:
    await db.execute(
        "INSERT INTO admins (user_id, role, added_at, disabled) VALUES (?, ?, ?, ?)",
        (user_id, role, NOW, disabled),
    )
    await db.commit()


async def test_bootstrap_env_admin_is_owner_while_no_owner_exists(db, env_admins):
    state = await evaluate_entry(db, ENV_ADMIN)
    assert state["is_admin"] is True and state["role"] == "owner"
    raise_for_state(state)  # bypass: must not raise
    # The gate is read-only: bootstrapping the row is auth's job.
    assert await _admin_rows(db) == []


async def test_disabled_owner_does_not_end_bootstrap(db, env_admins):
    # Same as auth.has_enabled_owner: only an *enabled* owner ends the bootstrap.
    await _add_admin(db, OWNER, "owner", disabled=1)
    state = await evaluate_entry(db, ENV_ADMIN)
    assert state["is_admin"] is True and state["role"] == "owner"


async def test_removed_admin_loses_bypass_once_an_owner_exists(db, env_admins):
    await _add_admin(db, OWNER, "owner")
    await _add_admin(db, ENV_ADMIN, "admin")
    assert (await evaluate_entry(db, ENV_ADMIN))["role"] == "admin"

    # The owner removes them from the panel; .env still lists the id.
    await db.execute("DELETE FROM admins WHERE user_id = ?", (ENV_ADMIN,))
    await db.commit()

    state = await evaluate_entry(db, ENV_ADMIN)
    assert state["is_admin"] is False and state["role"] is None
    with pytest.raises(Exception) as exc:
        raise_for_state(state)
    assert exc.value.detail["code"] == "BOT_START_REQUIRED"
    # Gate and auth agree on the role.
    assert await resolve_admin_role(db, ENV_ADMIN) is None


async def test_env_admin_never_added_gets_no_bypass_after_owner_exists(db, env_admins):
    await _add_admin(db, OWNER, "owner")
    state = await evaluate_entry(db, ENV_ADMIN)
    assert state["is_admin"] is False and state["role"] is None


async def test_missing_admins_table_falls_back_to_env(db, env_admins):
    await db.execute("DROP TABLE admins")
    await db.commit()
    assert await entry_gate.admin_role(db, ENV_ADMIN) == "owner"
    assert await entry_gate.admin_role(db, 900000000299) is None


class _AdminsLookupFails:
    """Connection proxy whose ``admins`` SELECT raises ``exc``; everything else is real."""

    def __init__(self, conn, exc: Exception):
        self._conn = conn
        self._exc = exc

    async def execute(self, sql, params=()):
        if "FROM admins" in sql:
            raise self._exc
        return await self._conn.execute(sql, params)

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.mark.parametrize(
    "exc",
    [sqlite3.OperationalError("database is locked"), sqlite3.DatabaseError("disk I/O error")],
)
async def test_other_admins_lookup_errors_fail_closed(db, env_admins, exc):
    # Bootstrap state (no owner): only a missing table may grant the env bypass.
    assert await entry_gate.admin_role(_AdminsLookupFails(db, exc), ENV_ADMIN) is None


async def test_missing_table_error_still_bootstraps(db, env_admins):
    exc = sqlite3.OperationalError("no such table: admins")
    assert await entry_gate.admin_role(_AdminsLookupFails(db, exc), ENV_ADMIN) == "owner"
