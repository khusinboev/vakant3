# ============================================
# functions.py - XAVFSIZ VERSIYA
# ============================================
import aiosqlite
from aiogram import types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import BASE_DIR, dp


class functions:
    @staticmethod
    async def check_on_start(user_id):
        """Kanalga obuna tekshiruvi"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        error_code = 0
        for row in rows:
            try:
                r = await dp.bot.get_chat_member(chat_id=row[0], user_id=user_id)
                if r.status not in ['member', 'creator', 'administrator']:
                    error_code = 1
            except:
                error_code = 1

        return error_code == 0


class panel_func:
    @staticmethod
    async def channel_add(channel_id):
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
    async def channel_delete(channel_id):
        """Kanal o'chirish"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            await conn.execute(
                "DELETE FROM channels WHERE id = ?",
                (channel_id,)
            )
            await conn.commit()

    @staticmethod
    async def channel_list():
        """Kanallar ro'yxati"""
        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute("SELECT id FROM channels")
            rows = await cursor.fetchall()

        result = ''
        for row in rows:
            try:
                chat = await dp.bot.get_chat(chat_id=row[0])
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


async def join_inline_btn(user_id):
    """Kanalga obuna tugmalari"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT id FROM channels")
        rows = await cursor.fetchall()

    join_inline = InlineKeyboardMarkup(row_width=1)
    for idx, row in enumerate(rows, 1):
        try:
            chat = await dp.bot.get_chat(chat_id=row[0])
            url = chat.invite_link
            if url:
                join_inline.add(InlineKeyboardButton(f"{idx} - kanal", url=url))
        except:
            pass

    join_inline.add(InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="check"))
    return join_inline


async def search_vakant(user_id, page):
    """Vakansiya qidirish - XAVFSIZ"""
    from src.functions.scraping import get_site_content

    async with aiosqlite.connect(BASE_DIR) as conn:
        # ✅ SQL Injection'dan himoyalangan
        cursor = await conn.execute(
            "SELECT region, district, specs, money FROM users WHERE user_id = ?",
            (user_id,)
        )
        user_data = await cursor.fetchone()

    if not user_data:
        return ("Foydalanuvchi topilmadi", [], 0, 0, 0)

    region, district, specs, money = user_data

    # Region/district ID'larini olish
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

    # API URL tuzish
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
                f"<b>👔 Lavozim: </b>{item['position_name']}\n"
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


async def vacancie_btn(ids, current_page, from_num):
    """Vakansiya tugmalari"""
    keyboard = InlineKeyboardMarkup(row_width=5)

    for num, vacancy_id in enumerate(ids, start=from_num):
        keyboard.insert(
            InlineKeyboardButton(
                str(num),
                callback_data=f"{vacancy_id}:{current_page}"
            )
        )

    keyboard.row(
        InlineKeyboardButton("⬅", callback_data=f"⬅{current_page}"),
        InlineKeyboardButton("❌", callback_data="❌"),
        InlineKeyboardButton("➡", callback_data=f"➡{current_page}")
    )

    return keyboard


async def region_btn(user_id):
    """Viloyatlar tugmalari"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT nom FROM viloyatlar ORDER BY my_num"
        )
        regions = await cursor.fetchall()

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Barchasi", callback_data="Barchasi"))

    for region in regions:
        keyboard.insert(InlineKeyboardButton(region[0], callback_data=region[0]))

    return keyboard


async def district_btn(user_id):
    """Tumanlar tugmalari"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT region FROM users WHERE user_id = ?",
            (user_id,)
        )
        result = await cursor.fetchone()

        if not result or not result[0]:
            return InlineKeyboardMarkup().add(
                InlineKeyboardButton("❌ Avval viloyat tanlang", callback_data="error")
            )

        cursor = await conn.execute(
            "SELECT districts FROM locations WHERE regions = ?",
            (result[0],)
        )
        districts = await cursor.fetchall()

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(InlineKeyboardButton("Barchasi.", callback_data="Barchasi."))

    for district in districts:
        if district[0]:
            keyboard.insert(InlineKeyboardButton(district[0], callback_data=district[0]))

    return keyboard


async def money_btn(user_id):
    """Maosh tugmalari"""
    options = [
        ('❌ Ahamiyatsiz', '0'),
        ('2 mln ➕', '2000000'),
        ('3 mln ➕', '3000000'),
        ('4 mln ➕', '4000000'),
        ('5 mln ➕', '5000000')
    ]

    keyboard = InlineKeyboardMarkup(row_width=2)
    for text, value in options:
        keyboard.insert(InlineKeyboardButton(text, callback_data=value))

    return keyboard


async def special_btn(user_id):
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

    keyboard = InlineKeyboardMarkup(row_width=2)
    for name, code in specs:
        keyboard.insert(InlineKeyboardButton(name, callback_data=code))

    return keyboard


async def saves_info(vacancy_id):
    """Vakansiya to'liq ma'lumoti"""
    from src.functions.scraping import get_site_content

    url = f'https://ishapi.mehnat.uz/api/v1/vacancies/{vacancy_id}'
    soup = await get_site_content(url)

    if not soup or not soup.get("success"):
        return "Vakansiya topilmadi"

    data = soup['data']
    status = "Faol" if data.get("active") else "Band"

    return (
        f"<b>🏬 Ish beruvchi:</b> {data.get('company_name', 'N/A')}\n"
        f"<b>👔 Lavozim:</b> {data.get('position_name', 'N/A')}\n"
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


async def forward_send_msg(chat_id: int, from_chat_id: int, message_id: int) -> int:
    """Xabar forward qilish"""
    try:
        await dp.bot.forward_message(chat_id, from_chat_id, message_id)
        return 1
    except:
        return 0


async def send_message_chats(chat_id: int, from_chat_id: int, message_id: int) -> int:
    """Xabar nusxalash"""
    try:
        await dp.bot.copy_message(chat_id, from_chat_id, message_id)
        return 1
    except:
        return 0