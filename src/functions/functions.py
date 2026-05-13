# ============================================
# src/functions/functions.py - Aiogram 3.x
# ============================================
import aiosqlite
import logging
import re
from dataclasses import asdict
from html import unescape
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import BASE_DIR
from src.functions.cache import CACHE_TTL, cache_get, cache_set, make_cache_key
from src.functions.scraping import (
    Vacancy,
    fetch_ishapi_detail,
    fetch_ishapi_list,
    fetch_osonish_detail,
    fetch_osonish_list,
)

logger = logging.getLogger(__name__)

# Legacy ishapi spec codes -> osonish mmk_group_field_id mapping.
LEGACY_SPEC_TO_OSONISH_FIELD: dict[str, int] = {
    "22,322,323,324": 47,  # Sog'liqni saqlash
    "71": 41,              # Qurilish
    "91,522,523": 64,      # Savdo va marketing
    "61": 7,               # Qishloq xo'jaligi
    "214": 41,             # Arxitektura (Qurilish yo'nalishiga yaqin)
    "213,312": 12,         # IT
    "23,33": 42,           # Ta'lim
    "83": 36,              # Haydovchilik (Transport)
}


def normalize_osonish_field_id(raw_spec: str) -> int | None:
    """Convert stored user `specs` value (legacy/new) to osonish field id."""
    val = (raw_spec or "").strip()
    if not val:
        return None

    if val.startswith("spec:"):
        val = val[5:]

    if val in LEGACY_SPEC_TO_OSONISH_FIELD:
        return LEGACY_SPEC_TO_OSONISH_FIELD[val]

    if val.isdigit():
        return int(val)

    return None


class functions:
    @staticmethod
    async def check_on_start(user_id: int, bot):
        """Kanalga obuna tekshiruvi"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        if not rows:
            return True

        for (channel_id,) in rows:
            try:
                member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                if member.status not in ["member", "creator", "administrator"]:
                    return False
            except Exception:
                return False

        return True


class panel_func:
    @staticmethod
    async def channel_add(channel_id: str):
        """Kanal qo'shish"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            try:
                await conn.execute(
                    "INSERT OR IGNORE INTO channels (id) VALUES (?)",
                    (channel_id,),
                )
                await conn.commit()
            except Exception:
                pass

    @staticmethod
    async def channel_delete(channel_id: str):
        """Kanal o'chirish"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            await conn.execute(
                "DELETE FROM channels WHERE id = ?",
                (channel_id,),
            )
            await conn.commit()

    @staticmethod
    async def channel_list(bot):
        """Kanallar ro'yxati"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        result = ""
        for row in rows:
            try:
                chat = await bot.get_chat(chat_id=row[0])
                result += (
                    "------------------------------------------------\n"
                    f"Kanal useri: {row[0]}\n"
                    f"Kanal nomi: {chat.title}\n"
                    f"Kanal ID: {chat.id}\n"
                    f"Haqida: {chat.description or 'Mavjud emas'}\n"
                )
            except Exception:
                result += f"Kanal {row[0]} - botni admin qiling\n"

        return result or "Kanallar mavjud emas"


