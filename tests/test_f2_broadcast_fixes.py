"""F2 broadcast engine fixes from the independent review of stage B.

* A ``ClientDecodeError`` whose cause is a pydantic ``ValidationError``
  ("Failed to deserialize object") means Telegram answered ``ok`` and the
  message was delivered: it is recorded as ``sent`` with the warning kind
  ``sent_unparsed`` and never retried.
* Results collected before a cancellation (SIGTERM on every deploy) or a
  transient ``database is locked`` are persisted instead of leaving the rows
  ``sending`` to be re-sent after the stale-claim reset.
* After a shared flood pause the token bucket is drained, so sending resumes
  at the steady rate instead of a burst of ``capacity`` messages.

The bot is a fake (no Telegram). User ids are synthetic (900000000000+).
"""
import asyncio
import sqlite3
import time
from contextlib import asynccontextmanager

import aiosqlite
import pytest
from aiogram.exceptions import ClientDecodeError, TelegramRetryAfter
from pydantic import BaseModel, ValidationError

from src.db.migrate import run_migrations
from src.functions import broadcast_worker as bw

BASE = 900_000_000_000
T0 = 1_800_000_000

USERS_DDL = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    date INTEGER,
    lang TEXT,
    region TEXT,
    user_pro INTEGER NOT NULL DEFAULT 0,
    blocked INTEGER NOT NULL DEFAULT 0
)
"""


async def _make_db(path, user_count):
    async with aiosqlite.connect(path) as conn:
        await conn.execute(USERS_DDL)
        await conn.executemany(
            "INSERT INTO users (user_id, lang, date) VALUES (?, 'uz', ?)",
            [(BASE + i, int(time.time())) for i in range(1, user_count + 1)],
        )
        await conn.commit()
        await run_migrations(conn)


def _connect_factory(path, timeout=5.0):
    @asynccontextmanager
    async def _connect():
        conn = await aiosqlite.connect(path, timeout=timeout)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    return _connect


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "f2.sqlite3"


@pytest.fixture
def clock(monkeypatch):
    state = {"now": T0}
    monkeypatch.setattr(bw, "_now", lambda: state["now"])
    return state


class VirtualClock:
    """One virtual monotonic clock for the flood pause and the token bucket."""

    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

    def __call__(self):
        return self.t

    async def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.t += max(0.0, seconds)


class FakeBot:
    """``behaviour[user_id]`` is a list of exceptions raised by successive sends."""

    def __init__(self, behaviour=None, clock=None, on_send=None):
        self.calls: list[int] = []
        self.times: list[float] = []
        self.behaviour = {uid: list(items) for uid, items in (behaviour or {}).items()}
        self.clock = clock
        self.on_send = on_send

    async def send_message(self, user_id, text, reply_markup=None):
        self.calls.append(user_id)
        if self.clock is not None:
            self.times.append(self.clock())
        if self.on_send is not None:
            await self.on_send(user_id)
        queue = self.behaviour.get(user_id)
        if queue:
            raise queue.pop(0)
        return object()


async def _new_job(connect):
    async with connect() as conn:
        broadcast_id = await bw.create_broadcast(
            conn, actor_id=BASE, kind="text", text="salom", target={"segment": "all"}
        )
        total = await bw.queue_broadcast(conn, broadcast_id)
        await conn.commit()
    return broadcast_id, total


def _instant_pause():
    clock = VirtualClock()
    return bw.SendPause(clock=clock, sleep=clock.sleep)


async def _run(bot, connect, broadcast_id, **kwargs):
    kwargs.setdefault("bucket", bw.TokenBucket(rate=100_000))
    kwargs.setdefault("pause", _instant_pause())
    return await bw.run_broadcast(bot, broadcast_id, connect=connect, **kwargs)


async def _targets(connect, broadcast_id):
    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT user_id, status, error, error_kind, attempts, next_attempt_at, claimed_at "
            "FROM broadcast_targets WHERE broadcast_id = ? ORDER BY user_id",
            (broadcast_id,),
        )
        return {row["user_id"]: dict(row) for row in await cursor.fetchall()}


async def _job(connect, broadcast_id):
    async with connect() as conn:
        cursor = await conn.execute("SELECT * FROM broadcasts WHERE id = ?", (broadcast_id,))
        return dict(await cursor.fetchone())


# ─── 1. ClientDecodeError after delivery ────────────────────────────────────

class _Message(BaseModel):
    message_id: int


def _validation_error() -> ValidationError:
    try:
        _Message.model_validate({"message_id": "not-a-number"})
    except ValidationError as exc:
        return exc
    raise AssertionError("expected a ValidationError")  # pragma: no cover


def _deserialize_error(ok=True):
    """What aiogram 3.14 raises when Telegram's JSON answer does not fit the model."""
    payload = {"ok": ok, "result": {"message_id": "not-a-number"}}
    return ClientDecodeError("Failed to deserialize object", _validation_error(), payload)


