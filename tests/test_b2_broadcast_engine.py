"""Stage B broadcast engine: error kinds, retry/backoff, shared flood pause, early abort.

The bot is a fake (no Telegram); the clock the worker writes with is pinned
through ``broadcast_worker._now`` and the flood pause gets a virtual clock.
User ids are synthetic (900000000000+).
"""
import asyncio
import time
from contextlib import asynccontextmanager

import aiohttp
import aiosqlite
import pytest
from aiogram.exceptions import (
    ClientDecodeError,
    TelegramBadRequest,
    TelegramEntityTooLarge,
    TelegramForbiddenError,
    TelegramMigrateToChat,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
    TelegramUnauthorizedError,
)

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


def _connect_factory(path):
    @asynccontextmanager
    async def _connect():
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    return _connect


@pytest.fixture
async def connect(tmp_path):
    path = tmp_path / "b2.sqlite3"
    await _make_db(path, 4)
    return _connect_factory(path)


@pytest.fixture
def clock(monkeypatch):
    state = {"now": T0}
    monkeypatch.setattr(bw, "_now", lambda: state["now"])
    return state


class VirtualPause(bw.SendPause):
    """A SendPause on a virtual clock; ``sleeps`` records every wait."""

    def __init__(self):
        self.t = 0.0
        self.sleeps: list[float] = []

        async def _sleep(seconds):
            self.sleeps.append(seconds)
            self.t += seconds

        super().__init__(clock=lambda: self.t, sleep=_sleep)


class FakeBot:
    """``behaviour[user_id]`` is a list of exceptions raised by successive sends."""

    def __init__(self, behaviour=None, default_error=None):
        self.calls: list[int] = []
        self.behaviour = {uid: list(items) for uid, items in (behaviour or {}).items()}
        self.default_error = default_error

    async def send_message(self, user_id, text, reply_markup=None):
        self.calls.append(user_id)
        queue = self.behaviour.get(user_id)
        if queue:
            raise queue.pop(0)
        if self.default_error is not None:
            raise self.default_error
        return object()


async def _new_job(connect):
    async with connect() as conn:
        broadcast_id = await bw.create_broadcast(
            conn, actor_id=BASE, kind="text", text="salom", target={"segment": "all"}
        )
        total = await bw.queue_broadcast(conn, broadcast_id)
        await conn.commit()
    return broadcast_id, total


async def _run(bot, connect, broadcast_id, pause=None, **kwargs):
    return await bw.run_broadcast(
        bot,
        broadcast_id,
        connect=connect,
        bucket=bw.TokenBucket(rate=100_000),
        pause=pause or VirtualPause(),
        **kwargs,
    )


async def _target(connect, broadcast_id, user_id):
    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT status, error, error_kind, attempts, next_attempt_at, claimed_at "
            "FROM broadcast_targets WHERE broadcast_id = ? AND user_id = ?",
            (broadcast_id, user_id),
        )
        return dict(await cursor.fetchone())


async def _job(connect, broadcast_id):
    async with connect() as conn:
        cursor = await conn.execute("SELECT * FROM broadcasts WHERE id = ?", (broadcast_id,))
        return dict(await cursor.fetchone())


def _bad(message):
    return TelegramBadRequest(method=None, message=message)


# ─── Classification ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "exc, kind",
    [
        (TelegramForbiddenError(method=None, message="Forbidden: bot was blocked by the user"), "blocked"),
        (TelegramForbiddenError(method=None, message="Forbidden: bot can't initiate conversation with a user"), "blocked"),
        (TelegramForbiddenError(method=None, message="Forbidden: user is deactivated"), "deactivated"),
        (_bad("Bad Request: user is deactivated"), "deactivated"),
        (_bad("Bad Request: chat not found"), "chat_not_found"),
        (_bad("Bad Request: PEER_ID_INVALID"), "chat_not_found"),
        (_bad("Bad Request: can't parse entities: unsupported start tag"), "bad_request"),
        (_bad("Bad Request: message is too long"), "bad_request"),
        (_bad("Bad Request: wrong file identifier/HTTP URL specified"), "bad_request"),
        (TelegramEntityTooLarge(method=None, message="Request Entity Too Large"), "bad_request"),
        (TelegramRetryAfter(method=None, message="flood", retry_after=7), "flood"),
        (TelegramServerError(method=None, message="Internal Server Error"), "network"),
        (TelegramNetworkError(method=None, message="Request timeout error"), "network"),
        (ClientDecodeError("Failed to decode object", ValueError("x"), "<html>"), "network"),
        (aiohttp.ClientConnectionError("reset"), "network"),
        (asyncio.TimeoutError(), "network"),
        (TelegramUnauthorizedError(method=None, message="Unauthorized"), "other"),
        (TelegramMigrateToChat(method=None, message="migrated", migrate_to_chat_id=-1), "other"),
        (FileNotFoundError("uploads/202610/missing.jpg"), "other"),
    ],
)
def test_classify_error(exc, kind):
    got_kind, text, retry_after = bw.classify_error(exc)
    assert got_kind == kind
    assert text and len(text) <= bw.ERROR_TEXT_LIMIT
    assert retry_after == (7.0 if kind == "flood" else None)


