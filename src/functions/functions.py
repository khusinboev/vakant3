# ============================================
# src/functions/functions.py - Aiogram 3.x
# ============================================
import aiosqlite
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BASE_DIR


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
                if member.status not in ['member', 'creator', 'administrator']:
                    return False
            except:
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
                    (channel_id,)
                )
                await conn.commit()
            except:
                pass

    @staticmethod
    async def channel_delete(channel_id: str):
        """Kanal o'chirish"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            await conn.execute(
                "DELETE FROM channels WHERE id = ?",
                (channel_id,)
            )
            await conn.commit()

    @staticmethod
    async def channel_list(bot):
        """Kanallar ro'yxati"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        result = ''
        for row in rows:
            try:
                chat = await bot.get_chat(chat_id=row[0])
                result += (
                    f"------------------------------------------------\n"
                    f"Kanal useri: {row[0]}\n"
                    f"Kanal nomi: {chat.title}\n"
                    f"Kanal ID: {chat.id}\n"
                    f"Haqida: {chat.description or 'Mavjud emas'}\n"
                )
            except:
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
                buttons.append([InlineKeyboardButton(
                    text=f"{idx} - kanal",
                    url=url
                )])
        except:
            pass

    buttons.append([InlineKeyboardButton(
        text="✅ Obuna bo'ldim",
        callback_data="check"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def search_vakant(user_id: int, page: int):
    """Vakansiya qidirish"""
    from src.functions.scraping import get_site_content

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT region, district, specs, money FROM users WHERE user_id = ?",
            (user_id,)
        )
        user_data = await cursor.fetchone()

    if not user_data:
        return ("Foydalanuvchi topilmadi", [], 0, 0, 0)

    region, district, specs, money = user_data

    yurt = ''
    if region:
        async with aiosqlite.connect(BASE_DIR) as conn:
            if district:
                cursor = await conn.execute(
                    "SELECT dist_ids FROM locations WHERE districts = ?",
                    (district,)
                )
            else:
                cursor = await conn.execute(
                    "SELECT reg_ids FROM locations WHERE regions = ?",
                    (region,)
                )
            result = await cursor.fetchone()
            if result:
                yurt = result[0]

    url = (
        f'https://ishapi.mehnat.uz/api/v1/vacancies?'
        f'per_page=5&salary={money or ""}&'
        f'vacancy_soato_code={yurt}&sort_key=created_at&'
        f'nskz={specs or ""}&page={page}'
    )

    soup = await get_site_content(url)

    try:
        if not soup or 'data' not in soup:
            return ("Xatolik yuz berdi", [], 0, 0, 0)

        data = soup['data']['data']
        num = soup['data']['from'] or 1
        texts = ''
        ids = []

        for item in data:
            salary_str = item.get('position_salary') or "Mavjud emas"
            texts += (
                f"<b>👨‍💻 {num}- VAKANSIYA\n\n</b>"
                f"<b>🆔 ID: </b>{item['id']}\n"
                f"<b>🏬 Ish beruvchi: </b>{item['company_name']}\n"
                f"<b>💼 Lavozim: </b>{item['position_name']}\n"
                f"<b>💰 Maosh: </b>{salary_str} so'm\n"
                f"<b>⏰ Sana: </b>{item['date_start']}\n"
                f"------------------------------------\n"
            )
            num += 1
            ids.append(item['id'])

        total = soup['data']['total']
        from_page = soup['data']['from']
        to_page = soup['data']['to']
        current = soup['data']['current_page']
        last = soup['data']['last_page']

        texts = f"<b>NATIJALAR</b>: {total} ta | {from_page}-{to_page}\n\n" + texts

        return (texts, ids, current, from_page, last)

    except Exception as e:
        return (f"Xatolik: {str(e)}", [], 0, 0, 0)


async def vacancie_btn(ids: list, current_page: int, from_num: int):
    """Vakansiya tugmalari"""
    buttons = []

    # Raqamlar qatori
    row = []
    for num, vacancy_id in enumerate(ids, start=from_num):
        row.append(InlineKeyboardButton(
            text=str(num),
            callback_data=f"{vacancy_id}:{current_page}"
        ))
    buttons.append(row)

    # Navigatsiya
    buttons.append([
        InlineKeyboardButton(text="⬅", callback_data=f"⬅{current_page}"),
        InlineKeyboardButton(text="❌", callback_data="❌"),
        InlineKeyboardButton(text="➡", callback_data=f"➡{current_page}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def region_btn(user_id: int):
    """Viloyatlar tugmalari"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT nom FROM viloyatlar ORDER BY my_num")
        regions = await cursor.fetchall()

    buttons = [[InlineKeyboardButton(text="Barchasi", callback_data="Barchasi")]]

    row = []
    for idx, (region,) in enumerate(regions):
        row.append(InlineKeyboardButton(text=region, callback_data=region))
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
            (user_id,)
        )
        result = await cursor.fetchone()

        if not result or not result[0]:
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Avval viloyat tanlang", callback_data="error")]
            ])

        cursor = await conn.execute(
            "SELECT districts FROM locations WHERE regions = ?",
            (result[0],)
        )
        districts = await cursor.fetchall()

    buttons = [[InlineKeyboardButton(text="Barchasi.", callback_data="Barchasi.")]]

    row = []
    for district, in districts:
        if district:
            row.append(InlineKeyboardButton(text=district, callback_data=district))
            if len(row) == 2:
                buttons.append(row)
                row = []

    if row:
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def money_btn(user_id: int):
    """Maosh tugmalari"""
    options = [
        ('❌ Ahamiyatsiz', '0'),
        ('2 mln ➕', '2000000'),
        ('3 mln ➕', '3000000'),
        ('4 mln ➕', '4000000'),
        ('5 mln ➕', '5000000')
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
        ("Sog'liqni saqlash", '22,322,323,324'),
        ("Qurilish", '71'),
        ("Savdo", '91,522,523'),
        ("Qishloq xo'jaligi", '61'),
        ("Arxitektura", '214'),
        ("IT", '213,312'),
        ("Ta'lim", '23,33'),
        ("Haydovchilik", '83')
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


async def saves_info(vacancy_id: int):
    """Vakansiya to'liq ma'lumoti"""
    from src.functions.scraping import get_site_content

    url = f'https://ishapi.mehnat.uz/api/v1/vacancies/{vacancy_id}'
    soup = await get_site_content(url)

    if not soup or not soup.get("success"):
        return "Vakansiya topilmadi"

    data = soup['data']

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
        f"<b>⏰ Sana:</b> {data.get('date_start', 'N/A')}\n\n"
        f"<b>♻️ @mehnatuz_bot</b>"
    )
