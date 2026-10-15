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