def test_error_text_is_short_and_uses_the_telegram_description():
    kind, text, _ = bw.classify_error(_bad("Bad Request: " + "x" * 1000))
    assert kind == "bad_request"
    assert text.startswith("Bad Request: ") and len(text) == bw.ERROR_TEXT_LIMIT
    assert "Telegram server says" not in text


def test_backoff_doubles_from_ten_seconds_and_is_capped():
    assert [bw.backoff_seconds(n) for n in range(5)] == [10, 20, 40, 80, 160]
    assert bw.backoff_seconds(6) == 600 and bw.backoff_seconds(30) == 600


# ─── Permanent kinds ────────────────────────────────────────────────────────

async def test_permanent_kinds_fail_at_once_with_their_kind(connect, clock):
    broadcast_id, _ = await _new_job(connect)
    bot = FakeBot(
        behaviour={
            BASE + 1: [_bad("Bad Request: can't parse entities")],
            BASE + 2: [TelegramForbiddenError(method=None, message="Forbidden: user is deactivated")],
            BASE + 3: [_bad("Bad Request: chat not found")],
        }
    )
    await _run(bot, connect, broadcast_id)

    assert sorted(bot.calls) == [BASE + 1, BASE + 2, BASE + 3, BASE + 4]  # one send each
    bad = await _target(connect, broadcast_id, BASE + 1)
    assert (bad["status"], bad["error_kind"], bad["attempts"]) == ("failed", "bad_request", 1)
    assert bad["next_attempt_at"] is None and "parse entities" in bad["error"]
    gone = await _target(connect, broadcast_id, BASE + 2)
    assert (gone["status"], gone["error_kind"]) == ("blocked", "deactivated")
    missing = await _target(connect, broadcast_id, BASE + 3)
    assert (missing["status"], missing["error_kind"]) == ("failed", "chat_not_found")
    ok = await _target(connect, broadcast_id, BASE + 4)
    assert (ok["status"], ok["error_kind"], ok["attempts"]) == ("sent", None, 1)

    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT user_id, blocked FROM users WHERE user_id IN (?, ?)", (BASE + 2, BASE + 3)
        )
        flags = {row[0]: row[1] for row in await cursor.fetchall()}
    assert flags == {BASE + 2: 1, BASE + 3: 0}  # deactivated marks the user, chat_not_found does not

    job = await _job(connect, broadcast_id)
    assert (job["status"], job["sent"], job["failed"], job["blocked"]) == ("done", 1, 2, 1)
    assert job["content_failed"] == 1  # only the bad_request one


# ─── Retry with backoff ─────────────────────────────────────────────────────

