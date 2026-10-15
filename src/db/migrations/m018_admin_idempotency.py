"""``admin_idempotency``: replay records for retried admin mutations.

An admin money mutation (``POST /api/admin/users/{id}/balance``) may be sent
twice — a flaky Telegram WebView retries, a double tap, a lost response. The
client sends ``X-Idempotency-Key`` (a fresh UUID per submission); the router
claims ``(actor_id, action, idem_key)`` with an ``INSERT ... ON CONFLICT DO
NOTHING`` as the FIRST write of the mutation's transaction, so:

* the PRIMARY KEY makes two concurrent requests with the same key serialize on
  SQLite's write lock — the second one waits, then sees the first one's
  committed row and replays its stored response instead of writing a second
  ledger row;
* a mutation that fails rolls back its claim with everything else, so a retry
  of a refused request runs again (nothing was moved the first time).

``body_hash`` binds the key to the validated request fields: the same key with
a different body is refused, never replayed. ``response_json`` is what the
original call returned. Rows older than 24 h are deleted by the router in the
claiming transaction (``created_at`` is indexed for that); after that window a
key counts as new.

The same table records single-use CSV download links (action
``users.export_download``, key = SHA-256 of the link token), see
``webapp/routers/admin_users.py``.
"""

ID = "m018_admin_idempotency"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_idempotency (
            actor_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            idem_key TEXT NOT NULL,
            target_id TEXT,
            body_hash TEXT NOT NULL,
            response_json TEXT,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (actor_id, action, idem_key)
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_idempotency_created_at "
        "ON admin_idempotency(created_at)"
    )