async def join_inline_btn(user_id: int, bot):
    """Kanalga obuna tugmalari"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT id FROM channels")
        rows = await cursor.fetchall()

    buttons = []
    for idx, (channel_id,) in enumerate(rows, 1):
        try:
            chat = await bot.get_chat(chat_id=channel_id)
            url = chat.invite_link
            if not url:
                url = await bot.export_chat_invite_link(channel_id)
            if url:
                buttons.append([InlineKeyboardButton(text=f"{idx} - kanal", url=url)])
        except Exception:
            pass

    buttons.append([InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="check")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _strip_html(text: str) -> str:
    no_tags = re.sub(r"<[^>]+>", "\n", text)
    no_entities = unescape(no_tags)
    return re.sub(r"\n{3,}", "\n\n", no_entities).strip()


def _serialize_vacancies(vacancies: list[Vacancy]) -> list[dict[str, Any]]:
    return [asdict(v) for v in vacancies]


def _deserialize_vacancies(items: list[dict[str, Any]]) -> list[Vacancy]:
    vacancies: list[Vacancy] = []
    for item in items:
        try:
            vacancies.append(Vacancy(**item))
        except Exception:
            continue
    return vacancies


def _interleave_lists(a: list[Vacancy], b: list[Vacancy]) -> list[Vacancy]:
    merged: list[Vacancy] = []
    max_len = max(len(a), len(b))
    for i in range(max_len):
        if i < len(a):
            merged.append(a[i])
        if i < len(b):
            merged.append(b[i])
    return merged


async def get_user_search_params(user_id: int) -> tuple[int, str, str, str]:
    """(money, yurt, specs, region_soato)"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT region, district, specs, money FROM users WHERE user_id = ?",
            (user_id,),
        )
        user_data = await cursor.fetchone()

        if not user_data:
            return 0, "", "", ""

        region, district, specs, money = user_data

        yurt = ""
        region_soato = ""

        if region:
            cursor = await conn.execute(
                "SELECT soato FROM regions WHERE name_uz = ?",
                (region,),
            )
            row = await cursor.fetchone()
            if row and row[0]:
                region_soato = str(row[0])
                yurt = region_soato

        if region and district:
            cursor = await conn.execute(
                "SELECT d.soato FROM districts d "
                "JOIN regions r ON d.region_soato = r.soato "
                "WHERE d.name_uz = ? AND r.name_uz = ?",
                (district, region),
            )
            row = await cursor.fetchone()
            if row and row[0]:
                yurt = str(row[0])

    return int(money or 0), yurt, str(specs or ""), region_soato


async def search_vakant(page: int, money: int, yurt: str, specs: str) -> tuple[list[Vacancy], int]:
    """
    Temporarily fetch from osonish only (ishapi is geo-blocked on current VPS).
    """
    cache_key = make_cache_key(
        "search",
        mode="osonish_filters_v2",
        page=page,
        money=money or 0,
        yurt=yurt or "",
        specs=specs or "",
    )
    cached = await cache_get(cache_key)
    if isinstance(cached, dict):
        items = cached.get("vacancies")
        last_page = cached.get("last_page", 1)
        if isinstance(items, list):
            return _deserialize_vacancies(items), int(last_page or 1)

    # ishapi disabled (geo-blocked on current VPS)
    # To re-enable: uncomment and restore asyncio.gather branch below
    # ishapi_result = await fetch_ishapi_list(
    #     page=page,
    #     salary=money or 0,
    #     soato=yurt or "",
    #     nskz=specs or "",
    # )

    try:
        soato_region = ""
        soato_district = ""
        if yurt:
            # Osonish uses separate params for region and district.
            if len(yurt) > 4:
                soato_district = yurt
            else:
                soato_region = yurt

        field_id = normalize_osonish_field_id(specs)
        osonish_items, last_page = await fetch_osonish_list(
            page=page,
            salary=money or 0,
            soato_region=soato_region,
            soato_district=soato_district,
            mmk_group_field_id=field_id,
        )
    except Exception as e:
        logger.error("search_vakant: osonish error: %s", e)
        osonish_items, last_page = [], 1

    await cache_set(
        cache_key,
        {"vacancies": _serialize_vacancies(osonish_items), "last_page": last_page},
        ttl=CACHE_TTL,
    )
    return osonish_items, last_page


