"""``vacancies.category_id``: the canonical Mini App category of every store row.

The ids are the ``/api/filters/specs`` taxonomy (osonish field ids, see
``src/ingest/categories.py``); ``NULL`` = unknown. The ingest adapters fill it
on every upsert from now on. Existing rows are backfilled here from what the
store already holds (``raw_json`` + ``title`` + the free-text ``category``
label), in id-ordered chunks of ``CHUNK`` rows with one ``executemany`` each:
pure CPU work on ~20k rows, well under a second, inside the migration's own
``BEGIN IMMEDIATE``. Only rows whose ``category_id`` is still NULL are touched,
so a re-run (or a DB where the adapters already wrote some ids) changes nothing
it should not.

The partial index serves ``repo.search(category=...)``: it covers exactly the
rows the Mini App lists (``status = 'open' AND dup_of IS NULL``), newest first.
"""
from __future__ import annotations

import json

from src.db.migrate import add_column_if_missing
from src.ingest.categories import categorize

ID = "m026_vacancy_category"
CHUNK = 1_000


async def apply(conn) -> None:
    cursor = await conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'vacancies'")
    if await cursor.fetchone() is None:
        return
    await add_column_if_missing(conn, "vacancies", "category_id", "INTEGER")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_vacancies_open_category "
        "ON vacancies(category_id, published_at) WHERE status = 'open' AND dup_of IS NULL"
    )
    await backfill(conn)


async def backfill(conn) -> int:
    """Classify rows with ``category_id IS NULL``; returns how many got an id."""
    last_id = 0
    filled = 0
    while True:
        cursor = await conn.execute(
            "SELECT id, source, title, category, raw_json FROM vacancies "
            "WHERE id > ? AND category_id IS NULL ORDER BY id LIMIT ?",
            (last_id, CHUNK),
        )
        rows = await cursor.fetchall()
        if not rows:
            return filled
        updates = []
        for row in rows:
            row_id, source, title, label, raw_json = row[0], row[1], row[2], row[3], row[4]
            try:
                raw = json.loads(raw_json or "{}")
            except ValueError:
                raw = {}
            category = categorize(str(source or ""), raw if isinstance(raw, dict) else {}, title or "", label or "")
            if category is not None:
                updates.append((category, row_id))
        if updates:
            await conn.executemany("UPDATE vacancies SET category_id = ? WHERE id = ?", updates)
            filled += len(updates)
        last_id = int(rows[-1][0])