async def test_network_errors_back_off_and_fail_after_six_attempts(connect, clock):
    broadcast_id, _ = await _new_job(connect)
    flaky = BASE + 2
    bot = FakeBot(
        behaviour={flaky: [TelegramNetworkError(method=None, message="timeout")] * bw.MAX_ATTEMPTS}
    )

    await _run(bot, connect, broadcast_id)
    delays = []
    for attempt in range(1, bw.MAX_ATTEMPTS):
        row = await _target(connect, broadcast_id, flaky)
        assert (row["status"], row["error_kind"], row["attempts"]) == ("pending", "network", attempt)
        assert row["claimed_at"] is None
        delays.append(row["next_attempt_at"] - clock["now"])
        assert (await _job(connect, broadcast_id))["status"] == "running"  # never done early

        # One second early: the row is not claimed, nothing is sent, the job is
        # not picked (the loop would otherwise spin on it).
        clock["now"] = row["next_attempt_at"] - 1
        sends = len(bot.calls)
        async with connect() as conn:
            assert await bw._next_broadcast_id(conn) is None
        await _run(bot, connect, broadcast_id)
        assert len(bot.calls) == sends
        assert await bw.process_once(bot, connect=connect, pause=VirtualPause()) is False

        clock["now"] = row["next_attempt_at"]
        async with connect() as conn:
            assert await bw._next_broadcast_id(conn) == broadcast_id
        await _run(bot, connect, broadcast_id)
        assert len(bot.calls) == sends + 1

    assert delays == [10, 20, 40, 80, 160]
    row = await _target(connect, broadcast_id, flaky)
    assert (row["status"], row["error_kind"], row["attempts"]) == ("failed", "network", 6)
    assert row["next_attempt_at"] is None
    assert bot.calls.count(flaky) == bw.MAX_ATTEMPTS
    job = await _job(connect, broadcast_id)
    assert (job["status"], job["sent"], job["failed"]) == ("done", 3, 1)
    assert job["content_failed"] == 0  # a network failure says nothing about the content


async def test_a_retry_that_succeeds_clears_the_error(connect, clock):
    broadcast_id, _ = await _new_job(connect)
    bot = FakeBot(behaviour={BASE + 1: [TelegramServerError(method=None, message="Bad Gateway")]})
    await _run(bot, connect, broadcast_id)
    clock["now"] += 10
    await _run(bot, connect, broadcast_id)
    row = await _target(connect, broadcast_id, BASE + 1)
    assert (row["status"], row["error"], row["error_kind"], row["attempts"]) == ("sent", None, None, 2)
    async with connect() as conn:
        breakdown = await bw.broadcast_breakdown(conn, broadcast_id)
    assert breakdown["retry"] == {
        "scheduled": 0, "next_attempt_at": None, "retried": 1, "extra_attempts": 1,
    }
    assert (await _job(connect, broadcast_id))["status"] == "done"


async def test_flood_waits_at_least_retry_after(connect, clock):
    broadcast_id, _ = await _new_job(connect)
    bot = FakeBot(behaviour={BASE + 1: [TelegramRetryAfter(method=None, message="flood", retry_after=45)]})
    await _run(bot, connect, broadcast_id)
    row = await _target(connect, broadcast_id, BASE + 1)
    assert (row["status"], row["error_kind"], row["attempts"]) == ("pending", "flood", 1)
    assert row["next_attempt_at"] == T0 + 45  # retry_after beats the 10 s backoff


async def test_a_job_with_only_future_retries_does_not_block_the_next_one(connect, clock):
    waiting_id, _ = await _new_job(connect)
    bot = FakeBot(default_error=TelegramNetworkError(method=None, message="down"))
    await _run(bot, connect, waiting_id)
    assert len(bot.calls) == 4

    bot.default_error = None
    next_id, _ = await _new_job(connect)
    assert await bw.process_once(bot, connect=connect, pause=VirtualPause()) is True
    assert (await _job(connect, next_id))["status"] == "done"
    assert (await _job(connect, waiting_id))["status"] == "running"
    assert await bw.process_once(bot, connect=connect, pause=VirtualPause()) is False
    assert len(bot.calls) == 8


async def test_the_loop_does_not_spin_on_future_retries(connect, clock, monkeypatch):
    broadcast_id, _ = await _new_job(connect)
    bot = FakeBot(default_error=TelegramNetworkError(method=None, message="down"))
    await _run(bot, connect, broadcast_id)
    runs = []
    real_run = bw.run_broadcast

    async def counting_run(*args, **kwargs):
        runs.append(1)
        return await real_run(*args, **kwargs)

    monkeypatch.setattr(bw, "run_broadcast", counting_run)
    task = asyncio.create_task(bw.broadcast_worker_loop(bot, poll_interval=0.02, connect=connect))
    try:
        await asyncio.sleep(0.3)
        assert runs == [] and len(bot.calls) == 4
        clock["now"] += 10  # the retries are due: the loop picks the job again
        for _ in range(100):
            if len(bot.calls) == 8:
                break
            await asyncio.sleep(0.02)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert len(runs) >= 1 and len(bot.calls) == 8