async def search_vakant_for_user(user_id: int, page: int):
    money, yurt, specs, _ = await get_user_search_params(user_id)
    vacancies, last_page = await search_vakant(page=page, money=money, yurt=yurt, specs=specs)

    if not vacancies:
        return ("⚠️ Natija topilmadi.", [], page, (page - 1) * 5 + 1, last_page)

    from_num = (page - 1) * 5 + 1
    num = from_num
    texts = ""
    ids: list[str] = []

    for item in vacancies:
        texts += (
            f"<b>👨‍💻 {num}- VAKANSIYA\n\n</b>"
            f"<b>🆔 ID: </b>{item.uid}\n"
            f"<b>🏬 Ish beruvchi: </b>{item.company}\n"
            f"<b>💼 Lavozim: </b>{item.title}\n"
            f"<b>💰 Maosh: </b>{item.salary_text}\n"
            f"<b>📍 Hudud: </b>{item.location or 'N/A'} {('- ' + item.district) if item.district else ''}\n"
            f"<b>⏰ Sana: </b>{item.posted_at}\n"
            "------------------------------------\n"
        )
        ids.append(item.uid)
        num += 1

    total_est = len(vacancies) * max(last_page, page)
    texts = f"<b>NATIJALAR</b>: {total_est} ta | {from_num}-{num - 1}\n\n" + texts
    return texts, ids, page, from_num, last_page


