"""Bot admin roles: parity with the API rule, the IsAdmin filter, audit rows.

``src/functions/admin_roles.py`` is a copy of the API rule (the bot may not
import ``webapp``). The parity test runs the bot copy and both API
implementations on the same database for every case, so a change on one side
that is not mirrored on the other fails here.
"""
from __future__ import annotations

import functools
import json
from types import SimpleNamespace
from unittest.mock import patch

import aiosqlite
import pytest

from src.db.connection import connect as real_connect
from src.db.migrations import m002_admins, m003_audit_log
from src.filters import admin as admin_filter
from src.functions import admin_audit, admin_roles

ENV_ADMIN = 1  # tests/conftest.py sets ADMIN_IDS=1
OTHER = 900000000001
THIRD = 900000000002

# (name, create_table, rows [(user_id, role, disabled)], user_id, expected)
CASES = [
    ("no_table_env_id", False, [], ENV_ADMIN, "owner"),
    ("no_table_stranger", False, [], OTHER, None),
    ("empty_table_env_id", True, [], ENV_ADMIN, "owner"),
    ("empty_table_stranger", True, [], OTHER, None),
    ("owner_exists_env_id_without_row", True, [(OTHER, "owner", 0)], ENV_ADMIN, None),
    ("env_id_disabled_row", True, [(ENV_ADMIN, "owner", 1)], ENV_ADMIN, None),
    ("admin_row", True, [(OTHER, "admin", 0)], OTHER, "admin"),
    ("moderator_row", True, [(OTHER, "moderator", 0)], OTHER, "moderator"),
    ("viewer_row", True, [(OTHER, "viewer", 0)], OTHER, "viewer"),
    ("unknown_role_degrades", True, [(OTHER, "root", 0)], OTHER, "viewer"),
    ("only_disabled_owner_env_id", True, [(OTHER, "owner", 1)], ENV_ADMIN, "owner"),
    ("non_owner_admin_env_id", True, [(OTHER, "admin", 0)], ENV_ADMIN, "owner"),
    ("env_id_with_viewer_row", True, [(ENV_ADMIN, "viewer", 0), (OTHER, "owner", 0)], ENV_ADMIN, "viewer"),
    ("disabled_admin_row", True, [(OTHER, "admin", 1), (THIRD, "owner", 0)], OTHER, None),
    ("stranger_with_owner", True, [(THIRD, "owner", 0)], OTHER, None),
]


async def _make_db(path, create_table: bool, rows) -> None:
    async with aiosqlite.connect(path) as conn:
        await conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
        if create_table:
            await m002_admins.apply(conn)
            await conn.executemany(
                "INSERT INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, ?, NULL, 0, ?)",
                rows,
            )
        await conn.commit()


@pytest.mark.parametrize("name, create_table, rows, user_id, expected", CASES, ids=[c[0] for c in CASES])
async def test_role_parity_with_the_api(tmp_path, name, create_table, rows, user_id, expected):
    from webapp.core.auth import resolve_admin_role as api_resolve
    from webapp.core.entry_gate import admin_role as gate_role

    path = tmp_path / f"{name}.sqlite3"
    await _make_db(path, create_table, rows)
    async with real_connect(str(path)) as conn:
        bot_role = await admin_roles.resolve_admin_role(conn, user_id)
        gate = await gate_role(conn, user_id)
        api = await api_resolve(conn, user_id)  # may bootstrap a row: run last
    assert bot_role == expected
    assert bot_role == gate == api


async def test_resolve_never_writes(tmp_path):
    path = tmp_path / "ro.sqlite3"
    await _make_db(path, True, [])
    async with real_connect(str(path)) as conn:
        assert await admin_roles.resolve_admin_role(conn, ENV_ADMIN) == "owner"
        cursor = await conn.execute("SELECT COUNT(*) FROM admins")
        assert (await cursor.fetchone())[0] == 0


async def test_other_failures_fail_closed():
    class Broken:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("database is locked")

    assert await admin_roles.resolve_admin_role(Broken(), ENV_ADMIN) is None


