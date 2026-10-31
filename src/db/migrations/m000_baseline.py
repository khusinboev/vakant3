"""Baseline marker: everything before the migration framework lives in
StatsMiddleware.init_db (bot) and webapp/core/database.py:init_db (API)."""

ID = "m000_baseline"


async def apply(conn) -> None:  # noqa: ARG001 - nothing to do
    return None