async def vacancie_btn(ids: list[str], current_page: int, from_num: int):
    """Vakansiya tugmalari"""
    buttons = []

    row = []
    for num, vacancy_uid in enumerate(ids, start=from_num):
        row.append(
            InlineKeyboardButton(
                text=str(num),
                callback_data=f"{vacancy_uid}:{current_page}",
            )
        )
    buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(text="⬅", callback_data=f"⬅{current_page}"),
            InlineKeyboardButton(text="❌", callback_data="❌"),
            InlineKeyboardButton(text="➡", callback_data=f"➡{current_page}"),
        ]
    )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def region_btn(user_id: int):
    """Viloyatlar tugmalari"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT name_uz FROM regions ORDER BY CAST(soato AS INTEGER)"
        )
        regions = await cursor.fetchall()

    buttons = [[InlineKeyboardButton(text="Barchasi", callback_data="reg:Barchasi")]]

    row = []
    for (name_uz,) in regions:
        row.append(InlineKeyboardButton(text=name_uz, callback_data=f"reg:{name_uz}"))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def district_btn(user_id: int):
    """Tumanlar tugmalari"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT region FROM users WHERE user_id = ?",
            (user_id,),
        )
        result = await cursor.fetchone()

        if not result or not result[0]:
            return InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Avval viloyat tanlang", callback_data="error")]
                ]
            )

        cursor = await conn.execute(
            "SELECT soato FROM regions WHERE name_uz = ?",
            (result[0],),
        )
        region_row = await cursor.fetchone()

        if not region_row:
            return InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Viloyat topilmadi", callback_data="error")]
                ]
            )

        cursor = await conn.execute(
            "SELECT name_uz FROM districts WHERE region_soato = ? ORDER BY name_uz",
            (region_row[0],),
        )
        districts = await cursor.fetchall()

    buttons = [[InlineKeyboardButton(text="Barchasi.", callback_data="dist:Barchasi.")]]

    row = []
    for (name_uz,) in districts:
        if name_uz:
            row.append(InlineKeyboardButton(text=name_uz, callback_data=f"dist:{name_uz}"))
            if len(row) == 2:
                buttons.append(row)
                row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def money_btn(user_id: int):
    """Maosh tugmalari"""
    options = [
        ("❌ Ahamiyatsiz", "0"),
        ("2 mln ➕", "2000000"),
        ("3 mln ➕", "3000000"),
        ("4 mln ➕", "4000000"),
        ("5 mln ➕", "5000000"),
    ]

    buttons = []
    row = []
    for text, value in options:
        row.append(InlineKeyboardButton(text=text, callback_data=value))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def special_btn(user_id: int):
    """Soha tugmalari"""
    specs = [
        ("Sog'liqni saqlash", "spec:47"),
        ("Qurilish", "spec:41"),
        ("Savdo", "spec:64"),
        ("Qishloq xo'jaligi", "spec:7"),
        ("Arxitektura", "spec:41"),
        ("IT", "spec:12"),
        ("Ta'lim", "spec:42"),
        ("Haydovchilik", "spec:36"),
        ("Moliya", "spec:1"),
        ("Sanoat", "spec:21"),
        ("Xizmatlar", "spec:48"),
    ]

    buttons = []
    row = []
    for name, code in specs:
        row.append(InlineKeyboardButton(text=name, callback_data=code))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_detail(source: str, data: dict[str, Any]) -> str:
    if source == "ishapi":
        return (
            f"<b>🏬 Ish beruvchi:</b> {data.get('company_name', 'N/A')}\n"
            f"<b>💼 Lavozim:</b> {data.get('position_name', 'N/A')}\n"
            f"<b>📋 Stavka:</b> {data.get('position_rate', 'N/A')}\n"
            f"<b>🛠 Vazifalar:</b> {data.get('position_duties', 'N/A')}\n"
            f"<b>🎓 Talab:</b> {data.get('position_requirements', 'N/A')}\n"
            f"<b>⏰ Vaqt:</b> {data.get('position_conditions', 'N/A')}\n"
            f"<b>💰 Maosh:</b> {data.get('position_salary', 'N/A')}\n"
            f"<b>🗺 Manzil:</b> {data.get('region', {}).get('name_uz_ln', '')}, "
            f"{data.get('district', {}).get('name_uz_ln', '')}\n"
            f"<b>📞 Tel:</b> {', '.join(data.get('phones', []))}\n"
            f"<b>⏰ Sana:</b> {data.get('date_start', 'N/A')}\n"
            f"<b>🔗 Manba:</b> ishapi\n"
        )

    company_name = "N/A"
    company_obj = data.get("company")
    if isinstance(company_obj, dict):
        company_name = company_obj.get("name") or "N/A"

    min_salary = data.get("min_salary") if isinstance(data.get("min_salary"), int) else None
    max_salary = data.get("max_salary") if isinstance(data.get("max_salary"), int) else None
    if min_salary and max_salary:
        salary_text = f"{min_salary:,} – {max_salary:,} so'm".replace(",", " ")
    elif min_salary:
        salary_text = f"{min_salary:,} so'mdan".replace(",", " ")
    else:
        salary_text = "Kelishiladi"

    district_obj = data.get("soato_district") if isinstance(data.get("soato_district"), dict) else {}
    district = district_obj.get("name_uz") or ""
    address = data.get("address") or ""
    info = data.get("info") or ""
    info_text = _strip_html(info) if isinstance(info, str) else "N/A"

    hr_phone = ""
    hr_obj = data.get("hr")
    if isinstance(hr_obj, dict):
        hr_phone = hr_obj.get("phone") or ""

    return (
        f"<b>🏬 Ish beruvchi:</b> {company_name}\n"
        f"<b>💼 Lavozim:</b> {data.get('title', 'N/A')}\n"
        f"<b>💰 Maosh:</b> {salary_text}\n"
        f"<b>🗺 Tuman:</b> {district or 'N/A'}\n"
        f"<b>📍 Manzil:</b> {address or 'N/A'}\n"
        f"<b>📞 HR Tel:</b> {hr_phone or 'N/A'}\n"
        f"<b>⏰ Sana:</b> {data.get('created_at', 'N/A')}\n"
        f"<b>ℹ️ Batafsil:</b>\n{info_text[:1200]}\n"
        f"<b>🔗 Manba:</b> osonish\n"
    )


async def saves_info(uid: str) -> dict[str, Any] | None:
    cache_key = make_cache_key("detail", uid=uid)
    cached = await cache_get(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("source"), str):
        return cached

    try:
        raw_id = int(str(uid).replace("osonish_", "").replace("ishapi_", ""))
    except Exception:
        logger.warning("saves_info: uid format xato: %s", uid)
        return None

    # ishapi disabled (geo-blocked)
    # if str(uid).startswith("ishapi_"):
    #     data = await fetch_ishapi_detail(raw_id)
    # else:
    data = await fetch_osonish_detail(raw_id)

    if not isinstance(data, dict):
        return None

    result = {"source": "osonish", "data": data}
    await cache_set(cache_key, result, ttl=3600)
    return result
