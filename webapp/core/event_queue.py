"""In-process batching for ``resume_events``.

Every Mini App analytics beat (``builder_opened``, ``autosave_success``, ...)
used to be one ``INSERT`` plus one ``COMMIT`` on the request's pooled
connection. A commit is an fsync on a file both processes share, so under load
those writes serialize against real work (profile saves, wallet updates) for
rows nothing reads in real time — the admin analytics queries aggregate the
table minutes or hours later.

So events are buffered in memory and written by a single background task:
one ``executemany`` every :data:`FLUSH_INTERVAL_SECONDS`, or as soon as
:data:`FLUSH_BATCH_SIZE` events are pending. The flusher uses its own
standalone connection (``open_connection``) and never a pooled one, so it
cannot take a slot away from a request.

Trade-offs, deliberately accepted because these rows are analytics only:

* Up to :data:`FLUSH_INTERVAL_SECONDS` of events are lost if the process is
  killed; ``stop()`` drains the buffer on a clean shutdown.
* Above :data:`QUEUE_MAX` pending events new ones are dropped (counted and
  logged) rather than growing the buffer without bound.
* A failing flush drops its batch instead of re-queueing it: retrying a batch
  that fails for a permanent reason would pin the buffer at its maximum and
  drop *new* events instead of old ones.

Reading the table is unchanged — the admin analytics/metrics queries still
read ``resume_events`` directly.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from webapp.core.database import open_connection

_log = logging.getLogger(__name__)

#: Flush at least this often, even for a single pending event.
FLUSH_INTERVAL_SECONDS = 2.0
#: Flush immediately once this many events are pending.
FLUSH_BATCH_SIZE = 200
#: Hard ceiling on the in-memory buffer; beyond it events are dropped.
QUEUE_MAX = 10_000
#: How long ``stop()`` waits for the flusher to finish its current batch.
STOP_TIMEOUT_SECONDS = 5.0

INSERT_SQL = (
    "INSERT INTO resume_events (user_id, event_name, step, meta_json, created_at) "
    "VALUES (?, ?, ?, ?, ?)"
)

#: ``(user_id, event_name, step, meta_json, created_at)``
EventRow = tuple[int, str, str | None, str | None, int]


class EventQueue:
    """Buffer of pending ``resume_events`` rows plus the task that writes them.

    Not thread-safe: it is only ever touched from the API's event loop.
    """

    def __init__(
        self,
        *,
        max_size: int = QUEUE_MAX,
        batch_size: int = FLUSH_BATCH_SIZE,
        interval: float = FLUSH_INTERVAL_SECONDS,
    ) -> None:
        self._buffer: deque[EventRow] = deque()
        self._max_size = max(1, int(max_size))
        self._batch_size = max(1, int(batch_size))
        self._interval = float(interval)
        # Created in start() so it binds to the loop that will await it.
        self._wakeup: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._dropped = 0
        self._written = 0

    # -- introspection (tests, /admin/system) -------------------------------

    @property
    def pending(self) -> int:
        return len(self._buffer)

    @property
    def dropped(self) -> int:
        return self._dropped

    @property
    def written(self) -> int:
        return self._written

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    # -- producer side ------------------------------------------------------

    def enqueue(
        self,
        user_id: int,
        event_name: str,
        step: str | None = None,
        meta_json: str | None = None,
        created_at: int | None = None,
    ) -> bool:
        """Buffer one event. Returns False when it was dropped (queue full).

        Synchronous and non-blocking on purpose: a request must never wait on
        analytics.
        """
        if len(self._buffer) >= self._max_size:
            self._dropped += 1
            # One line per 1000 drops: a full queue means every request drops.
            if self._dropped % 1000 == 1:
                _log.warning(
                    "resume event queue full (max=%s), dropped %s event(s) so far",
                    self._max_size,
                    self._dropped,
                )
            return False

        self._buffer.append(
            (
                int(user_id),
                str(event_name),
                step,
                meta_json,
                int(created_at if created_at is not None else time.time()),
            )
        )
        if self._wakeup is not None and len(self._buffer) >= self._batch_size:
            self._wakeup.set()
        return True

    # -- consumer side ------------------------------------------------------

    async def flush(self, conn=None) -> int:
        """Write everything buffered right now; returns the rows written.

        With no ``conn`` a standalone connection is opened for this call —
        that is the shutdown/test path. The flusher passes its own long-lived
        connection.
        """
        if not self._buffer:
            return 0

        rows: list[EventRow] = []
        while self._buffer:
            rows.append(self._buffer.popleft())

        owned = conn is None
        if owned:
            conn = await open_connection()
        try:
            await conn.executemany(INSERT_SQL, rows)
            await conn.commit()
        except Exception as exc:
            # Dropped, not re-queued — see the module docstring.
            _log.error("resume event flush failed, dropping %s event(s): %s", len(rows), exc)
            self._dropped += len(rows)
            try:
                await conn.rollback()
            except Exception:  # pragma: no cover - connection already broken
                pass
            return 0
        finally:
            if owned:
                try:
                    await conn.close()
                except Exception:  # pragma: no cover
                    pass

        self._written += len(rows)
        return len(rows)

    async def _run(self) -> None:
        """Flush loop: wake on a full batch or every ``interval`` seconds."""
        conn = None
        try:
            while True:
                assert self._wakeup is not None
                try:
                    await asyncio.wait_for(self._wakeup.wait(), timeout=self._interval)
                except (asyncio.TimeoutError, TimeoutError):
                    pass
                self._wakeup.clear()

                if self._buffer:
                    try:
                        if conn is None:
                            conn = await open_connection()
                        await self.flush(conn)
                    except Exception as exc:
                        _log.error("resume event flusher error: %s", exc)
                        if conn is not None:
                            try:
                                await conn.close()
                            except Exception:  # pragma: no cover
                                pass
                            conn = None

                if self._stopping and not self._buffer:
                    return
        finally:
            if conn is not None:
                try:
                    await conn.close()
                except Exception:  # pragma: no cover
                    pass

    async def start(self) -> None:
        """Start the flusher task (no-op when it is already running)."""
        if self.running:
            return
        self._stopping = False
        self._wakeup = asyncio.Event()
        self._task = asyncio.create_task(self._run(), name="resume_event_flusher")

    async def stop(self) -> None:
        """Ask the flusher to drain and exit, then flush whatever is left."""
        self._stopping = True
        if self._wakeup is not None:
            self._wakeup.set()

        task, self._task = self._task, None
        if task is not None and not task.done():
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=STOP_TIMEOUT_SECONDS)
            except (asyncio.TimeoutError, TimeoutError):
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            except Exception as exc:  # pragma: no cover - defensive
                _log.error("resume event flusher stopped with an error: %s", exc)

        self._wakeup = None
        # Anything enqueued while the task was winding down.
        try:
            await self.flush()
        except Exception as exc:  # pragma: no cover - shutdown must not raise
            _log.error("final resume event flush failed: %s", exc)


#: Process-wide instance; the API lifespan starts and stops it.
_queue = EventQueue()


def get_event_queue() -> EventQueue:
    return _queue


def enqueue_event(
    user_id: int,
    event_name: str,
    step: str | None = None,
    meta_json: str | None = None,
) -> bool:
    """Buffer one ``resume_events`` row on the process-wide queue."""
    return _queue.enqueue(user_id, event_name, step, meta_json)
