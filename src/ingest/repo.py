"""All SQL for the vacancy store (tables from ``m023_vacancy_store``).

Writes run in short explicit transactions (``BEGIN IMMEDIATE`` ... ``COMMIT``)
that never span network I/O; the runner calls them between HTTP requests.
Read helpers at the bottom (``search``, ``get``, ``freshest_for_post``) are the
contract the API / auto-post / notifications use. Every function expects a
connection with ``row_factory = aiosqlite.Row`` (``src/db/connection.connect``).
"""
from __future__ import annotations

import base64
import json
import re
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Iterable, Optional, Sequence

from src.ingest import dedup, quality
from src.ingest.base import NormalizedVacancy
from src.ingest.text import excerpt

BATCH_SIZE = 200
SEARCH_MAX_LIMIT = 50
EXCERPT_LEN = 400
#: Description-like fields are already stored as ``description_text``.
_RAW_DROP_KEYS = ("description", "branded_description", "info", "requirements")
#: ``raw`` must keep these (``vacancy_format.osonish_store_detail``); other keys are dropped largest first.
_RAW_KEEP_KEYS = ("id", "hr")
_RAW_MAX = 4_096
#: A detail re-check failure backs the row off 1 h, 2 h, ... up to a day.
DETAIL_BACKOFF_BASE = 3_600
DETAIL_BACKOFF_MAX = 86_400
#: After this many failed re-checks in a row the stale rule applies again.
DETAIL_FAILURE_GIVE_UP = 8


@asynccontextmanager
async def write_tx(conn) -> AsyncIterator[None]:
    await conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        await conn.rollback()
        raise
    await conn.commit()


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _raw_json(raw: dict[str, Any]) -> str:
    """The source payload without description fields, at most ``_RAW_MAX`` chars.

    Too large: the largest other top-level values go first; ``{}`` when even
    the kept keys do not fit.
    """
    slim = {k: v for k, v in raw.items() if k not in _RAW_DROP_KEYS}
    text = _dumps(slim)
    if len(text) <= _RAW_MAX:
        return text
    sizes = sorted(((len(_dumps(v)), k) for k, v in slim.items() if k not in _RAW_KEEP_KEYS), reverse=True)
    for _size, key in sizes:
        del slim[key]
        text = _dumps(slim)
        if len(text) <= _RAW_MAX:
            return text
    return "{}"


def _row_values(v: NormalizedVacancy, now: int) -> tuple:
    keys = dedup.normalized_for_key(v)
    return (
        v.uid, v.source, v.source_id, v.title, v.employer, keys["employer_key"],
        v.salary_min, v.salary_max, v.currency,
        None if v.salary_gross is None else int(bool(v.salary_gross)),
        v.region_soato, v.district_soato, v.region_name, v.category, v.experience, v.employment, v.schedule,
        v.description_text,
        json.dumps(v.skills, ensure_ascii=False), json.dumps(v.contacts, ensure_ascii=False),
        v.url, int(v.published_at), now, now,
        None if v.is_open else now, None if v.is_open else "source_closed",
        "open" if v.is_open else "closed",
        quality.score(v, now), keys["dedup_key"], _raw_json(v.raw),
    )


_COLUMNS = (
    "uid, source, source_id, title, employer, employer_key, salary_min, salary_max, currency, salary_gross, "
    "region_soato, district_soato, region_name, category, experience, employment, schedule, description_text, "
    "skills_json, contacts_json, url, published_at, fetched_at, last_seen_at, closed_at, close_reason, status, "
    "quality_score, dedup_key, raw_json"
)
_PLACEHOLDERS = ",".join("?" * 30)

