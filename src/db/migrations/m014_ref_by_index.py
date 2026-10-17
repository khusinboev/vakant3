"""Index ``users(ref_by)``.

Every referral read — the user-facing ``/api/referral`` list, the referral gate's
count and the admin ``/api/admin/finance/referrals`` aggregate — filters or
groups by ``ref_by``. Without an index each of those is a full scan of
``users``, the largest table in the database.

The index is partial (``WHERE ref_by IS NOT NULL``) because the overwhelming
majority of rows have no referrer: a partial index stores only the rows any of
those queries can match, so it stays a small fraction of the table's size while
still serving ``ref_by = ?`` and ``GROUP BY ref_by``.
"""

ID = "m014_ref_by_index"


async def apply(conn) -> None:
    # ``users`` is created by the bot's StatsMiddleware and by m006; on a fresh
    # database m006 has already run by the time we get here (ids are ordered).
    cursor = await conn.execute("PRAGMA table_info(users)")
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "ref_by" not in columns:
        # Older bot schema without the column: nothing to index, and the column
        # is added with its own DDL elsewhere.
        return
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_ref_by ON users(ref_by) WHERE ref_by IS NOT NULL"
    )
