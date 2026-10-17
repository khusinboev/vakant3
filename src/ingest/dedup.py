"""Cross-source duplicate detection.

Two vacancies are the same job when either
- their exact key matches: normalised title + employer + region + salary bucket, or
- fuzzy: same normalised employer and region, published within 14 days of
  each other, and ``difflib`` title ratio >= 0.9.

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
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def _translit(text: str) -> str:
    return "".join(_CYR.get(ch, ch) for ch in text)


def normalize_text(text: str) -> str:
    text = text.lower().replace("ʻ", "").replace("'", "").replace("’", "").replace("`", "")
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


async def find_match(conn, uid: str) -> str | None:
    """Group id of an existing *other-source-or-same* vacancy that duplicates ``uid``, else ``None``."""
    cur = await conn.execute(
        "SELECT uid, title, employer_key, region_soato, published_at, dedup_key FROM vacancies WHERE uid = ?",
        (uid,),
    )
    me = await cur.fetchone()
    if me is None:
        return None
    cur = await conn.execute(
        """SELECT COALESCE(dedup_group, uid) FROM vacancies
           WHERE dedup_key = ? AND uid != ? AND status = 'open'
           ORDER BY published_at LIMIT 1""",
        (me["dedup_key"], uid),
    )
    row = await cur.fetchone()
    if row is not None:
        return row[0]
    if not me["employer_key"] or not me["region_soato"]:
        return None
    cur = await conn.execute(
        """SELECT uid, title, COALESCE(dedup_group, uid) AS grp FROM vacancies
           WHERE employer_key = ? AND region_soato = ? AND uid != ? AND status = 'open'
             AND published_at BETWEEN ? AND ?
           LIMIT 200""",
        (
            me["employer_key"],
            me["region_soato"],
            uid,
            me["published_at"] - FUZZY_WINDOW_SECONDS,
            me["published_at"] + FUZZY_WINDOW_SECONDS,
        ),
    )
    best: tuple[float, str] | None = None
    for cand in await cur.fetchall():
        ratio = title_ratio(me["title"], cand["title"])
        if ratio >= FUZZY_RATIO and (best is None or ratio > best[0]):
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


async def assign(conn, uids: Iterable[str]) -> None:
    """Attach each new/changed vacancy to its duplicate group (or its own). Caller owns the transaction."""
    for uid in uids:
        cur = await conn.execute("SELECT dedup_group FROM vacancies WHERE uid = ?", (uid,))
        row = await cur.fetchone()
        if row is None:
            continue
        current = row[0]
        if current and current != uid:
            continue  # already joined to a group; regroup on close keeps it right
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