# A list sighting refreshes the list fields; detail-only fields (description,
# skills, contacts, category, raw) are kept once a detail check has filled them.
# A row the detail endpoint answered "gone" for stays closed: only a detail
# answer (``_UPSERT_DETAIL``) reopens it.
_UPSERT_LIST = f"""
INSERT INTO vacancies ({_COLUMNS}) VALUES ({_PLACEHOLDERS})
ON CONFLICT(uid) DO UPDATE SET
    title = excluded.title,
    employer = excluded.employer,
    employer_key = excluded.employer_key,
    salary_min = excluded.salary_min,
    salary_max = excluded.salary_max,
    currency = excluded.currency,
    salary_gross = excluded.salary_gross,
    region_soato = COALESCE(excluded.region_soato, vacancies.region_soato),
    district_soato = COALESCE(excluded.district_soato, vacancies.district_soato),
    region_name = CASE WHEN excluded.region_name != '' THEN excluded.region_name ELSE vacancies.region_name END,
    experience = excluded.experience,
    employment = excluded.employment,
    schedule = excluded.schedule,
    url = excluded.url,
    published_at = excluded.published_at,
    last_seen_at = excluded.last_seen_at,
    status = CASE WHEN vacancies.close_reason = 'gone' THEN vacancies.status ELSE excluded.status END,
    closed_at = CASE WHEN vacancies.close_reason = 'gone' THEN vacancies.closed_at ELSE excluded.closed_at END,
    close_reason = CASE WHEN vacancies.close_reason = 'gone'
        THEN vacancies.close_reason ELSE excluded.close_reason END,
    dedup_key = excluded.dedup_key,
    description_text = CASE WHEN vacancies.checked_at IS NULL
        THEN excluded.description_text ELSE vacancies.description_text END,
    skills_json = CASE WHEN vacancies.checked_at IS NULL THEN excluded.skills_json ELSE vacancies.skills_json END,
    contacts_json = CASE WHEN vacancies.checked_at IS NULL
        THEN excluded.contacts_json ELSE vacancies.contacts_json END,
    category = CASE WHEN vacancies.checked_at IS NULL OR excluded.category != ''
        THEN excluded.category ELSE vacancies.category END,
    raw_json = CASE WHEN vacancies.checked_at IS NULL THEN excluded.raw_json ELSE vacancies.raw_json END,
    quality_score = CASE WHEN vacancies.checked_at IS NULL
        THEN excluded.quality_score ELSE MAX(vacancies.quality_score, excluded.quality_score) END
"""

# A detail check is the authority: everything is replaced.
_UPSERT_DETAIL = f"""
INSERT INTO vacancies ({_COLUMNS}) VALUES ({_PLACEHOLDERS})
ON CONFLICT(uid) DO UPDATE SET
    title = excluded.title, employer = excluded.employer, employer_key = excluded.employer_key,
    salary_min = excluded.salary_min, salary_max = excluded.salary_max, currency = excluded.currency,
    salary_gross = excluded.salary_gross,
    region_soato = COALESCE(excluded.region_soato, vacancies.region_soato),
    district_soato = COALESCE(excluded.district_soato, vacancies.district_soato),
    region_name = CASE WHEN excluded.region_name != '' THEN excluded.region_name ELSE vacancies.region_name END,
    category = excluded.category, experience = excluded.experience, employment = excluded.employment,
    schedule = excluded.schedule, description_text = excluded.description_text,
    skills_json = excluded.skills_json, contacts_json = excluded.contacts_json, url = excluded.url,
    published_at = excluded.published_at, last_seen_at = excluded.last_seen_at,
    status = excluded.status, closed_at = excluded.closed_at, close_reason = excluded.close_reason,
    quality_score = excluded.quality_score, dedup_key = excluded.dedup_key, raw_json = excluded.raw_json
"""


