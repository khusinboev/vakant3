"""Revocation watermark for the bot's signed Mini App links (``?bt=``).

``users.bot_links_before`` is unix seconds, NULL = never revoked. A ban or an
admin "revoke sessions" (``webapp/routers/admin_users.py:_revoke_sessions``)
sets it to the current time, and ``POST /api/auth/bot-link`` refuses every
link issued at or before it (``src/functions/webapp_link.py:is_revoked``).

A timestamp instead of a counter keeps link signing a pure function: the bot
does not need to read the user's row to build a keyboard. The users table is
owned by the bot; m009 already guarantees it exists before this runs.
"""

from src.db.migrate import add_column_if_missing

ID = "m021_bot_link_revocation"


async def apply(conn) -> None:
    await add_column_if_missing(conn, "users", "bot_links_before", "INTEGER")
