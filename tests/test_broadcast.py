"""Broadcast queue tests: targeting, the worker, validation and uploads.

No Telegram is involved: the worker takes the bot object as an argument, so a
small fake records the calls and raises the aiogram exceptions we care about.
"""
import asyncio
import time
from contextlib import asynccontextmanager

import aiosqlite
import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from src.db.migrate import run_migrations
from src.functions import broadcast_worker as bw

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

NOW = int(time.time())

# user_id, lang, region, pro, blocked, date
SAMPLE_USERS = [
    (1, "uz", "1703", 1, 0, NOW),
    (2, "ru", "1703", 0, 0, NOW),
    (3, "en", "1726", 0, 1, NOW),            # blocked the bot
    (4, "uz", "1726", 1, 0, NOW - 90 * 86400),  # inactive
    (5, "uz", "1703", 0, 0, NOW),
]


@pytest.fixture
async def db_path(tmp_path):
    path = tmp_path / "broadcast.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await conn.execute(USERS_DDL)
        await conn.executemany(
            "INSERT INTO users (user_id, lang, region, user_pro, blocked, date) VALUES (?, ?, ?, ?, ?, ?)",
            [(u[0], u[1], u[2], u[3], u[4], u[5]) for u in SAMPLE_USERS],
        )
        await conn.commit()
        await run_migrations(conn)
    return path