def _chunks(items: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


async def upsert_batch(conn, items: Sequence[NormalizedVacancy], now: int) -> int:
    """Store list results (one short transaction per ``BATCH_SIZE`` rows) and group duplicates.

    Returns the number of rows that were new.
    """
    new_count = 0
    unique = list({v.uid: v for v in items}.values())
    for chunk in _chunks(unique, BATCH_SIZE):
        uids = [v.uid for v in chunk]
        marks = ",".join("?" * len(uids))
        # Everything that needs no lock is computed before BEGIN IMMEDIATE.
        values = [_row_values(v, now) for v in chunk]
        keys = {v.uid: dedup.dedup_key(v) for v in chunk}
        async with write_tx(conn):
            cur = await conn.execute(
                f"SELECT uid, dedup_key, status, district_soato FROM vacancies WHERE uid IN ({marks})", uids
            )
            before = {row[0]: (row[1], row[2], row[3]) for row in await cur.fetchall()}
            await conn.executemany(_UPSERT_LIST, values)
            changed = []
            for v in chunk:
                if v.uid not in before:
                    new_count += 1
                    changed.append(v.uid)
                elif before[v.uid][0] != keys[v.uid] or (
                    v.district_soato is not None and before[v.uid][2] != v.district_soato
                ):
                    changed.append(v.uid)
            await dedup.assign(conn, changed)
            # Closed by the source, or reopened by a new sighting: the group's canonical may change.
            status_changed = [
                v.uid for v in chunk
                if (not v.is_open) or (v.uid in before and before[v.uid][1] == "closed")
            ]
            if status_changed:
                await _regroup_for(conn, status_changed)
    return new_count


async def apply_detail(conn, v: NormalizedVacancy, now: int) -> None:
    """Store a full detail answer and mark the row checked (closing it when the source says so)."""
    values = _row_values(v, now)
    async with write_tx(conn):
        await conn.execute(_UPSERT_DETAIL, values)
        await conn.execute(
            "UPDATE vacancies SET checked_at = ?, detail_failures = 0, recheck_after = NULL WHERE uid = ?",
            (now, v.uid),
        )
        await dedup.assign(conn, [v.uid])
        if not v.is_open:
            await _regroup_for(conn, [v.uid])


async def _regroup_for(conn, uids: Sequence[str]) -> None:
    marks = ",".join("?" * len(uids))
    cur = await conn.execute(
        f"SELECT DISTINCT dedup_group FROM vacancies WHERE uid IN ({marks}) AND dedup_group IS NOT NULL", list(uids)
    )
    await dedup.regroup(conn, [row[0] for row in await cur.fetchall()])


async def close(conn, uids: Sequence[str], reason: str, now: int) -> int:
    """Close open vacancies by uid; a duplicate is promoted to canonical where needed."""
    if not uids:
        return 0
    total = 0
    for chunk in _chunks(list(uids), BATCH_SIZE):
        marks = ",".join("?" * len(chunk))
        async with write_tx(conn):
            cur = await conn.execute(
                f"""UPDATE vacancies SET status = 'closed', closed_at = ?, close_reason = ?, checked_at = ?
                    WHERE uid IN ({marks}) AND status = 'open'""",
                (now, reason, now, *chunk),
            )
            total += cur.rowcount
            await _regroup_for(conn, chunk)
    return total


async def close_stale(conn, source: str, seen_before: int, now: int, limit: int = 2000) -> int:
    """Close open rows of ``source`` neither seen in a list nor confirmed by detail since ``seen_before``.

    A row whose last detail re-check failed is not closed: the failure says
    nothing about the vacancy. After ``DETAIL_FAILURE_GIVE_UP`` failures in a
    row (days, with the backoff) the stale rule applies again.
    """
    cur = await conn.execute(
        """SELECT uid FROM vacancies WHERE source = ? AND status = 'open' AND last_seen_at < ?
             AND (detail_failures = 0 OR detail_failures >= ?) LIMIT ?""",
        (source, seen_before, DETAIL_FAILURE_GIVE_UP, limit),
    )
    uids = [row[0] for row in await cur.fetchall()]
    return await close(conn, uids, "stale", now)


async def purge_closed(conn, closed_before: int, limit: int = 5000) -> int:
    async with write_tx(conn):
        cur = await conn.execute(
            """DELETE FROM vacancies WHERE id IN (
                   SELECT id FROM vacancies WHERE status = 'closed' AND closed_at < ? LIMIT ?)""",
            (closed_before, limit),
        )
        return cur.rowcount


async def mark_checked(conn, uid: str, now: int) -> None:
    """Rotate a row to the back of the re-check queue without confirming it is still open."""
    async with write_tx(conn):
        await conn.execute("UPDATE vacancies SET checked_at = ? WHERE uid = ?", (now, uid))


async def record_detail_failure(conn, uid: str, now: int) -> None:
    """A re-check failed (outage, 5xx): count it and back the row off; it stays open and unconfirmed."""
    async with write_tx(conn):
        await conn.execute(
            """UPDATE vacancies SET checked_at = ?, detail_failures = detail_failures + 1,
                   recheck_after = ? + MIN(?, ? * (1 << MIN(detail_failures, 10)))
               WHERE uid = ?""",
            (now, now, DETAIL_BACKOFF_MAX, DETAIL_BACKOFF_BASE, uid),
        )


async def save_cursor(conn, source: str, cursor: str) -> None:
    """Persist progress mid-run so a later failure does not redo completed windows."""
    async with write_tx(conn):
        await conn.execute(
            """INSERT INTO ingest_cursor (source, cursor) VALUES (?, ?)
               ON CONFLICT(source) DO UPDATE SET cursor = excluded.cursor""",
            (source, cursor),
        )


async def pick_for_recheck(conn, source: str, limit: int, now: Optional[int] = None) -> list[str]:
    """``source_id`` of open vacancies never detail-checked first, then the longest unchecked.

    With ``now``, rows backed off after a failed re-check wait until ``recheck_after``.
    """
    if limit <= 0:
        return []
    cur = await conn.execute(
        """SELECT source_id FROM vacancies WHERE source = ? AND status = 'open'
             AND (? IS NULL OR recheck_after IS NULL OR recheck_after <= ?)
           ORDER BY checked_at IS NOT NULL, checked_at, published_at DESC LIMIT ?""",
        (source, now, now, limit),
    )
    return [row[0] for row in await cur.fetchall()]


async def get_cursor(conn, source: str) -> Optional[dict[str, Any]]:
    cur = await conn.execute(
        "SELECT source, cursor, last_run_at, last_ok_at, last_error, stats_json FROM ingest_cursor WHERE source = ?",
        (source,),
    )
    row = await cur.fetchone()
    if row is None:
        return None
    out = dict(row)
    try:
        out["stats"] = json.loads(out.pop("stats_json") or "{}")
    except ValueError:
        out["stats"] = {}
    return out


async def save_run(
    conn, source: str, *, now: int, cursor: Optional[str], ok: bool, error: Optional[str], stats: dict[str, Any]
) -> None:
    """Record a run. ``cursor=None`` keeps the stored cursor."""
    async with write_tx(conn):
        await conn.execute(
            """INSERT INTO ingest_cursor (source, cursor, last_run_at, last_ok_at, last_error, stats_json)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(source) DO UPDATE SET
                   cursor = COALESCE(excluded.cursor, ingest_cursor.cursor),
                   last_run_at = excluded.last_run_at,
                   last_ok_at = COALESCE(excluded.last_ok_at, ingest_cursor.last_ok_at),
                   last_error = excluded.last_error,
                   stats_json = excluded.stats_json""",
            (source, cursor, now, now if ok else None, (error or None) and error[:500], json.dumps(stats)),
        )


async def region_name_map(conn) -> dict[str, str]:
    """lower(``regions.name_uz``) -> soato, for osonish's name fallback (empty when the table is absent)."""
    try:
        cur = await conn.execute("SELECT soato, name_uz FROM regions")
    except Exception:
        return {}
    return {str(row[1]).lower(): str(row[0]) for row in await cur.fetchall() if row[0] and row[1]}


# ---------------------------------------------------------------- read API

_PUBLIC_COLUMNS = (
    "uid, source, source_id, title, employer, salary_min, salary_max, currency, salary_gross, region_soato, "
    "district_soato, region_name, category, experience, employment, schedule, description_text, skills_json, "
    "contacts_json, url, published_at, fetched_at, last_seen_at, checked_at, closed_at, close_reason, status, "
    "quality_score, dedup_group, dup_of"
)


def _to_dict(row: Any) -> dict[str, Any]:
    out = dict(row)
    for src, dst, empty in (("skills_json", "skills", []), ("contacts_json", "contacts", {})):
        try:
            out[dst] = json.loads(out.pop(src) or "null") or empty
        except ValueError:
            out[dst] = empty
    if out.get("salary_gross") is not None:
        out["salary_gross"] = bool(out["salary_gross"])
    out["excerpt"] = excerpt(out.get("description_text") or "", EXCERPT_LEN)
    return out


async def _attach_openings(conn, items: Sequence[dict[str, Any]]) -> None:
    """Set ``openings`` on each item: open rows in its dedup group (1 without a group).

    One grouped query over the page's groups (``idx_vacancies_dedup_group``).
    ``+status`` keeps the planner on the dedup_group index (status has few values).
    A duplicate collapsed into a canonical card counts as one more opening;
    closed members never count, so a lone open row is always 1.
    """
    groups = sorted({str(i["dedup_group"]) for i in items if i.get("dedup_group")})
    counts: dict[str, int] = {}
    for part in _chunks(groups, 500):
        marks = ",".join("?" * len(part))
        cur = await conn.execute(
            f"SELECT dedup_group, COUNT(*) FROM vacancies WHERE dedup_group IN ({marks}) AND +status = 'open' "
            "GROUP BY dedup_group",
            list(part),
        )
        counts.update({str(r[0]): int(r[1]) for r in await cur.fetchall()})
    for item in items:
        group = item.get("dedup_group")
        item["openings"] = max(1, counts.get(str(group), 1)) if group else 1


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
#: Same set the FTS view strips (``m025_ingest_hardening.APOSTROPHES``): o'qituvchi = oʻqituvchi.
_APOSTROPHES = str.maketrans("", "", "ʻʼ'`‘’")


def fts_query(text: str, max_terms: int = 8) -> str:
    """User text -> a safe FTS5 query: every word quoted and prefix-matched, AND-ed.

    Quoting removes FTS5 syntax (``OR``, ``NEAR``, ``*``, ``:``, ``"``) from
    user input, so no input can raise a syntax error or widen the query.
    """
    terms = _TOKEN_RE.findall((text or "").translate(_APOSTROPHES))[:max_terms]
    return " ".join(f'"{t}"*' for t in terms)


def _encode_cursor(published_at: int, row_id: int) -> str:
    return base64.urlsafe_b64encode(f"{published_at}:{row_id}".encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> Optional[tuple[int, int]]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        a, b = raw.split(":")
        return int(a), int(b)
    except (ValueError, UnicodeDecodeError):
        return None


def _filters(
    *,
    query: Optional[str],
    region_soato: Optional[str],
    district_soato: Optional[str],
    min_salary: int,
    source: Optional[str],
) -> tuple[list[str], list[Any]]:
    where = ["v.status = 'open'", "v.dup_of IS NULL"]
    params: list[Any] = []
    if query:
        match = fts_query(query)
        if match:
            where.append("v.id IN (SELECT rowid FROM vacancies_fts WHERE vacancies_fts MATCH ?)")
            params.append(match)
    if region_soato:
        where.append("v.region_soato = ?")
        params.append(str(region_soato))
    if district_soato:
        where.append("v.district_soato = ?")
        params.append(str(district_soato))
    if min_salary and min_salary > 0:
        # Only UZS amounts are comparable; foreign-currency salaries never pass a UZS floor.
        where.append("COALESCE(v.currency, 'UZS') = 'UZS' AND COALESCE(v.salary_max, v.salary_min, 0) >= ?")
        params.append(int(min_salary))
    if source:
        where.append("v.source = ?")
        params.append(source)
    return where, params


#: Sort orders of ``search``: (SQL key expression, direction). The key is an
#: integer so one ``key:id`` cursor format serves every order.
_SORTS: dict[str, tuple[str, str]] = {
    "new": ("v.published_at", "DESC"),
    "old": ("v.published_at", "ASC"),
    # Only UZS amounts are comparable: foreign-currency rows sort as "no salary".
    "salary": (
        "CASE WHEN COALESCE(v.currency, 'UZS') = 'UZS' THEN COALESCE(v.salary_max, v.salary_min, 0) ELSE 0 END",
        "DESC",
    ),
}


async def search(
    conn,
    *,
    query: Optional[str] = None,
    region_soato: Optional[str] = None,
    district_soato: Optional[str] = None,
    min_salary: int = 0,
    source: Optional[str] = None,
    limit: int = 20,
    cursor: Optional[str] = None,
    sort: str = "new",
    offset: int = 0,
    with_total: bool = False,
) -> dict[str, Any]:
    """Open canonical vacancies: ``{items, next_cursor, total|None}``.

    ``sort`` is ``new`` (default), ``old`` or ``salary`` (UZS, highest first).
    ``total`` is counted for the first page (``cursor is None``) or when
    ``with_total`` is set. ``offset`` (only without a cursor) serves clients
    that page by number; the cursor is the normal way to page.
    """
    limit = max(1, min(int(limit), SEARCH_MAX_LIMIT))
    key_sql, direction = _SORTS.get(sort, _SORTS["new"])
    where, params = _filters(
        query=query, region_soato=region_soato, district_soato=district_soato, min_salary=min_salary, source=source
    )
    total = None
    if cursor is None or with_total:
        cur = await conn.execute(f"SELECT COUNT(*) FROM vacancies v WHERE {' AND '.join(where)}", params)
        total = int((await cur.fetchone())[0])
    page_where, page_params = list(where), list(params)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is None:
            return {"items": [], "next_cursor": None, "total": total}
        op = "<" if direction == "DESC" else ">"
        page_where.append(f"(({key_sql}) {op} ? OR (({key_sql}) = ? AND v.id {op} ?))")
        page_params += [decoded[0], decoded[0], decoded[1]]
    skip = max(0, int(offset)) if not cursor else 0
    cur = await conn.execute(
        f"""SELECT v.id AS _id, ({key_sql}) AS _key, {', '.join('v.' + c.strip() for c in _PUBLIC_COLUMNS.split(','))}
            FROM vacancies v WHERE {' AND '.join(page_where)}
            ORDER BY _key {direction}, v.id {direction} LIMIT ? OFFSET ?""",
        (*page_params, limit + 1, skip),
    )
    rows = await cur.fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = []
    for row in rows:
        item = _to_dict(row)
        item.pop("_id", None)
        item.pop("_key", None)
        items.append(item)
    await _attach_openings(conn, items)
    next_cursor = _encode_cursor(int(rows[-1]["_key"] or 0), rows[-1]["_id"]) if has_more and rows else None
    return {"items": items, "next_cursor": next_cursor, "total": total}


async def get(conn, uid: str, *, with_raw: bool = False) -> Optional[dict[str, Any]]:
    """One vacancy by uid in any status (``None`` when unknown).

    ``with_raw`` adds ``raw`` (the source payload without its description,
    ``{}`` when it was too large) for consumers that render the source's own
    fields, e.g. an osonish detail checked by the runner.
    """
    columns = _PUBLIC_COLUMNS + (", raw_json" if with_raw else "")
    cur = await conn.execute(f"SELECT {columns} FROM vacancies WHERE uid = ?", (uid,))
    row = await cur.fetchone()
    if row is None:
        return None
    out = _to_dict(row)
    if with_raw:
        try:
            raw = json.loads(out.pop("raw_json") or "{}")
        except ValueError:
            raw = {}
        out["raw"] = raw if isinstance(raw, dict) else {}
    await _attach_openings(conn, [out])
    return out


async def has_open(conn) -> bool:
    """True once the store holds at least one open vacancy (False before the first ingest)."""
    if not await _table_exists(conn, "vacancies"):
        return False
    cur = await conn.execute("SELECT 1 FROM vacancies WHERE status = 'open' LIMIT 1")
    return await cur.fetchone() is not None


async def _table_exists(conn, name: str) -> bool:
    cur = await conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,))
    return await cur.fetchone() is not None


