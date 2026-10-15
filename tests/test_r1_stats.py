"""Bot admin statistics card: aggregate numbers, rich message, plain fallback.

Synthetic data only (user ids from 900000000000). Handlers run through the
real Dispatcher harness of ``tests/test_b1_bot_admin.py``; nothing leaves the
process.
"""
from __future__ import annotations

from datetime import datetime

import aiosqlite
import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SendMessage, SendRichMessage

from src.core.timeutil import TZ
from src.db.migrate import run_migrations
from src.functions.admin_stats import (
    _table,
    collect_stats,
    fmt_int,
    render_plain_html,
    render_rich_html,
)
from src.i18n import LANGS, t
from tests import test_b1_bot_admin as b1

harness = b1.harness

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=TZ)
NOW_TS = int(NOW.timestamp())
DAY = 86_400
HOUR = 3_600


async def _seed(conn) -> None:
    """9 users + payments, ledger rows and broadcasts with known totals."""
    rows = [
        # id, date, last_seen, blocked, banned, pro, ref_by
        (900000000301, NOW_TS - HOUR, NOW_TS - HOUR, 0, 0, 1, 900000000302),   # new today, active, pro, referred
        (900000000302, NOW_TS - 3 * DAY, NOW_TS - 2 * DAY, 0, 0, 0, None),      # new 7d
        (900000000303, NOW_TS - 10 * DAY, NOW_TS - 9 * DAY, 1, 0, 0, 900000000302),  # 30d, blocked, referred
        (900000000304, NOW_TS - 40 * DAY, NOW_TS - 40 * DAY, 0, 1, 1, 900000000302),  # old, banned, pro, referred long ago
        (900000000305, NOW_TS - 50 * DAY, None, 0, 0, 0, None),
    ]
    for uid, date, seen, blocked, banned, pro, ref in rows:
        await conn.execute(
            "INSERT INTO users (user_id, date, lang, blocked, banned, user_pro, last_seen_at, ref_by) "
            "VALUES (?, ?, 'uz', ?, ?, ?, ?, ?)",
            (uid, date, blocked, banned, pro, seen, ref),
        )
    # payments: (state, amount, perform_time ms, method)
    orders = [
        ("paid", 10_000, (NOW_TS - HOUR) * 1000, "card"),
        ("paid", 25_000, (NOW_TS - 3 * DAY) * 1000, "page"),
        ("paid", 1_000_000, (NOW_TS - 20 * DAY) * 1000, "card"),
        ("paid", 5_000, (NOW_TS - 60 * DAY) * 1000, None),
        ("pending", 7_000, 0, None),
        ("created", 8_000, 0, None),
        ("cancelled", 9_000, 0, None),
    ]
    for i, (state, amount, performed, method) in enumerate(orders):
        await conn.execute(
            "INSERT INTO payment_orders (id, user_id, amount_soum, state, perform_time, click_method, "
            "created_at, updated_at) VALUES (?, 900000000301, ?, ?, ?, ?, 1, 1)",
            (f"ord{i}", amount, state, performed, method),
        )
    ledger = [
        ("topup", 10_000, NOW_TS - HOUR),
        ("topup", 25_000, NOW_TS - 20 * DAY),
        ("topup", 99_999, NOW_TS - 45 * DAY),  # outside 30 d
        ("topup_bonus", 500, NOW_TS - HOUR),
        ("pro_activation", -10_000, NOW_TS - 2 * DAY),
        ("pro_activation", -10_000, NOW_TS - 15 * DAY),
        ("pro_activation", -10_000, NOW_TS - 90 * DAY),
        ("referral_reward", 3_000, NOW_TS - DAY),
    ]
    for i, (kind, amount, created) in enumerate(ledger):
        await conn.execute(
            "INSERT INTO wallet_transactions (user_id, kind, amount, balance_after, created_at, reference) "
            "VALUES (900000000301, ?, ?, 0, ?, ?)",
            (kind, amount, created, f"ref{i}"),
        )
    for i, (status, sent, failed) in enumerate(
        [("done", 90, 10), ("running", 5, 0), ("failed", 0, 3), ("done", 1, 1)]
    ):
        await conn.execute(
            "INSERT INTO broadcasts (actor_id, status, kind, total, sent, failed, created_at) "
            "VALUES (?, ?, 'text', ?, ?, ?, ?)",
            (b1.OWNER, status, sent + failed, sent, failed, NOW_TS - i),
        )
    await conn.commit()


@pytest.fixture
async def seeded(tmp_path):
    path = tmp_path / "stats.sqlite3"
    async with aiosqlite.connect(path) as conn:
        await conn.execute(b1.USERS_DDL)
        await conn.commit()
        await run_migrations(conn)
        await _seed(conn)
    async with aiosqlite.connect(path) as conn:
        yield conn


