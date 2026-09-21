# ============================================================
# src/db/connection.py
# Bot tomonidagi yagona SQLite ulanish nuqtasi.
# Har bir ulanish WAL + busy_timeout + foreign_keys bilan ochiladi.
# ============================================================
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

from config import BASE_DIR

logger = logging.getLogger(__name__)

BUSY_TIMEOUT_MS = 5000
# WAL fayli cheksiz o'smasligi uchun (64 MB).
JOURNAL_SIZE_LIMIT = 64 * 1024 * 1024


async def apply_pragmas(conn: aiosqlite.Connection) -> None:
    """Ulanishga standart pragmalarni qo'llaydi (xatolar yutiladi)."""
    conn.row_factory = aiosqlite.Row
    for pragma in (
        "PRAGMA journal_mode=WAL",
        # NORMAL: WAL rejimida xavfsiz va FULL dan sezilarli tez.
        "PRAGMA synchronous=NORMAL",
        f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}",
        "PRAGMA foreign_keys=ON",
        f"PRAGMA journal_size_limit={JOURNAL_SIZE_LIMIT}",
    ):
        try:
            await conn.execute(pragma)
        except Exception as exc:  # pragma: no cover - read-only FS / locked DB
            logger.debug("pragma failed (%s): %s", pragma, exc)


@asynccontextmanager
async def connect(db_path: str | None = None) -> AsyncIterator[aiosqlite.Connection]:
    """`async with connect() as conn:` — row_factory va pragmalar tayyor holda."""
    async with aiosqlite.connect(db_path or BASE_DIR) as conn:
        await apply_pragmas(conn)
        yield conn
