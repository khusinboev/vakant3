"""Admin statistics card: aggregate queries and the two renderings.

``collect_stats`` runs a fixed number of aggregate queries (no per-row or
per-day loops). ``render_rich_html`` builds the Bot API 10.1 rich message
(``InputRichMessage.html``: ``<h1>``..``<h3>`` headings, ``<table>`` with
``<th>``/``<td>`` cells, ``<p>``); ``render_plain_html`` is the classic HTML
card the handler falls back to when Telegram rejects the rich one.

Every string goes through ``html.escape``; nothing user-typed is shown (labels
come from the dictionaries, the rest are numbers we computed).
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime

from src.core.timeutil import now_tz, today_start_ts
from src.i18n import t

DAY = 86_400
LEDGER_KINDS = ("topup", "topup_bonus", "pro_activation", "referral_reward")
PAY_METHODS = ("page", "card", "phone", "app")
PERIODS = ("today", "d7", "d30", "all")


@dataclass
class Stats:
    users: dict[str, int] = field(default_factory=dict)
    pro: dict[str, int] = field(default_factory=dict)
    #: period -> (paid count, paid sum)
    paid: dict[str, tuple[int, int]] = field(default_factory=dict)
    pending: int = 0
    cancelled: int = 0
    #: method ("unknown" for NULL) -> (paid count, paid sum), all time
    by_method: dict[str, tuple[int, int]] = field(default_factory=dict)
    #: ledger kind -> (rows, signed sum) over 30 days
    wallet: dict[str, tuple[int, int]] = field(default_factory=dict)
    referrals_30d: int = 0
    broadcasts: list[dict] = field(default_factory=list)


async def collect_stats(conn, now: datetime | None = None) -> Stats:
    moment = now or now_tz()
    now_ts = int(moment.timestamp())
    today = today_start_ts(moment)
    d7, d30 = now_ts - 7 * DAY, now_ts - 30 * DAY
    stats = Stats()

    cur = await conn.execute(
        """
        SELECT COUNT(*),
               COALESCE(SUM(date >= ?), 0), COALESCE(SUM(date >= ?), 0), COALESCE(SUM(date >= ?), 0),
               COALESCE(SUM(last_seen_at >= ?), 0),
               COALESCE(SUM(blocked = 1), 0), COALESCE(SUM(banned = 1), 0),
               COALESCE(SUM(user_pro = 1), 0),
               COALESCE(SUM(ref_by IS NOT NULL AND date >= ?), 0)
        FROM users
        """,
        (today, d7, d30, d7, d30),
    )
    r = await cur.fetchone()
    stats.users = {
        "total": r[0], "today": r[1], "d7": r[2], "d30": r[3],
        "active7": r[4], "blocked": r[5], "banned": r[6],
    }
    stats.pro = {"count": r[7]}
    stats.referrals_30d = r[8]

    cur = await conn.execute(
        """
        SELECT COALESCE(SUM(created_at >= ?), 0), COALESCE(SUM(created_at >= ?), 0)
        FROM wallet_transactions WHERE kind = 'pro_activation'
        """,
        (d7, d30),
    )
    r = await cur.fetchone()
    stats.pro["act7"], stats.pro["act30"] = r[0], r[1]

    cur = await conn.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN state = 'paid' AND perform_time >= ? THEN 1 END), 0),
          COALESCE(SUM(CASE WHEN state = 'paid' AND perform_time >= ? THEN amount_soum END), 0),
          COALESCE(SUM(CASE WHEN state = 'paid' AND perform_time >= ? THEN 1 END), 0),
          COALESCE(SUM(CASE WHEN state = 'paid' AND perform_time >= ? THEN amount_soum END), 0),
          COALESCE(SUM(CASE WHEN state = 'paid' AND perform_time >= ? THEN 1 END), 0),
          COALESCE(SUM(CASE WHEN state = 'paid' AND perform_time >= ? THEN amount_soum END), 0),
          COALESCE(SUM(CASE WHEN state = 'paid' THEN 1 END), 0),
          COALESCE(SUM(CASE WHEN state = 'paid' THEN amount_soum END), 0),
          COALESCE(SUM(CASE WHEN state IN ('created', 'pending') THEN 1 END), 0),
          COALESCE(SUM(CASE WHEN state = 'cancelled' THEN 1 END), 0)
        FROM payment_orders
        """,
        # perform_time is in milliseconds (Click), every other column in seconds
        (today * 1000, today * 1000, d7 * 1000, d7 * 1000, d30 * 1000, d30 * 1000),
    )
    r = await cur.fetchone()
    stats.paid = {"today": (r[0], r[1]), "d7": (r[2], r[3]), "d30": (r[4], r[5]), "all": (r[6], r[7])}
    stats.pending, stats.cancelled = r[8], r[9]

    cur = await conn.execute(
        """
        SELECT COALESCE(click_method, 'unknown'), COUNT(*), COALESCE(SUM(amount_soum), 0)
        FROM payment_orders WHERE state = 'paid' GROUP BY 1
        """
    )
    stats.by_method = {row[0]: (row[1], row[2]) for row in await cur.fetchall()}

    cur = await conn.execute(
        """
        SELECT kind, COUNT(*), COALESCE(SUM(amount), 0)
        FROM wallet_transactions
        WHERE created_at >= ? AND kind IN ('topup', 'topup_bonus', 'pro_activation', 'referral_reward')
        GROUP BY kind
        """,
        (d30,),
    )
    stats.wallet = {row[0]: (row[1], row[2]) for row in await cur.fetchall()}

    cur = await conn.execute("SELECT id, status, sent, failed FROM broadcasts ORDER BY id DESC LIMIT 3")
    stats.broadcasts = [
        {"id": row[0], "status": row[1], "sent": row[2] or 0, "failed": row[3] or 0}
        for row in await cur.fetchall()
    ]
    return stats


