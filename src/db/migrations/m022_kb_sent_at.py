"""When the bot last sent a user their main reply keyboard.

The keyboard's Mini App buttons embed a signed login link valid for 7 days
(``src/functions/webapp_link.py``). ``users.kb_sent_at`` (unix seconds, NULL =
never sent with signed links) lets the bot re-send the keyboard once the link
is about to expire, see ``src/functions/main_menu.py``.
"""

from src.db.migrate import add_column_if_missing

ID = "m022_kb_sent_at"


async def apply(conn) -> None:
    await add_column_if_missing(conn, "users", "kb_sent_at", "INTEGER")
