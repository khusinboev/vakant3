"""``broadcast_targets.claimed_at`` — when a worker took the row.

The worker claims a batch by flipping rows to ``sending``; a crash leaves them
there, so ``reset_stale_claims`` puts them back to ``pending`` at startup.
Without a timestamp that reset could only be "every row in ``sending``", which
means a second worker (or a restart while the first one is mid-batch) yanks
rows out from under a send that is still in flight and delivers them twice.

With ``claimed_at`` the reset can be restricted to claims older than the
longest a batch can plausibly take.
"""

from src.db.migrate import add_column_if_missing

ID = "m015_broadcast_claimed_at"


async def apply(conn) -> None:
    cursor = await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'broadcast_targets' LIMIT 1"
    )
    if await cursor.fetchone() is None:
        return  # m008 creates it; nothing to alter on a database without it
    await add_column_if_missing(conn, "broadcast_targets", "claimed_at", "INTEGER")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_broadcast_targets_claimed_at "
        "ON broadcast_targets(claimed_at) WHERE status = 'sending'"
    )
