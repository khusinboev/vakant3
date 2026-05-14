import asyncio
import random
import time
from datetime import datetime, timedelta

import aiosqlite

from config import BASE_DIR, bot
from src.functions.scraping import fetch_osonish_detail, fetch_osonish_list
from src.functions.vacancy_format import format_vacancy_message_html


def _next_random_daily_ts() -> int:
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    target = tomorrow.replace(
        hour=random.randint(9, 22),
        minute=random.randint(0, 59),
        second=0,
        microsecond=0,
    )
    return int(target.timestamp())


async def _ensure_settings(conn: aiosqlite.Connection) -> None:
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS webapp_admin_settings (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            auto_post_enabled INTEGER NOT NULL DEFAULT 0,
            auto_post_channel TEXT NOT NULL DEFAULT '',
            auto_post_min_salary INTEGER NOT NULL DEFAULT 8000000,
            referral_enabled INTEGER NOT NULL DEFAULT 0,
            referral_required_count INTEGER NOT NULL DEFAULT 0,
            next_auto_post_ts INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    await conn.execute(
        """
        INSERT OR IGNORE INTO webapp_admin_settings (
            singleton,
            auto_post_enabled,
            auto_post_channel,
            auto_post_min_salary,
            referral_enabled,
            referral_required_count,
            next_auto_post_ts
        )
        VALUES (1, 0, '', 8000000, 0, 0, 0)
        """
    )
    await conn.commit()


async def auto_post_loop() -> None:
    while True:
        try:
            async with aiosqlite.connect(BASE_DIR) as conn:
                await _ensure_settings(conn)
                conn.row_factory = aiosqlite.Row

                cursor = await conn.execute(
                    "SELECT auto_post_enabled, auto_post_channel, auto_post_min_salary, next_auto_post_ts "
                    "FROM webapp_admin_settings WHERE singleton = 1"
                )
                row = await cursor.fetchone()
                if not row:
                    await asyncio.sleep(300)
                    continue

                enabled = bool(int(row["auto_post_enabled"] or 0))
                channel = str(row["auto_post_channel"] or "").strip()
                min_salary = int(row["auto_post_min_salary"] or 0)
                next_ts = int(row["next_auto_post_ts"] or 0)

                now_ts = int(time.time())

                if not enabled or not channel:
                    await asyncio.sleep(300)
                    continue

                if next_ts <= 0:
                    next_ts = _next_random_daily_ts()
                    await conn.execute(
                        "UPDATE webapp_admin_settings SET next_auto_post_ts = ? WHERE singleton = 1",
                        (next_ts,),
                    )
                    await conn.commit()
                    await asyncio.sleep(300)
                    continue

                if now_ts < next_ts:
                    await asyncio.sleep(120)
                    continue

                vacancies, _ = await fetch_osonish_list(
                    page=1,
                    salary=min_salary,
                    soato_region="",
                    soato_district="",
                    mmk_group_field_id=None,
                    sort_key="",
                    sort_type="",
                    search="",
                )
                if vacancies:
                    chosen = random.choice(vacancies[: min(5, len(vacancies))])
                    raw_id = int(chosen.uid.split("_", 1)[1])
                    detail = await fetch_osonish_detail(raw_id)
                    if isinstance(detail, dict):
                        text = format_vacancy_message_html(chosen.uid, detail)
                        await bot.send_message(channel, text, disable_web_page_preview=True)

                next_ts = _next_random_daily_ts()
                await conn.execute(
                    "UPDATE webapp_admin_settings SET next_auto_post_ts = ? WHERE singleton = 1",
                    (next_ts,),
                )
                await conn.commit()

                await asyncio.sleep(60)
        except Exception:
            await asyncio.sleep(120)
