"""Nightly rollup table: one row per Tashkent calendar day.

Populated by ``src.functions.daily_rollup.compute_day`` / ``daily_rollup_loop``
(00:10 Asia/Tashkent, with a startup backfill of missing days). Every column
defaults to 0 because a source table the rollup reads from may not exist yet
on a given deploy (see ``compute_day``'s guards) — a missing signal should
degrade to "no data" rather than block the row from being written.
"""

ID = "m011_daily_stats"


async def apply(conn) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_stats (
            day                 TEXT PRIMARY KEY,
            new_users           INTEGER NOT NULL DEFAULT 0,
            active_users        INTEGER NOT NULL DEFAULT 0,
            pro_users           INTEGER NOT NULL DEFAULT 0,
            pro_activations     INTEGER NOT NULL DEFAULT 0,
            revenue             INTEGER NOT NULL DEFAULT 0,
            referral_payouts    INTEGER NOT NULL DEFAULT 0,
            saves               INTEGER NOT NULL DEFAULT 0,
            resume_saves        INTEGER NOT NULL DEFAULT 0,
            resume_sends_ok     INTEGER NOT NULL DEFAULT 0,
            resume_sends_err    INTEGER NOT NULL DEFAULT 0,
            auto_posts          INTEGER NOT NULL DEFAULT 0,
            notifications       INTEGER NOT NULL DEFAULT 0,
            broadcasts_sent     INTEGER NOT NULL DEFAULT 0,
            computed_at         INTEGER NOT NULL
        )
        """
    )
