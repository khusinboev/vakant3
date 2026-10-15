"""Make ``idx_users_ref_by`` the partial index m014 intended.

m014 creates ``idx_users_ref_by ... WHERE ref_by IS NOT NULL`` with
``IF NOT EXISTS``, but the API's ``init_db`` runs before the migrations and
used to create a *full* index under the same name, so on every database the
API had started against, m014 was a silent no-op and the full index stayed.

Every query on the column (``ref_by = ?``, ``WHERE ref_by IS NOT NULL ...
GROUP BY ref_by``) implies ``ref_by IS NOT NULL``, so the partial index serves
all of them while storing only the referred users. ``init_db`` now creates the
partial definition too; this migration replaces a full index left behind.
"""

ID = "m016_ref_by_partial_index"

INDEX_NAME = "idx_users_ref_by"
PARTIAL_INDEX_SQL = (
    f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON users(ref_by) WHERE ref_by IS NOT NULL"
)


async def is_partial(conn, index_name: str = INDEX_NAME) -> bool | None:
    """True/False for an existing index, None when there is no such index on ``users``."""
    cursor = await conn.execute("PRAGMA index_list(users)")
    for row in await cursor.fetchall():
        # (seq, name, unique, origin, partial)
        if str(row[1]) == index_name:
            return bool(row[4])
    return None


async def apply(conn) -> None:
    cursor = await conn.execute("PRAGMA table_info(users)")
    columns = {str(row[1]) for row in await cursor.fetchall()}
    if "ref_by" not in columns:
        return  # same guard as m014: nothing to index yet
    if await is_partial(conn) is False:
        await conn.execute(f"DROP INDEX {INDEX_NAME}")
    await conn.execute(PARTIAL_INDEX_SQL)
