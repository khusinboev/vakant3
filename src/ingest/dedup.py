"""Cross-source duplicate detection.

Two vacancies are the same job only when they name the same (non-empty)
normalised employer, were published within 14 days of each other and are not
in two different known districts, and then either
- their exact key matches: normalised title + employer + region + salary bucket, or
- fuzzy: same region and ``difflib`` title ratio >= 0.9, unless the titles
  differ in a short or numeric token ("Haydovchi B" / "Haydovchi C").

Matches form a group (``dedup_group`` = the canonical uid). The canonical copy
is the open row with the highest source priority (hh > osonish), then the
higher quality score, then the earliest published; every other member gets
``dup_of`` = canonical. Searches show only ``dup_of IS NULL``.
"""
from __future__ import annotations

import hashlib
import re
from difflib import SequenceMatcher
from typing import Any, Iterable

from src.ingest.base import SOURCE_PRIORITY, NormalizedVacancy

FUZZY_RATIO = 0.9
FUZZY_WINDOW_SECONDS = 14 * 86_400
SALARY_BUCKET = 500_000

_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}
_LEGAL_FORMS = re.compile(
    r"\b(ooo|mchj|xk|ok|aj|llc|ltd|inc|jsc|qk|chp|ip|oao|zao|pao|ao|unitar|korxona|davlat|"
    r"масъулияти|чекланган|жамияти)\b"
)
_APOSTROPHES = str.maketrans("", "", "ʻʼ'`‘’")
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def _translit(text: str) -> str:
    return "".join(_CYR.get(ch, ch) for ch in text)


def normalize_text(text: str) -> str:
    text = text.lower().translate(_APOSTROPHES)
    text = _translit(text)
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def employer_key(name: str) -> str:
    text = normalize_text(name)
    text = _LEGAL_FORMS.sub(" ", text)
    return " ".join(text.split())


def _salary_bucket(v: NormalizedVacancy) -> str:
    amount = v.salary_max or v.salary_min or 0
    if amount <= 0:
        return "-"
    currency = (v.currency or "UZS").upper()
    if currency in ("UZS", "SUM", "SO'M"):
        return f"UZS{amount // SALARY_BUCKET}"
    return f"{currency}{amount // max(1, SALARY_BUCKET // 10_000)}"


def dedup_key(v: NormalizedVacancy) -> str:
    raw = "|".join((normalize_text(v.title), employer_key(v.employer), v.region_soato or "", _salary_bucket(v)))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def title_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def canonical_rank(row: Any) -> tuple:
    """Sort key: the first row after ``sorted(...)`` is canonical."""
    is_open = row["status"] == "open"
    return (
        0 if is_open else 1,
        -SOURCE_PRIORITY.get(row["source"], 0),
        -int(row["quality_score"] or 0),
        int(row["published_at"] or 0),
        row["uid"],
    )


_MATCH_COLUMNS = (
    "uid, title, employer_key, region_soato, district_soato, published_at, dedup_key, dedup_group, "
    "COALESCE(dedup_group, uid) AS grp"
)


def _distinguishing_tokens(a: str, b: str) -> bool:
    """True when the titles differ in a short or numeric token ("Haydovchi B" / "Haydovchi C", "Kassir 1" / "2")."""
    diff = set(normalize_text(a).split()) ^ set(normalize_text(b).split())
    return any(len(tok) <= 3 or any(ch.isdigit() for ch in tok) for tok in diff)


def titles_match(a: str, b: str) -> bool:
    return title_ratio(a, b) >= FUZZY_RATIO and not _distinguishing_tokens(a, b)


def is_match(a: Any, b: Any) -> bool:
    """Do two vacancy rows (``_MATCH_COLUMNS``) describe the same job?

    Never without a named employer, never more than ``FUZZY_WINDOW_SECONDS``
    apart, never in two different known districts. Then either the exact key
    matches, or the same employer in the same region has a near-identical title.
    """
    if not a["employer_key"] or a["employer_key"] != b["employer_key"]:
        return False
    if abs(int(a["published_at"] or 0) - int(b["published_at"] or 0)) > FUZZY_WINDOW_SECONDS:
        return False
    if a["district_soato"] and b["district_soato"] and a["district_soato"] != b["district_soato"]:
        return False
    if a["dedup_key"] and a["dedup_key"] == b["dedup_key"]:
        return True
    if not a["region_soato"] or a["region_soato"] != b["region_soato"]:
        return False
    return titles_match(a["title"], b["title"])


async def _load(conn, uid: str) -> Any:
    cur = await conn.execute(f"SELECT {_MATCH_COLUMNS} FROM vacancies WHERE uid = ?", (uid,))
    return await cur.fetchone()