async def test_collect_stats_numbers(seeded):
    s = await collect_stats(seeded, NOW)
    assert s.users == {"total": 5, "today": 1, "d7": 2, "d30": 3, "active7": 2, "blocked": 1, "banned": 1}
    assert s.pro == {"count": 2, "act7": 1, "act30": 2}
    assert s.referrals_30d == 2  # 301 and 303; 304 was referred 40 days ago
    assert s.paid == {
        "today": (1, 10_000),
        "d7": (2, 35_000),
        "d30": (3, 1_035_000),
        "all": (4, 1_040_000),
    }
    assert (s.pending, s.cancelled) == (2, 1)  # created + pending
    assert s.by_method == {"card": (2, 1_010_000), "page": (1, 25_000), "unknown": (1, 5_000)}
    assert s.wallet == {
        "topup": (2, 35_000),
        "topup_bonus": (1, 500),
        "pro_activation": (2, -20_000),
        "referral_reward": (1, 3_000),
    }
    assert [(b["status"], b["sent"], b["failed"]) for b in s.broadcasts] == [
        ("done", 1, 1), ("failed", 0, 3), ("running", 5, 0),
    ]  # the newest three only (by id)


async def test_collect_stats_is_a_fixed_number_of_queries(seeded):
    statements: list[str] = []
    await seeded._execute(seeded._conn.set_trace_callback, statements.append)
    await collect_stats(seeded, NOW)
    small = len(statements)
    for i in range(200):  # many more rows must not add queries
        await seeded.execute(
            "INSERT INTO users (user_id, date, lang) VALUES (?, ?, 'uz')", (900000100000 + i, NOW_TS)
        )
    statements.clear()
    await collect_stats(seeded, NOW)
    assert len(statements) == small <= 8


@pytest.mark.parametrize("lang", LANGS)
async def test_both_renderings_carry_the_amounts_with_separators(seeded, lang):
    s = await collect_stats(seeded, NOW)
    money = t(lang, "stats2.money", amount="1 040 000")
    rich, plain = render_rich_html(lang, s), render_plain_html(lang, s)
    assert f"<td>{money}</td>" in rich
    assert money in plain
    for rendered in (rich, plain):
        assert "{" not in rendered and "stats2." not in rendered  # no unfilled placeholder / raw key
    for tag in ("<h1>", "<h2>", "<table>", "<th>", "<td>", "<p>"):
        assert tag in rich
    assert "<table" not in plain and "<h" not in plain
    assert t(lang, "stats2.method.card") in rich and t(lang, "stats2.sec.broadcasts") in plain


def test_thousands_separator_and_escaping():
    assert fmt_int(0) == "0" and fmt_int(1234) == "1 234" and fmt_int(1234567890) == "1 234 567 890"
    html = _table(("<b>x</b>",), [("a & b", "<script>")])
    assert "<b>" not in html and "<script>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "a &amp; b" in html and "&lt;script&gt;" in html


async def test_stats_handler_sends_one_rich_message(harness):
    await harness.send(b1.OWNER, t("uz", "btn.admin.stats"))
    (card,) = harness.session.of(SendRichMessage)
    assert harness.session.of(SendMessage) == []
    assert card.chat_id == b1.OWNER
    html = card.rich_message.html
    assert card.rich_message.markdown is None and card.rich_message.blocks is None
    assert html.startswith("<h1>") and "<table>" in html
    assert f"<td>{fmt_int(len(b1.USERS))}</td>" in html  # total users from the harness DB


async def test_rejected_rich_message_falls_back_to_the_plain_card(harness):
    original = harness.session.make_request

    async def reject_rich(bot, method, timeout=None):
        if isinstance(method, SendRichMessage):
            raise TelegramBadRequest(method=method, message="Bad Request: can't parse rich message")
        return await original(bot, method, timeout)

    harness.session.make_request = reject_rich
    await harness.send(b1.VIEWER, t("uz", "btn.admin.stats"))
    (plain,) = harness.session.of(SendMessage)
    assert plain.text.startswith(f"<b>{t('uz', 'stats2.title')}")
    assert t("uz", "stats2.sec.users") in plain.text and "<table" not in plain.text
    assert len(plain.text) < 4096


def test_new_keys_exist_in_every_language_with_the_same_placeholders():
    import re

    from src.i18n.en import STRINGS as EN
    from src.i18n.ru import STRINGS as RU
    from src.i18n.uz import STRINGS as UZ

    keys = [k for k in UZ if k.startswith("stats2.")] + ["menu.admin", "btn.admin.exit", "menu.refreshed"]
    assert len(keys) > 40 and "start.app_prompt" not in UZ
    for key in keys:
        names = {tuple(sorted(re.findall(r"\{(\w+)\}", d[key]))) for d in (UZ, RU, EN)}
        assert key in RU and key in EN and len(names) == 1, key


async def test_m022_adds_kb_sent_at_once(tmp_path):
    from src.db.migrations import m022_kb_sent_at

    async with aiosqlite.connect(tmp_path / "m022.sqlite3") as conn:
        await conn.execute(b1.USERS_DDL)
        await m022_kb_sent_at.apply(conn)
        await m022_kb_sent_at.apply(conn)  # re-applied: no-op
        columns = [row[1] for row in await (await conn.execute("PRAGMA table_info(users)")).fetchall()]
    assert columns.count("kb_sent_at") == 1
