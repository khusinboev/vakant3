"""0-100 quality score: how useful a vacancy is to show or post.

Points: salary 25, employer 15, description up to 20, freshness up to 15,
known region 10, a sane (non-spammy) title 10, a link or contacts 5.
"""
from __future__ import annotations

import re

from src.ingest.base import NormalizedVacancy

DAY = 86_400

_SPAM_PHRASES = (
    "без вложений", "пассивный доход", "быстрый заработок", "заработок в интернете", "сетевой маркетинг",
    "investitsiyasiz", "tez pul", "passiv daromad", "uydan turib pul", "crypto", "крипто",
)
_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def is_spammy_title(title: str) -> bool:
    t = title.strip()
    if len(t) < 3 or len(t) > 150:
        return True
    letters = [c for c in t if c.isalpha()]
    if len(letters) >= 10 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        return True
    if t.count("!") >= 2 or t.count("$") >= 2 or len(_EMOJI_RE.findall(t)) >= 2:
        return True
    low = t.lower()
    return any(p in low for p in _SPAM_PHRASES)


def score(v: NormalizedVacancy, now: int) -> int:
    points = 0
    if (v.salary_min or 0) > 0 or (v.salary_max or 0) > 0:
        points += 25
    if v.employer.strip():
        points += 15
    desc = len(v.description_text)
    if desc >= 400:
        points += 20
    elif desc >= 100:
        points += 10
    elif desc > 0:
        points += 4
    age = max(0, now - v.published_at)
    if age <= DAY:
        points += 15
    elif age <= 3 * DAY:
        points += 10
    elif age <= 7 * DAY:
        points += 5
    if v.region_soato:
        points += 10
    if not is_spammy_title(v.title):
        points += 10
    if v.url or v.contacts:
        points += 5
    return max(0, min(100, points))