@pytest.fixture
def connect(db_path):
    @asynccontextmanager
    async def _connect(path=None):
        conn = await aiosqlite.connect(path or db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    return _connect


class FakeBot:
    """Records calls; ``behaviour[user_id]`` is a list of exceptions to raise."""

    def __init__(self, behaviour=None, on_send=None):
        self.calls: list[tuple[str, int]] = []
        self.behaviour = {uid: list(items) for uid, items in (behaviour or {}).items()}
        self.on_send = on_send
        self.file_id_counter = 0

    async def _record(self, method: str, user_id: int):
        self.calls.append((method, user_id))
        queue = self.behaviour.get(user_id)
        if queue:
            raise queue.pop(0)
        if self.on_send is not None:
            await self.on_send(user_id)
        return FakeMessage(len(self.calls))

    async def forward_message(self, user_id, chat_id, message_id):
        return await self._record("forward", user_id)

    async def copy_message(self, user_id, chat_id, message_id):
        return await self._record("copy", user_id)

    async def send_message(self, user_id, text, reply_markup=None):
        return await self._record("text", user_id)

    async def send_photo(self, user_id, media, caption=None, reply_markup=None):
        return await self._record("photo", user_id)


class FakePhoto:
    def __init__(self, file_id):
        self.file_id = file_id


class FakeMessage:
    def __init__(self, message_id):
        self.message_id = message_id
        self.photo = [FakePhoto("file-123")]


async def _new_job(connect, *, segment="all", exclude_blocked=True, kind="forward", queue=True):
    async with connect() as conn:
        broadcast_id = await bw.create_broadcast(
            conn,
            actor_id=99,
            kind=kind,
            text="salom" if kind == "text" else None,
            forward_chat_id=-100123,
            forward_message_id=5,
            target={"segment": segment, "exclude_blocked": exclude_blocked},
        )
        total = await bw.queue_broadcast(conn, broadcast_id, admin_ids=[1, 2]) if queue else 0
        await conn.commit()
    return broadcast_id, total


async def _targets(connect, broadcast_id, status=None):
    async with connect() as conn:
        sql = "SELECT user_id, status FROM broadcast_targets WHERE broadcast_id = ?"
        params = [broadcast_id]
        if status:
            sql += " AND status = ?"
            params.append(status)
        cursor = await conn.execute(sql, params)
        return {int(row[0]): row[1] for row in await cursor.fetchall()}


async def _job_row(connect, broadcast_id):
    async with connect() as conn:
        return await bw.broadcast_progress(conn, broadcast_id)


# ─── Targeting ──────────────────────────────────────────────────────────────

class TestMaterializeTargets:
    @pytest.mark.parametrize(
        "segment, expected",
        [
            ("all", {1, 2, 4, 5}),           # 3 is blocked
            ("pro", {1, 4}),
            ("free", {2, 5}),
            ("lang:uz", {1, 4, 5}),
            ("lang:ru", {2}),
            ("region:1703", {1, 2, 5}),
            ("active_days:30", {1, 2, 5}),   # 4 signed up 90 days ago
            ("test_admins", {1, 2}),
        ],
    )
    async def test_segment(self, connect, segment, expected):
        broadcast_id, total = await _new_job(connect, segment=segment)
        assert set(await _targets(connect, broadcast_id)) == expected
        assert total == len(expected)

    async def test_exclude_blocked_false_includes_blocked_users(self, connect):
        broadcast_id, total = await _new_job(connect, segment="all", exclude_blocked=False)
        assert set(await _targets(connect, broadcast_id)) == {1, 2, 3, 4, 5}
        assert total == 5

    async def test_unknown_segment_is_rejected(self, connect):
        async with connect() as conn:
            with pytest.raises(ValueError):
                await bw.materialize_targets(conn, 1, {"segment": "lang:de"})

    async def test_queue_is_idempotent(self, connect):
        broadcast_id, total = await _new_job(connect)
        async with connect() as conn:
            again = await bw.queue_broadcast(conn, broadcast_id)
            await conn.commit()
        assert again == total


# ─── Worker ─────────────────────────────────────────────────────────────────

class TestWorker:
    async def test_sends_every_pending_target_and_marks_done(self, connect):
        broadcast_id, total = await _new_job(connect)
        bot = FakeBot()

        await bw.run_broadcast(
            bot, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000), batch_size=2
        )

        assert sorted(user_id for _, user_id in bot.calls) == [1, 2, 4, 5]
        assert all(method == "forward" for method, _ in bot.calls)
        progress = await _job_row(connect, broadcast_id)
        assert progress["status"] == "done"
        assert progress["sent"] == total == 4
        assert set((await _targets(connect, broadcast_id)).values()) == {"sent"}

    async def test_copy_mode_uses_copy_message(self, connect):
        async with connect() as conn:
            broadcast_id = await bw.create_broadcast(
                conn,
                actor_id=1,
                kind="forward",
                forward_chat_id=-1,
                forward_message_id=2,
                target={"segment": "pro", "forward_mode": "copy"},
            )
            await bw.queue_broadcast(conn, broadcast_id)
            await conn.commit()
        bot = FakeBot()
        await bw.run_broadcast(bot, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000))
        assert {method for method, _ in bot.calls} == {"copy"}

    async def test_cancel_mid_run_stops_sending(self, connect):
        broadcast_id, _ = await _new_job(connect)
        sent_before_cancel = []

        async def cancel_after_two(user_id):
            sent_before_cancel.append(user_id)
            if len(sent_before_cancel) == 2:
                async with connect() as conn:
                    await conn.execute(
                        "UPDATE broadcasts SET status = 'cancelled' WHERE id = ?", (broadcast_id,)
                    )
                    await conn.commit()

        bot = FakeBot(on_send=cancel_after_two)
        await bw.run_broadcast(
            bot, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000), batch_size=2
        )

        assert len(bot.calls) == 2
        progress = await _job_row(connect, broadcast_id)
        assert progress["status"] == "cancelled"
        assert progress["sent"] == 2
        assert len(await _targets(connect, broadcast_id, "pending")) == 2

    async def test_forbidden_marks_target_and_user_blocked(self, connect):
        broadcast_id, _ = await _new_job(connect)
        bot = FakeBot(behaviour={2: [TelegramForbiddenError(method=None, message="bot was blocked")]})

        await bw.run_broadcast(bot, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000))

        targets = await _targets(connect, broadcast_id)
        assert targets[2] == "blocked"
        progress = await _job_row(connect, broadcast_id)
        assert (progress["sent"], progress["blocked"], progress["failed"]) == (3, 1, 0)
        async with connect() as conn:
            cursor = await conn.execute("SELECT blocked FROM users WHERE user_id = 2")
            assert (await cursor.fetchone())[0] == 1

    async def test_successful_send_clears_the_blocked_flag(self, connect):
        """A user who came back (blocked=1 in the DB, but reachable) is unblocked."""
        broadcast_id, _ = await _new_job(connect, segment="all", exclude_blocked=False)
        await bw.run_broadcast(
            FakeBot(), broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000)
        )
        async with connect() as conn:
            cursor = await conn.execute("SELECT blocked FROM users WHERE user_id = 3")
            assert (await cursor.fetchone())[0] == 0

    async def test_other_errors_are_recorded_as_failed(self, connect):
        broadcast_id, _ = await _new_job(connect)
        bot = FakeBot(behaviour={5: [TelegramBadRequest(method=None, message="chat not found")]})

        await bw.run_broadcast(bot, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000))

        targets = await _targets(connect, broadcast_id)
        assert targets[5] == "failed"
        progress = await _job_row(connect, broadcast_id)
        assert progress["failed"] == 1 and progress["status"] == "done"
        async with connect() as conn:
            cursor = await conn.execute(
                "SELECT error FROM broadcast_targets WHERE broadcast_id = ? AND user_id = 5",
                (broadcast_id,),
            )
            assert "chat not found" in (await cursor.fetchone())[0]

    async def test_retry_after_is_retried_once(self, connect):
        broadcast_id, _ = await _new_job(connect)
        bot = FakeBot(
            behaviour={
                2: [TelegramRetryAfter(method=None, message="flood", retry_after=0)],
                5: [
                    TelegramRetryAfter(method=None, message="flood", retry_after=0),
                    TelegramRetryAfter(method=None, message="flood", retry_after=0),
                ],
            }
        )

        await bw.run_broadcast(bot, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000))

        assert [uid for _, uid in bot.calls].count(2) == 2  # one retry, then success
        assert [uid for _, uid in bot.calls].count(5) == 2  # retried once, then given up
        targets = await _targets(connect, broadcast_id)
        assert targets[2] == "sent" and targets[5] == "failed"

    async def test_restart_resumes_pending_targets_only(self, connect):
        broadcast_id, total = await _new_job(connect)
        first = FakeBot()
        await bw.run_broadcast(
            first,
            broadcast_id,
            connect=connect,
            bucket=bw.TokenBucket(rate=10_000),
            batch_size=2,
            max_batches=1,
        )
        assert len(first.calls) == 2
        assert (await _job_row(connect, broadcast_id))["status"] == "running"

        second = FakeBot()  # the worker restarted
        await bw.run_broadcast(
            second, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000), batch_size=2
        )

        delivered = [uid for _, uid in first.calls] + [uid for _, uid in second.calls]
        assert sorted(delivered) == [1, 2, 4, 5]        # nobody was sent twice
        assert len(set(delivered)) == total
        assert (await _job_row(connect, broadcast_id))["status"] == "done"

    async def test_a_claimed_batch_is_not_handed_to_a_second_worker(self, connect):
        broadcast_id, _ = await _new_job(connect)
        async with connect() as conn:
            first = await bw._claim_batch(conn, broadcast_id, 2)
            second = await bw._claim_batch(conn, broadcast_id, 4)
        assert set(first).isdisjoint(second)
        assert len(first) == 2 and len(second) == 2

    async def test_stale_claims_are_reset_on_start(self, connect):
        broadcast_id, _ = await _new_job(connect)
        async with connect() as conn:
            await bw._claim_batch(conn, broadcast_id, 2)
            # A claim younger than STALE_CLAIM_SECONDS belongs to a worker that
            # may still be mid-batch; taking it back would double-send.
            assert await bw.reset_stale_claims(conn) == 0
            await conn.execute(
                "UPDATE broadcast_targets SET claimed_at = claimed_at - ? WHERE status = 'sending'",
                (bw.STALE_CLAIM_SECONDS + 60,),
            )
            await conn.commit()
            restored = await bw.reset_stale_claims(conn)
        assert restored == 2
        assert len(await _targets(connect, broadcast_id, "pending")) == 4

    async def test_process_once_returns_false_without_work(self, connect):
        assert await bw.process_once(FakeBot(), connect=connect) is False

    async def test_media_file_id_is_reused_after_the_first_send(self, connect, monkeypatch):
        async with connect() as conn:
            broadcast_id = await bw.create_broadcast(
                conn,
                actor_id=1,
                kind="photo",
                text="caption",
                media_path="uploads/202609/a.jpg",
                target={"segment": "pro"},
            )
            await bw.queue_broadcast(conn, broadcast_id)
            await conn.commit()
        monkeypatch.setattr(bw, "media_file_path", lambda path: "/dev/null")

        bot = FakeBot()
        await bw.run_broadcast(
            bot, broadcast_id, connect=connect, bucket=bw.TokenBucket(rate=10_000), batch_size=1
        )

        async with connect() as conn:
            cursor = await conn.execute(
                "SELECT media_file_id FROM broadcasts WHERE id = ?", (broadcast_id,)
            )
            assert (await cursor.fetchone())[0] == "file-123"

    async def test_token_bucket_limits_the_rate(self):
        bucket = bw.TokenBucket(rate=50, capacity=1)
        started = asyncio.get_running_loop().time()
        for _ in range(3):
            await bucket.acquire()
        assert asyncio.get_running_loop().time() - started >= 0.03


