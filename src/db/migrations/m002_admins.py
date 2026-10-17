"""Admin roles table.

``ADMIN_IDS`` (env) stops being the source of truth: it only bootstraps the
first ``owner`` row (see ``webapp.core.auth.resolve_admin_role``). Every later
admin is added from the panel by an owner and recorded here.
"""

ID = "m002_admins"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            user_id  INTEGER PRIMARY KEY,
            role     TEXT NOT NULL,
            added_by INTEGER,
            added_at INTEGER NOT NULL,
            disabled INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await conn.execute("CREATE INDEX IF NOT EXISTS idx_admins_role ON admins(role, disabled)")