def test_has_role_ranks():
    assert admin_roles.has_role("owner", "admin")
    assert admin_roles.has_role("admin", "admin")
    assert not admin_roles.has_role("moderator", "admin")
    assert not admin_roles.has_role("viewer", "moderator")
    assert admin_roles.has_role("viewer", "viewer")
    assert not admin_roles.has_role(None, "viewer")
    assert not admin_roles.has_role("root", "viewer")
    with pytest.raises(ValueError):
        admin_roles.has_role("owner", "superuser")


async def test_broadcast_admin_ids_matches_the_api(tmp_path):
    path = tmp_path / "ids.sqlite3"
    await _make_db(path, True, [(OTHER, "admin", 0), (THIRD, "viewer", 1)])
    async with real_connect(str(path)) as conn:
        assert await admin_roles.broadcast_admin_ids(conn) == [ENV_ADMIN, OTHER]


# ─── IsAdmin filter ─────────────────────────────────────────────────────────

@pytest.fixture
async def roles_db(tmp_path):
    path = tmp_path / "filter.sqlite3"
    await _make_db(path, True, [(THIRD, "owner", 0), (OTHER, "moderator", 0)])
    with patch.object(admin_filter, "connect", functools.partial(real_connect, str(path))):
        yield path


def _event(user_id):
    return SimpleNamespace(from_user=SimpleNamespace(id=user_id) if user_id else None)


async def test_is_admin_filter_reads_the_table(roles_db):
    viewer_plus = admin_filter.IsAdmin()
    admin_plus = admin_filter.IsAdmin("admin")

    assert await viewer_plus(_event(THIRD)) == {"admin_role": "owner"}
    assert await viewer_plus(_event(OTHER)) == {"admin_role": "moderator"}
    assert await admin_plus(_event(OTHER)) is False
    # The env id is not an owner any more: an enabled owner row exists.
    assert await viewer_plus(_event(ENV_ADMIN)) is False
    assert await viewer_plus(_event(None)) is False


async def test_is_admin_filter_rechecks_on_every_event(roles_db):
    flt = admin_filter.IsAdmin()
    assert await flt(_event(OTHER)) == {"admin_role": "moderator"}
    async with aiosqlite.connect(roles_db) as conn:
        await conn.execute("UPDATE admins SET disabled = 1 WHERE user_id = ?", (OTHER,))
        await conn.commit()
    assert await flt(_event(OTHER)) is False


async def test_is_admin_filter_reuses_the_role_of_the_same_update(roles_db):
    flt = admin_filter.IsAdmin("admin")
    with patch.object(admin_filter, "current_admin_role", side_effect=AssertionError("queried")):
        assert await flt(_event(OTHER), admin_role="admin") == {"admin_role": "admin"}
        assert await flt(_event(OTHER), admin_role="viewer") is False


def test_is_admin_rejects_unknown_role_names():
    with pytest.raises(ValueError):
        admin_filter.IsAdmin("root")


# ─── audit rows ─────────────────────────────────────────────────────────────

async def test_audit_row_is_marked_as_bot_and_not_committed(tmp_path):
    path = tmp_path / "audit.sqlite3"
    async with real_connect(str(path)) as conn:
        await m003_audit_log.apply(conn)
        await conn.commit()
        await admin_audit.log_bot_action(
            conn, actor_id=OTHER, action="broadcast.queue", target_type="broadcast",
            target_id=7, payload={"total": 3},
        )
        await conn.rollback()  # the caller owns the transaction
        cursor = await conn.execute("SELECT COUNT(*) FROM admin_audit_log")
        assert (await cursor.fetchone())[0] == 0

        await admin_audit.log_bot_action(
            conn, actor_id=OTHER, action="broadcast.queue", target_type="broadcast",
            target_id=7, payload={"total": 3},
        )
        await conn.commit()
        cursor = await conn.execute(
            "SELECT actor_id, action, target_type, target_id, payload_json, ip FROM admin_audit_log"
        )
        row = await cursor.fetchone()
    assert (row[0], row[1], row[2], row[3], row[5]) == (OTHER, "broadcast.queue", "broadcast", "7", None)
    assert json.loads(row[4]) == {"total": 3, "source": "bot"}


async def test_audit_rejects_unknown_actions(tmp_path):
    with pytest.raises(ValueError):
        await admin_audit.log_bot_action(None, actor_id=1, action="users.ban")