async def freshest_for_post(
    conn,
    *,
    since: int,
    min_quality: int = 0,
    min_salary: int = 0,
    exclude_posted: bool = True,
    channel: Optional[str] = None,
    region_soato: Optional[str] = None,
    limit: int = 20,
    require_salary: bool = False,
    require_employer: bool = False,
) -> list[dict[str, Any]]:
    """Open canonical vacancies published at/after ``since`` for the auto-post, newest then best first.

    ``exclude_posted`` skips uids already in ``posted_vacancies`` (for ``channel``
    when given, else for any channel). ``require_salary`` keeps only rows with
    an amount (any currency), ``require_employer`` only rows naming the employer.
    """
    where, params = _filters(
        query=None, region_soato=region_soato, district_soato=None, min_salary=min_salary, source=None
    )
    where += ["v.published_at >= ?", "v.quality_score >= ?"]
    params += [int(since), int(min_quality)]
    if require_salary:
        where.append("COALESCE(v.salary_max, v.salary_min, 0) > 0")
    if require_employer:
        where.append("TRIM(COALESCE(v.employer, '')) != ''")
    if exclude_posted and await _table_exists(conn, "posted_vacancies"):
        if channel:
            where.append("NOT EXISTS (SELECT 1 FROM posted_vacancies p WHERE p.vacancy_uid = v.uid AND p.channel = ?)")
            params.append(str(channel))
        else:
            where.append("NOT EXISTS (SELECT 1 FROM posted_vacancies p WHERE p.vacancy_uid = v.uid)")
    cur = await conn.execute(
        f"""SELECT {', '.join('v.' + c.strip() for c in _PUBLIC_COLUMNS.split(','))}
            FROM vacancies v WHERE {' AND '.join(where)}
            ORDER BY v.published_at DESC, v.quality_score DESC LIMIT ?""",
        (*params, max(1, int(limit))),
    )
    items = [_to_dict(row) for row in await cur.fetchall()]
    await _attach_openings(conn, items)
    return items