def _decode_error():
    """What aiogram raises for a non-JSON body (an HTML 502 from a proxy)."""
    try:
        import json

        json.loads("<html>502 Bad Gateway</html>")
    except ValueError as exc:
        return ClientDecodeError("Failed to decode object", exc, "<html>502 Bad Gateway</html>")
    raise AssertionError("expected a ValueError")  # pragma: no cover


def test_deserialize_error_is_delivered_not_retried():
    kind, text, retry_after = bw.classify_error(_deserialize_error())
    assert kind == "sent_unparsed"
    assert retry_after is None
    assert text == "Failed to deserialize object"
    assert kind not in bw.TRANSIENT_KINDS
    assert kind not in bw.CONTENT_KINDS
    assert kind in bw.DELIVERED_KINDS
    assert kind in bw.ERROR_KINDS


def test_undecodable_body_stays_a_retryable_network_error():
    kind, _, retry_after = bw.classify_error(_decode_error())
    assert kind == "network" and retry_after is None
    assert kind in bw.TRANSIENT_KINDS


def test_deserialize_error_of_an_explicit_failure_is_not_counted_as_delivered():
    # ``ok: false`` means Telegram refused the call: nothing was delivered.
    kind, _, _ = bw.classify_error(_deserialize_error(ok=False))
    assert kind == "network"


def test_plan_outcome_records_sent_unparsed_as_sent_with_its_warning():
    result = {"user_id": BASE + 1, "status": "sent", "kind": "sent_unparsed",
              "error": "Failed to deserialize object", "file_id": None}
    outcome = bw.plan_outcome(result, attempts_before=0, now=T0)
    assert outcome == {
        "status": "sent", "error": "Failed to deserialize object", "error_kind": "sent_unparsed",
        "attempts": 1, "next_attempt_at": None, "sent_at": T0,
    }


async def test_deserialize_error_sends_exactly_once_and_counts_as_sent(db_path, clock):
    await _make_db(db_path, 3)
    connect = _connect_factory(db_path)
    broadcast_id, _ = await _new_job(connect)
    unparsed = BASE + 2
    bot = FakeBot(behaviour={unparsed: [_deserialize_error()] * bw.MAX_ATTEMPTS})

    # Run well past every backoff: a retried row would be sent again.
    for _ in range(bw.MAX_ATTEMPTS + 1):
        await _run(bot, connect, broadcast_id)
        clock["now"] += bw.BACKOFF_CAP_SECONDS + 1

    assert bot.calls.count(unparsed) == 1
    row = (await _targets(connect, broadcast_id))[unparsed]
    assert (row["status"], row["error_kind"], row["attempts"], row["next_attempt_at"]) == (
        "sent", "sent_unparsed", 1, None,
    )
    assert row["error"] == "Failed to deserialize object"
    job = await _job(connect, broadcast_id)
    assert (job["status"], job["sent"], job["failed"], job["blocked"], job["content_failed"]) == (
        "done", 3, 0, 0, 0,
    )


async def test_undecodable_body_is_retried(db_path, clock):
    await _make_db(db_path, 2)
    connect = _connect_factory(db_path)
    broadcast_id, _ = await _new_job(connect)
    flaky = BASE + 1
    bot = FakeBot(behaviour={flaky: [_decode_error()]})

    await _run(bot, connect, broadcast_id)
    row = (await _targets(connect, broadcast_id))[flaky]
    assert (row["status"], row["error_kind"], row["attempts"]) == ("pending", "network", 1)

    clock["now"] = row["next_attempt_at"]
    await _run(bot, connect, broadcast_id)
    assert bot.calls.count(flaky) == 2
    row = (await _targets(connect, broadcast_id))[flaky]
    assert (row["status"], row["error_kind"], row["attempts"]) == ("sent", None, 2)


# ─── 2. Results survive a cancellation and a locked database ───────────────

def _hang_on(user_id, reached: asyncio.Event):
    async def on_send(uid):
        if uid == user_id:
            reached.set()
            await asyncio.Event().wait()  # in flight until cancelled

    return on_send