# ─── Validation ─────────────────────────────────────────────────────────────

class TestValidation:
    @pytest.fixture(autouse=True)
    def _router(self):
        pytest.importorskip("fastapi")
        from webapp.routers import admin_broadcasts

        self.mod = admin_broadcasts

    def test_allowed_html_passes(self):
        text = '<b>Salom</b> <a href="https://t.me/bandlikuzbot">link</a><br><i>ok</i>'
        assert self.mod.validate_html_text(text, limit=4096) == text

    @pytest.mark.parametrize(
        "text",
        [
            "<script>alert(1)</script>",
            '<a href="javascript:alert(1)">x</a>',
            "<b>unclosed",
            "<b>wrong</i>",
            '<div class="x">nope</div>',
            "<span>no spoiler class</span>",
        ],
    )
    def test_bad_html_is_rejected(self, text):
        with pytest.raises(Exception) as excinfo:
            self.mod.validate_html_text(text, limit=4096)
        assert excinfo.value.detail["code"] == "BROADCAST_INVALID"

    def test_text_limit_counts_visible_characters(self):
        self.mod.validate_html_text("<b>" + "a" * 4096 + "</b>", limit=4096)
        with pytest.raises(Exception) as excinfo:
            self.mod.validate_html_text("a" * 4097, limit=4096)
        assert excinfo.value.detail["reason"] == "too_long"

    def test_caption_limit_is_1024(self):
        with pytest.raises(Exception) as excinfo:
            self.mod.validate_html_text("a" * 1025, limit=self.mod.MAX_CAPTION_LENGTH, field="caption")
        assert excinfo.value.detail["field"] == "caption"

    def test_buttons_are_validated(self):
        good = [{"text": "Ochish", "url": "https://t.me/bandlikuzbot"}]
        assert self.mod.validate_buttons(good) == good
        for bad in (
            [{"text": "", "url": "https://a.uz"}],
            [{"text": "x", "url": "javascript:alert(1)"}],
            [{"text": "x", "url": "ftp://a.uz"}],
            [{"text": "x", "url": "https://a.uz"}] * 7,
        ):
            with pytest.raises(Exception) as excinfo:
                self.mod.validate_buttons(bad)
            assert excinfo.value.detail["code"] == "BROADCAST_INVALID"