# ─── Shared flood pause ─────────────────────────────────────────────────────

async def test_flood_pauses_every_send_and_releases_the_rest_of_the_batch(connect, clock):
    broadcast_id, _ = await _new_job(connect)
    pause = VirtualPause()
    bot = FakeBot(behaviour={BASE + 2: [TelegramRetryAfter(method=None, message="flood", retry_after=30)]})

    await _run(bot, connect, broadcast_id, pause=pause, max_batches=1)

    # The flood stopped the batch: users 3 and 4 were claimed but not sent.
    assert bot.calls == [BASE + 1, BASE + 2]
    assert pause.remaining() == 30
    for user_id in (BASE + 3, BASE + 4):
        row = await _target(connect, broadcast_id, user_id)
        assert (row["status"], row["attempts"], row["claimed_at"]) == ("pending", 0, None)
        assert row["next_attempt_at"] is None  # released, not penalised
    flooded = await _target(connect, broadcast_id, BASE + 2)
    assert (flooded["status"], flooded["error_kind"]) == ("pending", "flood")

    # The next batch waits out the pause before it opens a connection or claims.
    await _run(bot, connect, broadcast_id, pause=pause, max_batches=1)
    assert pause.sleeps == [30]
    assert bot.calls == [BASE + 1, BASE + 2, BASE + 3, BASE + 4]


async def test_the_pause_is_shared_by_other_broadcasts(connect, clock):
    first_id, _ = await _new_job(connect)
    pause = VirtualPause()
    bot = FakeBot(behaviour={BASE + 1: [TelegramRetryAfter(method=None, message="flood", retry_after=12)]})
    await _run(bot, connect, first_id, pause=pause, max_batches=1)
    assert bot.calls == [BASE + 1]

    second_id, _ = await _new_job(connect)
    await _run(bot, connect, second_id, pause=pause)
    assert pause.sleeps == [12]  # the other job waited for the same pause
    assert bot.calls[1:] == [BASE + 1, BASE + 2, BASE + 3, BASE + 4]


def test_pauses_only_extend_and_are_capped():
    pause = VirtualPause()
    pause.pause_for(30)
    pause.pause_for(5)
    assert pause.remaining() == 30
    pause.pause_for(10 ** 9)
    assert pause.remaining() == bw.MAX_RETRY_AFTER_SECONDS
    pause.pause_for(0)
    pause.pause_for(-3)
    assert pause.remaining() == bw.MAX_RETRY_AFTER_SECONDS


# ─── Early abort ────────────────────────────────────────────────────────────

@pytest.fixture
async def big(tmp_path):
    path = tmp_path / "big.sqlite3"
    await _make_db(path, 500)
    return _connect_factory(path)


async def test_content_rejected_by_every_recipient_aborts_after_200(big, clock):
    broadcast_id, total = await _new_job(big)
    assert total == 500
    bot = FakeBot(default_error=_bad("Bad Request: can't parse entities"))

    await _run(bot, big, broadcast_id)

    assert len(bot.calls) == bw.EARLY_ABORT_MIN_FAILURES  # 10 batches of 20, then stop
    job = await _job(big, broadcast_id)
    assert (job["status"], job["error"]) == ("failed", bw.CONTENT_REJECTED)
    assert job["failed"] == job["content_failed"] == 200 and job["finished_at"] == T0
    async with big() as conn:
        cursor = await conn.execute(
            "SELECT COUNT(*) FROM broadcast_targets WHERE broadcast_id = ? AND status = 'pending'",
            (broadcast_id,),
        )
        assert (await cursor.fetchone())[0] == 300
        assert await bw._next_broadcast_id(conn) is None  # a failed job is never picked again


async def test_a_few_deliveries_do_not_save_a_rejected_message(big, clock):
    broadcast_id, _ = await _new_job(big)
    early = {BASE + i for i in range(1, 6)}  # 5 users get it, then Telegram refuses

    class Bot(FakeBot):
        async def send_message(self, user_id, text, reply_markup=None):
            self.calls.append(user_id)
            if user_id in early:
                return object()
            raise _bad("Bad Request: wrong file identifier")

    bot = Bot()
    await _run(bot, big, broadcast_id)
    job = await _job(big, broadcast_id)
    assert (job["status"], job["error"], job["sent"]) == ("failed", bw.CONTENT_REJECTED, 5)
    assert job["content_failed"] < 260 and len(bot.calls) < 300