async def _cancel_mid_batch(db_path, *, cancel_twice=False):
    await _make_db(db_path, 4)
    connect = _connect_factory(db_path)
    broadcast_id, _ = await _new_job(connect)
    reached = asyncio.Event()
    bot = FakeBot(on_send=_hang_on(BASE + 3, reached))

    task = asyncio.create_task(_run(bot, connect, broadcast_id))
    await asyncio.wait_for(reached.wait(), 5)
    task.cancel()
    if cancel_twice:
        # A second cancel lands while the results are being written.
        for _ in range(3):
            await asyncio.sleep(0)
        task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    return connect, broadcast_id, bot


@pytest.mark.parametrize("cancel_twice", [False, True])
async def test_cancel_mid_batch_persists_the_sends_already_made(db_path, clock, cancel_twice):
    connect, broadcast_id, bot = await _cancel_mid_batch(db_path, cancel_twice=cancel_twice)

    assert bot.calls == [BASE + 1, BASE + 2, BASE + 3]
    rows = await _targets(connect, broadcast_id)
    # Delivered before the cancel: recorded, so no restart sends them again.
    assert [rows[BASE + i]["status"] for i in (1, 2)] == ["sent", "sent"]
    # The send in flight and the unsent rest go back to the queue, not ``sending``.
    for uid in (BASE + 3, BASE + 4):
        assert (rows[uid]["status"], rows[uid]["attempts"], rows[uid]["claimed_at"]) == (
            "pending", 0, None,
        )
    job = await _job(connect, broadcast_id)
    assert (job["status"], job["sent"], job["failed"]) == ("running", 2, 0)


async def test_after_a_cancel_the_next_run_sends_only_the_rest(db_path, clock):
    connect, broadcast_id, bot = await _cancel_mid_batch(db_path)
    bot.on_send = None

    await _run(bot, connect, broadcast_id)
    assert bot.calls == [BASE + 1, BASE + 2, BASE + 3, BASE + 3, BASE + 4]
    job = await _job(connect, broadcast_id)
    assert (job["status"], job["sent"]) == ("done", 4)


async def test_a_locked_database_is_retried_and_the_batch_persisted(db_path, clock, monkeypatch):
    await _make_db(db_path, 3)
    # A short busy timeout, so the lock surfaces as "database is locked" at once.
    connect = _connect_factory(db_path, timeout=0.05)
    broadcast_id, _ = await _new_job(connect)
    monkeypatch.setattr(bw, "WRITE_RETRY_DELAYS", (0.2, 0.2, 0.2, 0.2))
    holder: dict = {}

    async def lock_db(uid):
        if holder:
            return
        # Another writer holds the lock while the batch is sent and for 0.3 s after.
        holder["conn"] = conn = await aiosqlite.connect(db_path)
        await conn.execute("BEGIN IMMEDIATE")

        async def release():
            await asyncio.sleep(0.3)
            await conn.rollback()
            await conn.close()

        holder["task"] = asyncio.create_task(release())

    bot = FakeBot(on_send=lock_db)
    try:
        await _run(bot, connect, broadcast_id)
    finally:
        # Always release the other writer, or its thread outlives the test.
        if "task" in holder:
            await holder["task"]

    assert sorted(bot.calls) == [BASE + 1, BASE + 2, BASE + 3]
    rows = await _targets(connect, broadcast_id)
    assert {row["status"] for row in rows.values()} == {"sent"}
    job = await _job(connect, broadcast_id)
    assert (job["status"], job["sent"]) == ("done", 3)


async def test_write_retry_gives_up_on_errors_that_are_not_a_lock(monkeypatch):
    calls = []

    async def broken_write(*args, **kwargs):
        calls.append(args)
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(bw, "_write_results", broken_write)
    monkeypatch.setattr(bw, "WRITE_RETRY_DELAYS", (0, 0, 0))
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        await bw._write_results_retrying(None, 1, [], None, {}, ())
    assert len(calls) == 1


async def test_write_retry_stops_after_the_last_delay(monkeypatch):
    calls = []

    async def locked_write(*args, **kwargs):
        calls.append(args)
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(bw, "_write_results", locked_write)
    monkeypatch.setattr(bw, "WRITE_RETRY_DELAYS", (0, 0, 0))
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        await bw._write_results_retrying(None, 1, [], None, {}, ())
    assert len(calls) == 4  # the first try plus one per delay
