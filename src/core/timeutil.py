# ============================================================
# src/core/timeutil.py
# Yagona vaqt mintaqasi manbasi: Asia/Tashkent.
# pytz va timedelta(hours=5) o'rniga shu modul ishlatiladi.
# ============================================================
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Tashkent")

# Eski kod bilan moslik uchun nom (auto_post/notification schedulerlari).
TZ_UZB = TZ


def now_tz() -> datetime:
    """Toshkent vaqti bo'yicha hozirgi payt (tz-aware)."""
    return datetime.now(TZ)


def today_start(moment: datetime | None = None) -> datetime:
    """Berilgan paytning (yoki hozirning) Toshkent bo'yicha yarim tuni."""
    base = moment or now_tz()
    return base.astimezone(TZ).replace(hour=0, minute=0, second=0, microsecond=0)


def today_start_ts(moment: datetime | None = None) -> int:
    return int(today_start(moment).timestamp())


def day_key(moment: datetime | None = None) -> str:
    """'YYYY-MM-DD' — kun almashganini aniqlash uchun marker."""
    return (moment or now_tz()).astimezone(TZ).strftime("%Y-%m-%d")


def week_key(moment: datetime | None = None) -> str:
    """'YYYY-Www' — ISO hafta markeri (haftalik statistika uchun)."""
    base = (moment or now_tz()).astimezone(TZ)
    iso = base.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def month_step_back(moment: datetime, months: int) -> datetime:
    """moment ning oyi boshidan `months` oy orqaga (fevral ham to'g'ri hisoblanadi)."""
    year = moment.year
    month = moment.month - months
    while month <= 0:
        month += 12
        year -= 1
    return moment.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def month_end(first_day: datetime) -> datetime:
    """Oy boshidan shu oyning oxirgi soniyasiga."""
    if first_day.month == 12:
        next_first = first_day.replace(year=first_day.year + 1, month=1, day=1)
    else:
        next_first = first_day.replace(month=first_day.month + 1, day=1)
    return next_first - timedelta(seconds=1)
