"""Bot admin panel review fixes (F3).

* ordinary users never reach the role lookup (candidate pre-check);
* progress watchers and the stop question belong to one card, not one broadcast;
* an album at the content step is refused once, its other parts are ignored;
* a draft whose preview card could not be sent does not stay a usable draft,
  and stale drafts do not fill the bot's broadcast list.

Updates go through the real aiogram Dispatcher of ``tests/test_b1_bot_admin.py``
(recording Bot session, temp SQLite). Synthetic ids only.
"""
from __future__ import annotations

import contextlib
import functools

import aiosqlite

from src.db.connection import connect as real_connect
from src.filters import admin as admin_filter
from src.i18n import t
from tests import test_b1_bot_admin as b1

harness = b1.harness
OWNER, ADMIN, VIEWER, STRANGER = b1.OWNER, b1.ADMIN, b1.VIEWER, b1.STRANGER
CUSTOMER = 900000000101  # an ordinary bot user


class _Counter:
    """Counts connections opened by the filter and full role lookups."""

    def __init__(self, db_path, monkeypatch):
        self.connections = 0
        self.lookups: list[int] = []
        bound = functools.partial(real_connect, str(db_path))
        real_resolve = admin_filter.resolve_admin_role

        @contextlib.asynccontextmanager
        async def counting_connect():
            self.connections += 1
            async with bound() as conn:
                yield conn

        async def counting_resolve(conn, user_id, *args, **kwargs):
            self.lookups.append(int(user_id))
            return await real_resolve(conn, user_id, *args, **kwargs)

        monkeypatch.setattr(admin_filter, "connect", counting_connect)
        monkeypatch.setattr(admin_filter, "resolve_admin_role", counting_resolve)
        admin_filter.reset_admin_candidates()


# ─── 1. candidate pre-check ─────────────────────────────────────────────────

async def test_ordinary_users_never_reach_the_role_lookup(harness, monkeypatch):
    counter = _Counter(harness.db_path, monkeypatch)
    await harness.send(CUSTOMER, "Vakansiyalar")  # first event loads the candidate set
    assert counter.connections == 1 and counter.lookups == []
    for i in range(20):
        await harness.send(CUSTOMER, f"menu tap {i}")
        await harness.send(STRANGER, t("uz", "btn.admin.stats"))
    assert counter.connections == 1  # no connection at all after the refresh
    assert counter.lookups == []
    assert harness.session.requests == []


async def test_admins_are_still_rechecked_on_every_update(harness, monkeypatch):
    counter = _Counter(harness.db_path, monkeypatch)
    for _ in range(3):
        await harness.send(OWNER, t("uz", "btn.admin.stats"))
    assert counter.lookups.count(OWNER) == 3
    assert len(harness.texts()) == 3


async def test_a_revoked_admin_is_refused_immediately_despite_the_cache(harness, monkeypatch):
    counter = _Counter(harness.db_path, monkeypatch)
    await harness.send(ADMIN, t("uz", "btn.admin.stats"))
    assert len(harness.texts()) == 1
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE admins SET disabled = 1 WHERE user_id = ?", (ADMIN,))
        await conn.commit()
    assert ADMIN in admin_filter._candidates.ids  # still a cached candidate
    await harness.send(ADMIN, t("uz", "btn.admin.stats"))
    assert len(harness.texts()) == 1  # refused on the very next message
    assert counter.lookups.count(ADMIN) == 2


async def test_a_new_admin_is_picked_up_after_the_ttl(harness, monkeypatch):
    _Counter(harness.db_path, monkeypatch)
    clock = [1000.0]
    monkeypatch.setattr(admin_filter.time, "monotonic", lambda: clock[0])
    await harness.send(CUSTOMER, t("uz", "btn.admin.stats"))
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute(
            "INSERT INTO admins (user_id, role, added_by, added_at, disabled) VALUES (?, 'viewer', NULL, 0, 0)",
            (CUSTOMER,),
        )
        await conn.commit()
    clock[0] += admin_filter.CANDIDATE_TTL_SECONDS - 1
    await harness.send(CUSTOMER, t("uz", "btn.admin.stats"))
    assert harness.texts() == []  # documented delay: not a candidate yet
    clock[0] += 2
    await harness.send(CUSTOMER, t("uz", "btn.admin.stats"))
    assert harness.texts()[0].startswith(t("uz", "admin.stats.header"))


async def test_callbacks_from_non_candidates_are_denied_without_a_query(harness, monkeypatch):
    counter = _Counter(harness.db_path, monkeypatch)
    await harness.tap(STRANGER, "adm:b:1:pause")
    await harness.tap(STRANGER, "adm:b:1:pause")
    assert counter.connections == 1 and counter.lookups == []
    assert harness.last_answer().text == t("uz", "admin.denied")


async def test_a_failed_refresh_falls_back_to_the_full_lookup(harness, monkeypatch):
    calls = []

    @contextlib.asynccontextmanager
    async def broken_then_real():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database is locked")
        async with real_connect(str(harness.db_path)) as conn:
            yield conn

    monkeypatch.setattr(admin_filter, "connect", broken_then_real)
    admin_filter.reset_admin_candidates()
    await harness.send(OWNER, t("uz", "btn.admin.stats"))
    assert harness.texts()[0].startswith(t("uz", "admin.stats.header"))
    assert admin_filter._candidates.ids is None  # the failure was not cached