def fmt_int(value: int) -> str:
    """``1234567`` -> ``1 234 567`` (plain spaces)."""
    return f"{int(value):,}".replace(",", " ")


def fmt_money(lang: str, amount: int) -> str:
    return t(lang, "stats2.money", amount=fmt_int(amount))


def _esc(value) -> str:
    return html.escape(str(value), quote=False)


def _sections(lang: str, s: Stats) -> list[tuple[str, list[tuple[str, str]]]]:
    """(title, [(label, value)]) for the two-column sections both renderings share."""
    u, p = s.users, s.pro
    users = [
        (t(lang, "stats2.users.total"), fmt_int(u["total"])),
        (t(lang, "stats2.users.today"), fmt_int(u["today"])),
        (t(lang, "stats2.users.d7"), fmt_int(u["d7"])),
        (t(lang, "stats2.users.d30"), fmt_int(u["d30"])),
        (t(lang, "stats2.users.active7"), fmt_int(u["active7"])),
        (t(lang, "stats2.users.blocked"), fmt_int(u["blocked"])),
        (t(lang, "stats2.users.banned"), fmt_int(u["banned"])),
    ]
    pro = [
        (t(lang, "stats2.pro.count"), fmt_int(p["count"])),
        (t(lang, "stats2.pro.act7"), fmt_int(p["act7"])),
        (t(lang, "stats2.pro.act30"), fmt_int(p["act30"])),
    ]
    wallet = [
        (t(lang, f"stats2.wallet.{kind}"), fmt_money(lang, s.wallet.get(kind, (0, 0))[1]))
        for kind in LEDGER_KINDS
    ]
    referrals = [(t(lang, "stats2.ref.new30"), fmt_int(s.referrals_30d))]
    return [
        (t(lang, "stats2.sec.users"), users),
        (t(lang, "stats2.sec.pro"), pro),
        (t(lang, "stats2.sec.wallet"), wallet),
        (t(lang, "stats2.sec.referrals"), referrals),
    ]


def _payment_rows(lang: str, s: Stats) -> list[tuple[str, str, str]]:
    return [
        (t(lang, f"stats2.period.{period}"), fmt_int(s.paid[period][0]), fmt_money(lang, s.paid[period][1]))
        for period in PERIODS
    ]


