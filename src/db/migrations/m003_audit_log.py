"""Append-only audit trail for every admin mutation.

Rows are written by ``webapp.core.audit.log_admin_action`` inside the same
transaction as the mutation itself, so a failed mutation leaves no audit row.
"""

ID = "m003_audit_log"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id     INTEGER NOT NULL,
            action       TEXT NOT NULL,
            target_type  TEXT,
            target_id    TEXT,
            payload_json TEXT,
            ip           TEXT,
            created_at   INTEGER NOT NULL
        )
        """
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created_at ON admin_audit_log(created_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_admin_audit_log_actor_created ON admin_audit_log(actor_id, created_at)"
    )