# ─── Uploads ────────────────────────────────────────────────────────────────

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class TestUploads:
    @pytest.fixture(autouse=True)
    def _uploads(self, tmp_path, monkeypatch):
        from webapp.core import uploads

        monkeypatch.setattr(uploads, "DB_PATH", tmp_path / "database.sqlite3")
        self.uploads = uploads
        self.root = tmp_path / "uploads"

    async def _save(self, payload: bytes, **kwargs):
        async def chunks():
            for start in range(0, len(payload), 1024):
                yield payload[start : start + 1024]

        return await self.uploads.save_upload_stream(chunks(), **kwargs)

    async def test_png_is_stored_under_the_db_directory(self):
        saved = await self._save(PNG_BYTES)
        assert saved["mime"] == "image/png" and saved["kind"] == "photo"
        assert saved["size"] == len(PNG_BYTES)
        path = self.uploads.resolve_upload_path(saved["path"])
        assert path.is_file() and self.root in path.parents
        assert path.suffix == ".png"

    async def test_extension_comes_from_the_content_not_the_client(self):
        saved = await self._save(JPEG_BYTES)
        assert saved["path"].endswith(".jpg") and saved["mime"] == "image/jpeg"

    async def test_wrong_magic_bytes_are_rejected(self):
        with pytest.raises(Exception) as excinfo:
            await self._save(b"<?php system($_GET['c']); ?>" + b"\x00" * 64)
        assert excinfo.value.detail["code"] == "UPLOAD_TYPE_NOT_ALLOWED"
        assert not list(self.root.rglob("*")) or not any(p.is_file() for p in self.root.rglob("*"))

    async def test_a_zip_that_is_not_a_docx_is_rejected(self):
        with pytest.raises(Exception) as excinfo:
            await self._save(b"PK\x03\x04" + b"\x00" * 128)
        assert excinfo.value.detail["code"] == "UPLOAD_TYPE_NOT_ALLOWED"

    async def test_oversize_uploads_are_rejected_without_landing_on_disk(self):
        with pytest.raises(Exception) as excinfo:
            await self._save(PNG_BYTES + b"\x00" * 4096, max_bytes=1024)
        assert excinfo.value.detail["code"] == "UPLOAD_TOO_LARGE"
        assert not any(p.is_file() for p in self.root.rglob("*"))

    def test_path_traversal_is_refused(self):
        with pytest.raises(ValueError):
            self.uploads.resolve_upload_path("../../etc/passwd")
        with pytest.raises(ValueError):
            self.uploads.resolve_upload_path("")