async def find_match(conn, uid: str) -> str | None:
    """Group id of an open vacancy (any source) that duplicates ``uid``, else ``None``.

    Both lookups are index range scans (``m025_ingest_hardening``): this runs
    inside the upsert's write transaction, so it must never scan the table.
    ``+status`` keeps the planner (no ``sqlite_stat1``) off
    ``idx_vacancies_status_pub``, which would walk every open row.
    """
    me = await _load(conn, uid)
    if me is None or not me["employer_key"]:
        return None
    lo, hi = me["published_at"] - FUZZY_WINDOW_SECONDS, me["published_at"] + FUZZY_WINDOW_SECONDS
    own_group = me["dedup_group"] or uid
    cur = await conn.execute(
        f"""SELECT {_MATCH_COLUMNS} FROM vacancies
            WHERE dedup_key = ? AND status = 'open' AND published_at BETWEEN ? AND ? AND uid != ?
            ORDER BY published_at LIMIT 50""",
        (me["dedup_key"], lo, hi, uid),
    )
    for cand in await cur.fetchall():
        if cand["grp"] != own_group and is_match(me, cand):
            return cand["grp"]
    if not me["region_soato"]:
        return None
    cur = await conn.execute(
        f"""SELECT {_MATCH_COLUMNS} FROM vacancies
            WHERE employer_key = ? AND region_soato = ? AND published_at BETWEEN ? AND ?
              AND +status = 'open' AND uid != ?
            LIMIT 200""",
        (me["employer_key"], me["region_soato"], lo, hi, uid),
    )
    best: tuple[float, str] | None = None
    for cand in await cur.fetchall():
        if cand["grp"] == own_group or not is_match(me, cand):
            continue
        ratio = title_ratio(me["title"], cand["title"])
        if best is None or ratio > best[0]:
            best = (ratio, cand["grp"])
    return best[1] if best else None


async def regroup(conn, group_ids: Iterable[str]) -> None:
    """Recompute canonical / dup_of for each group. Caller owns the transaction."""
    for group in set(group_ids):
        cur = await conn.execute(
            "SELECT uid, source, status, quality_score, published_at FROM vacancies WHERE dedup_group = ? OR uid = ?",
            (group, group),
        )
        members = await cur.fetchall()
        if not members:
            continue
        canonical = sorted(members, key=canonical_rank)[0]["uid"]
        uids = [m["uid"] for m in members]
        marks = ",".join("?" * len(uids))
        await conn.execute(
            f"""UPDATE vacancies
                SET dedup_group = ?, dup_of = CASE WHEN uid = ? THEN NULL ELSE ? END
                WHERE uid IN ({marks})""",
            (canonical, canonical, canonical, *uids),
        )


async def _still_grouped(conn, me: Any) -> bool:
    """True when ``me`` still duplicates at least one other member of its group."""
    cur = await conn.execute(
        f"SELECT {_MATCH_COLUMNS} FROM vacancies WHERE dedup_group = ? AND uid != ? LIMIT 200",
        (me["dedup_group"], me["uid"]),
    )
    return any(is_match(me, other) for other in await cur.fetchall())


async def _detach(conn, me: Any) -> None:
    """Take ``me`` out of its group (it no longer matches anyone there) and fix the rest of the group."""
    uid, group = me["uid"], me["dedup_group"]
    await conn.execute("UPDATE vacancies SET dedup_group = uid, dup_of = NULL WHERE uid = ?", (uid,))
    if group != uid:
        await regroup(conn, [group])
        return
    # ``me`` was the group id: the others move under their own best member.
    cur = await conn.execute(
        "SELECT uid, source, status, quality_score, published_at FROM vacancies WHERE dedup_group = ? AND uid != ?",
        (uid, uid),
    )
    others = await cur.fetchall()
    if not others:
        return
    new_group = sorted(others, key=canonical_rank)[0]["uid"]
    await conn.execute(
        "UPDATE vacancies SET dedup_group = ? WHERE dedup_group = ? AND uid != ?", (new_group, uid, uid)
    )
    await regroup(conn, [new_group])


async def assign(conn, uids: Iterable[str]) -> None:
    """Attach each new/changed vacancy to its duplicate group (or its own). Caller owns the transaction.

    A grouped row that no longer matches any other member (its title, salary
    or employer changed) is split out and shown again before it looks for a
    new group.
    """
    for uid in uids:
        me = await _load(conn, uid)
        if me is None:
            continue
        current = me["dedup_group"]
        if current:
            if await _still_grouped(conn, me):
                continue
            await _detach(conn, me)
            current = uid
        match = await find_match(conn, uid)
        if match is None:
            if current is None:
                await conn.execute(
                    "UPDATE vacancies SET dedup_group = uid, dup_of = NULL WHERE uid = ?", (uid,)
                )
            continue
        # Merge: my own group (if I was canonical of one) joins the matched group.
        await conn.execute(
            "UPDATE vacancies SET dedup_group = ? WHERE uid = ? OR dedup_group = ?", (match, uid, uid)
        )
        await regroup(conn, [match])


def normalized_for_key(v: NormalizedVacancy) -> dict[str, str]:
    return {"dedup_key": dedup_key(v), "employer_key": employer_key(v.employer)}