def _method_rows(lang: str, s: Stats) -> list[tuple[str, str, str]]:
    known = (*PAY_METHODS, "unknown")
    order = [m for m in known if m in s.by_method] + sorted(m for m in s.by_method if m not in known)
    rows = []
    for method in order:
        label = t(lang, f"stats2.method.{method}") if method in known else method
        count, total = s.by_method[method]
        rows.append((label, fmt_int(count), fmt_money(lang, total)))
    return rows


def _broadcast_lines(lang: str, s: Stats) -> list[str]:
    if not s.broadcasts:
        return [t(lang, "stats2.bc.none")]
    return [
        t(
            lang,
            "stats2.bc.row",
            id=b["id"],
            status=t(lang, f"bc.status.{b['status']}"),
            sent=fmt_int(b["sent"]),
            failed=fmt_int(b["failed"]),
        )
        for b in s.broadcasts
    ]


def _table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    head = "".join(f"<th>{_esc(c)}</th>" for c in header)
    body = "".join("<tr>" + "".join(f"<td>{_esc(c)}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def render_rich_html(lang: str, s: Stats) -> str:
    """The card as ``InputRichMessage.html`` (headings, tables, paragraphs)."""
    metric, value = t(lang, "stats2.col.metric"), t(lang, "stats2.col.value")
    sections = _sections(lang, s)
    parts = [f"<h1>{_esc(t(lang, 'stats2.title', plain_emoji=True))}</h1>"]
    for title, rows in sections[:2]:
        parts += [f"<h2>{_esc(title)}</h2>", _table((metric, value), rows)]
    pay_head = (t(lang, "stats2.pay.period"), t(lang, "stats2.pay.paid"), t(lang, "stats2.pay.sum"))
    parts += [
        f"<h2>{_esc(t(lang, 'stats2.sec.payments'))}</h2>",
        _table(pay_head, _payment_rows(lang, s)),
        _table(
            (metric, value),
            [
                (t(lang, "stats2.pay.pending"), fmt_int(s.pending)),
                (t(lang, "stats2.pay.cancelled"), fmt_int(s.cancelled)),
            ],
        ),
    ]
    method_rows = _method_rows(lang, s)
    if method_rows:
        parts += [f"<h3>{_esc(t(lang, 'stats2.pay.by_method'))}</h3>", _table(pay_head, method_rows)]
    for title, rows in sections[2:]:
        parts += [f"<h2>{_esc(title)}</h2>", _table((metric, value), rows)]
    parts.append(f"<h2>{_esc(t(lang, 'stats2.sec.broadcasts'))}</h2>")
    parts += [f"<p>{_esc(line)}</p>" for line in _broadcast_lines(lang, s)]
    return "".join(parts)


def render_plain_html(lang: str, s: Stats) -> str:
    """Fallback: classic Telegram HTML (bold headings, one line per value)."""
    lines = [f"<b>{t(lang, 'stats2.title')}</b>"]

    def block(title: str, rows: list[tuple[str, str]]) -> None:
        lines.extend(["", f"<b>{_esc(title)}</b>"])
        lines.extend(f"{_esc(label)}: {_esc(val)}" for label, val in rows)

    sections = _sections(lang, s)
    for title, rows in sections[:2]:
        block(title, rows)
    block(
        t(lang, "stats2.sec.payments"),
        [(period, f"{count} / {total}") for period, count, total in _payment_rows(lang, s)]
        + [
            (t(lang, "stats2.pay.pending"), fmt_int(s.pending)),
            (t(lang, "stats2.pay.cancelled"), fmt_int(s.cancelled)),
        ]
        + [(label, f"{count} / {total}") for label, count, total in _method_rows(lang, s)],
    )
    for title, rows in sections[2:]:
        block(title, rows)
    lines.extend(["", f"<b>{_esc(t(lang, 'stats2.sec.broadcasts'))}</b>"])
    lines.extend(_esc(line) for line in _broadcast_lines(lang, s))
    return "\n".join(lines)