# ─── Router ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client(db_path):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from webapp.core.database import get_db
    from webapp.core.limiter import limiter
    from webapp.routers import admin_broadcasts

    async def _db():
        conn = await aiosqlite.connect(db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()

    # The limiter is a module singleton with in-memory storage: without a reset
    # the 10/minute mutation budget is shared by the whole test session.
    try:
        limiter.reset()
    except Exception:  # pragma: no cover - depends on the slowapi version
        limiter._storage.reset()

    app = fastapi.FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.include_router(admin_broadcasts.router, prefix="/api")
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[admin_broadcasts.require_broadcast_admin] = lambda: {
        "user_id": 1,
        "role": "admin",
    }
    app.dependency_overrides[admin_broadcasts.confirm_create] = lambda: None
    # ``/queue`` gained its own confirmation (action ``broadcast.queue``, bound
    # to ``broadcast_id``); the token flow itself is covered in test_secfix.py.
    app.dependency_overrides[admin_broadcasts.confirm_queue] = lambda: None
    with TestClient(app) as test_client:
        yield test_client


class TestRouter:
    def test_create_queue_cancel_and_read_back(self, client):
        created = client.post(
            "/api/admin/broadcasts",
            json={"kind": "text", "text": "<b>Salom</b>", "segment": "lang:uz",
                  "buttons": [{"text": "Ochish", "url": "https://t.me/bandlikuzbot"}]},
        )
        assert created.status_code == 200, created.text
        broadcast = created.json()
        assert broadcast["status"] == "draft" and broadcast["buttons"][0]["text"] == "Ochish"

        queued = client.post(
            f"/api/admin/broadcasts/{broadcast['id']}/queue",
            json={"broadcast_id": broadcast["id"]},
        )
        assert queued.status_code == 200
        assert queued.json() == {"id": broadcast["id"], "status": "queued", "total": 3}

        listed = client.get("/api/admin/broadcasts").json()
        assert listed["total"] == 1 and listed["items"][0]["id"] == broadcast["id"]

        cancelled = client.post(f"/api/admin/broadcasts/{broadcast['id']}/cancel")
        assert cancelled.status_code == 200

        detail = client.get(f"/api/admin/broadcasts/{broadcast['id']}").json()
        assert detail["status"] == "cancelled"
        assert detail["targets"] == {"pending": 3}
        assert detail["errors"] == []

    def test_invalid_html_is_rejected_before_anything_is_stored(self, client):
        response = client.post(
            "/api/admin/broadcasts", json={"kind": "text", "text": "<script>x</script>"}
        )
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "BROADCAST_INVALID"
        assert client.get("/api/admin/broadcasts").json()["total"] == 0

    def test_queue_twice_is_a_conflict(self, client):
        broadcast_id = client.post(
            "/api/admin/broadcasts", json={"kind": "text", "text": "ok", "segment": "all"}
        ).json()["id"]
        body = {"broadcast_id": broadcast_id}
        assert client.post(
            f"/api/admin/broadcasts/{broadcast_id}/queue", json=body
        ).status_code == 200
        second = client.post(f"/api/admin/broadcasts/{broadcast_id}/queue", json=body)
        assert second.status_code == 409

    def test_unknown_broadcast_is_404(self, client):
        response = client.get("/api/admin/broadcasts/999")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "NOT_FOUND"

    def test_forward_requires_message_ids(self, client):
        response = client.post("/api/admin/broadcasts", json={"kind": "forward"})
        assert response.status_code == 400
        assert response.json()["detail"]["field"] == "forward_message_id"
