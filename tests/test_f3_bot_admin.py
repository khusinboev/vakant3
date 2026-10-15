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

import asyncio
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


# ─── 2. one watcher and one stop question per card ──────────────────────────

CARD = 777  # message id of the card ``harness.tap`` presses by default


def _cards(broadcast_id, user_id=None):
    return [
        key for key, task in b1.admin_handlers._watchers.items()
        if key[0] == broadcast_id and (user_id is None or key[1] == user_id) and not task.done()
    ]


async def _queued_with_second_card(harness):
    """OWNER queues (card 777); ADMIN opens the same broadcast from the list."""
    broadcast_id = await b1._queued(harness)
    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:open")
    await asyncio.sleep(0)  # let a cancellation, if any, land
    (admin_card,) = _cards(broadcast_id, ADMIN)
    return broadcast_id, admin_card


async def test_a_second_admin_opening_the_card_keeps_the_first_watcher(harness):
    broadcast_id, admin_card = await _queued_with_second_card(harness)
    assert _cards(broadcast_id) == [(broadcast_id, OWNER, CARD), admin_card]


async def test_pause_restarts_the_watcher_of_this_card_only(harness):
    broadcast_id, admin_card = await _queued_with_second_card(harness)
    owner_task = b1.admin_handlers._watchers[(broadcast_id, OWNER, CARD)]
    owner_task.cancel()  # e.g. it reached its deadline
    await asyncio.sleep(0)
    assert _cards(broadcast_id) == [admin_card]

    await harness.tap(OWNER, f"adm:b:{broadcast_id}:pause")
    assert await b1._status(harness, broadcast_id) == "paused"
    assert set(_cards(broadcast_id)) == {(broadcast_id, OWNER, CARD), admin_card}
    # ADMIN's watcher was neither replaced nor restarted.
    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:resume", message_id=admin_card[2])
    assert set(_cards(broadcast_id)) == {(broadcast_id, OWNER, CARD), admin_card}


async def test_the_stop_question_belongs_to_one_card(harness):
    broadcast_id, admin_card = await _queued_with_second_card(harness)
    owner_card = (broadcast_id, OWNER, CARD)
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:stop")
    assert b1.admin_handlers._stop_pending == {owner_card}

    # ADMIN redraws and re-opens their own card: OWNER's question survives.
    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:view", message_id=admin_card[2])
    admin_view = harness.session.of(b1.EditMessageText)[-1]
    assert f"adm:b:{broadcast_id}:stopok" not in b1._callback_data(admin_view.reply_markup)
    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:open")
    assert b1.admin_handlers._stop_pending == {owner_card}

    # OWNER's card still shows the question when it is redrawn.
    await b1.admin_handlers._render(OWNER, CARD, broadcast_id, "uz")
    owner_view = harness.session.of(b1.EditMessageText)[-1]
    assert b1._callback_data(owner_view.reply_markup) == [
        f"adm:b:{broadcast_id}:stopok", f"adm:b:{broadcast_id}:view",
    ]


async def test_stop_on_a_finished_broadcast_leaves_nothing_pending(harness):
    broadcast_id = await b1._queued(harness)
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE broadcasts SET status = 'done' WHERE id = ?", (broadcast_id,))
        await conn.commit()
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:stop")
    assert b1.admin_handlers._stop_pending == set()
    assert harness.session.of(b1.EditMessageText)[-1].reply_markup is None


async def test_a_finished_job_clears_every_card(harness, monkeypatch):
    monkeypatch.setattr(b1.admin_handlers, "PROGRESS_POLL_SECONDS", 0.01)
    broadcast_id, admin_card = await _queued_with_second_card(harness)
    await harness.tap(OWNER, f"adm:b:{broadcast_id}:stop")
    await harness.tap(ADMIN, f"adm:b:{broadcast_id}:stop", message_id=admin_card[2])
    assert len(b1.admin_handlers._stop_pending) == 2
    tasks = [b1.admin_handlers._watchers[key] for key in _cards(broadcast_id)]
    async with aiosqlite.connect(harness.db_path) as conn:
        await conn.execute("UPDATE broadcasts SET status = 'done' WHERE id = ?", (broadcast_id,))
        await conn.commit()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=2)
    assert b1.admin_handlers._stop_pending == set()
    assert b1.admin_handlers._watchers == {}


async def test_watchers_per_broadcast_are_capped(harness):
    broadcast_id = await b1._queued(harness)
    cap = b1.admin_handlers.MAX_WATCHERS_PER_BROADCAST
    for _ in range(cap + 3):
        await harness.tap(ADMIN, f"adm:b:{broadcast_id}:open")
    await asyncio.sleep(0)
    live = _cards(broadcast_id)
    assert len(live) == cap
    # The newest cards keep ticking; the oldest (OWNER's queue card first) stopped.
    assert (broadcast_id, OWNER, CARD) not in live
    assert all(key[1] == ADMIN for key in live)
