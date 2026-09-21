"""Ordered, idempotent schema migrations shared by the bot and the API.

Each module in ``src/db/migrations/`` named ``mNNN_<slug>.py`` exposes
``ID: str`` (the file stem) and ``async def apply(conn) -> None``. Applied ids
are recorded in ``schema_migrations``. Both processes call ``run_migrations``
at startup; ``BEGIN IMMEDIATE`` serializes them across processes.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
import time

import aiosqlite

from src.db import migrations as _pkg

_log = logging.getLogger(__name__)


def discover() -> list[tuple[str, object]]:
    mods = []
    for info in pkgutil.iter_modules(_pkg.__path__):
        if info.name.startswith("m") and info.name[1:4].isdigit():
            mods.append((info.name, importlib.import_module(f"{_pkg.__name__}.{info.name}")))
    return sorted(mods, key=lambda m: m[0])


#: While a migration holds ``BEGIN IMMEDIATE``, the *other* process (bot or
#: API, they share one SQLite file) is blocked out of every write. The
#: connection default is 5 s — short enough that a migration touching a large
#: table makes the other process raise "database is locked" instead of waiting.
#: Migrations are rare, brief and startup-only, so they wait a full minute.
MIGRATION_BUSY_TIMEOUT_MS = 60_000


async def _busy_timeout(conn: aiosqlite.Connection) -> int | None:
    cursor = await conn.execute("PRAGMA busy_timeout")
    row = await cursor.fetchone()
    return int(row[0]) if row is not None else None


async def run_migrations(conn: aiosqlite.Connection) -> list[str]:
    """Apply pending migrations; returns the ids applied in this call."""
    previous_timeout = await _busy_timeout(conn)
    await conn.execute(f"PRAGMA busy_timeout = {MIGRATION_BUSY_TIMEOUT_MS}")
    try:
        return await _run_migrations(conn)
    finally:
        if previous_timeout is not None:
            # The connection is handed back to normal request/tick traffic,
            # which wants the short timeout it was opened with.
            await conn.execute(f"PRAGMA busy_timeout = {previous_timeout}")


async def _run_migrations(conn: aiosqlite.Connection) -> list[str]:
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (id TEXT PRIMARY KEY, applied_at INTEGER NOT NULL)"
    )
    await conn.commit()
    applied: list[str] = []
    for mig_id, module in discover():
        cursor = await conn.execute("SELECT 1 FROM schema_migrations WHERE id = ?", (mig_id,))
        if await cursor.fetchone():
            continue
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = await conn.execute("SELECT 1 FROM schema_migrations WHERE id = ?", (mig_id,))
            if await cursor.fetchone():  # another process won the race
                await conn.execute("COMMIT")
                continue
            await module.apply(conn)  # type: ignore[attr-defined]
            await conn.execute(
                "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)", (mig_id, int(time.time()))
            )
            await conn.execute("COMMIT")
            applied.append(mig_id)
            _log.info("migration applied: %s", mig_id)
        except Exception:
            await conn.execute("ROLLBACK")
            _log.exception("migration failed: %s", mig_id)
            raise
    return applied


async def add_column_if_missing(conn: aiosqlite.Connection, table: str, column: str, decl: str) -> bool:
    """Helper for migrations: ALTER TABLE ADD COLUMN only when absent."""
    cursor = await conn.execute(f"PRAGMA table_info({table})")
    if any(row[1] == column for row in await cursor.fetchall()):
        return False
    await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    return True