async def test_a_healthy_job_with_many_bad_chats_is_not_aborted(big, clock):
    broadcast_id, _ = await _new_job(big)
    bad_users = {BASE + i for i in range(1, 501) if i % 2 == 0}  # 250 of 500 fail

    class Bot(FakeBot):
        async def send_message(self, user_id, text, reply_markup=None):
            self.calls.append(user_id)
            if user_id in bad_users:
                raise _bad("Bad Request: message is too long")
            return object()

    bot = Bot()
    await _run(bot, big, broadcast_id)
    job = await _job(big, broadcast_id)
    assert (job["status"], job["sent"], job["failed"]) == ("done", 250, 250)
    assert len(bot.calls) == 500


async def test_permanent_non_content_failures_never_abort(big, clock):
    broadcast_id, _ = await _new_job(big)
    bot = FakeBot(default_error=TelegramForbiddenError(method=None, message="Forbidden: bot was blocked by the user"))
    await _run(bot, big, broadcast_id)
    job = await _job(big, broadcast_id)
    assert (job["status"], job["blocked"], job["content_failed"]) == ("done", 500, 0)


# ─── Invariants still hold ──────────────────────────────────────────────────

async def test_no_write_transaction_is_open_during_a_send(connect, clock):
    """Another connection can write while the worker is inside a Telegram call."""
    broadcast_id, _ = await _new_job(connect)
    seen = []

    class Bot(FakeBot):
        async def send_message(self, user_id, text, reply_markup=None):
            async with connect() as other:
                await other.execute("PRAGMA busy_timeout = 0")
                await other.execute("UPDATE users SET lang = 'ru' WHERE user_id = ?", (user_id,))
                await other.commit()
            seen.append(user_id)
            if user_id == BASE + 2:
                raise TelegramNetworkError(method=None, message="down")
            return object()

    await _run(Bot(), connect, broadcast_id)
    assert seen == [BASE + 1, BASE + 2, BASE + 3, BASE + 4]


async def test_pause_and_resume_through_the_shared_contract(connect, clock):
    from src.functions.broadcast_control import set_broadcast_state

    broadcast_id, _ = await _new_job(connect)
    bot = FakeBot()

    await _run(bot, connect, broadcast_id, batch_size=2, max_batches=1)
    async with connect() as conn:
        assert await set_broadcast_state(conn, broadcast_id, "pause") == ("running", "paused")
        await conn.commit()
        assert await bw._next_broadcast_id(conn) is None
    await _run(bot, connect, broadcast_id, batch_size=2)
    assert len(bot.calls) == 2  # paused: nothing more is sent
    async with connect() as conn:
        assert await set_broadcast_state(conn, broadcast_id, "resume") == ("paused", "queued")
        await conn.commit()
    await _run(bot, connect, broadcast_id, batch_size=2)
    assert sorted(bot.calls) == [BASE + 1, BASE + 2, BASE + 3, BASE + 4]
    assert (await _job(connect, broadcast_id))["status"] == "done"


# ─── last_attempt_at (m019) ─────────────────────────────────────────────────

async def test_every_result_write_stamps_last_attempt_at(connect, clock):
    broadcast_id, _ = await _new_job(connect)
    forbidden = TelegramForbiddenError(method=None, message="Forbidden: bot was blocked by the user")
    bot = FakeBot({
        BASE + 2: [forbidden],
        BASE + 3: [_bad("Bad Request: chat not found")],
        BASE + 4: [TelegramServerError(method=None, message="Internal Server Error")] * 3,
    })
    await _run(bot, connect, broadcast_id)  # the clock is pinned: the retry is not due yet
    async with connect() as conn:
        cursor = await conn.execute(
            "SELECT user_id, status, last_attempt_at FROM broadcast_targets WHERE broadcast_id = ?",
            (broadcast_id,),
        )
        rows = {row["user_id"]: (row["status"], row["last_attempt_at"]) for row in await cursor.fetchall()}
    # Sent, blocked, failed and a transient retry back in the queue: all stamped with the write time.
    assert rows[BASE + 1] == ("sent", T0)
    assert rows[BASE + 2] == ("blocked", T0)
    assert rows[BASE + 3] == ("failed", T0)
    assert rows[BASE + 4] == ("pending", T0)
