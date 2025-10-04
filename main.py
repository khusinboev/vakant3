# ============================================
# main.py - XAVFSIZ HANDLERLAR
# ============================================
import asyncio
import aiosqlite
from aiogram import executor, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from config import dp, BASE_DIR
from src.functions.functions import (
    functions, panel_func, join_inline_btn, search_vakant,
    vacancie_btn, region_btn, district_btn, money_btn,
    special_btn, saves_info
)
from src.functions.scraping import get_site_content

# Main menu tugmalari
MM_btn = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
MM_btn.add("💼 Ish qidirish", "🛠 Filtrni boshqarish")
MM_btn.add("🗂 Saqlangan ishlar")


# ============================================
# ISH QIDIRISH
# ============================================
@dp.message_handler(text="💼 Ish qidirish")
async def search_handler(message: Message):
    user_id = message.from_user.id

    if not await functions.check_on_start(user_id):
        await message.answer(
            "Botdan foydalanish uchun kanallarga obuna bo'ling",
            reply_markup=await join_inline_btn(user_id)
        )
        return

    send = await message.answer("⏳ Iltimos kuting, 🔎 ish qidirilmoqda...")

    try:
        texts, ids, current, from_num, last = await search_vakant(user_id, 1)

        if ids:
            await message.answer(
                text=texts,
                reply_markup=await vacancie_btn(ids, current, from_num)
            )
        else:
            await message.answer(texts)

    except Exception as e:
        await message.answer(f"Xatolik: {str(e)}")

    finally:
        try:
            await send.delete()
        except:
            pass


# ============================================
# FILTRLAR
# ============================================
@dp.message_handler(text="🛠 Filtrni boshqarish")
async def filter_handler(message: Message):
    await message.answer(
        "Kerakli sohani tanlang",
        reply_markup=await special_btn(message.from_user.id)
    )


# Soha tanlash
@dp.callback_query_handler(text=['22,322,323,324', '71', '91,522,523', '61', 
                                  '214', '213,312', '23,33', '83'])
async def specialty_handler(call: CallbackQuery):
    user_id = call.from_user.id
    spec_code = call.data

    async with aiosqlite.connect(BASE_DIR) as conn:
        await conn.execute(
            "UPDATE users SET specs = ? WHERE user_id = ?",
            (spec_code, user_id)
        )
        await conn.commit()

    try:
        await call.message.delete()
    except:
        pass

    await call.answer("Saqlandi")
    await call.message.answer(
        "Viloyatni tanlang",
        reply_markup=await region_btn(user_id)
    )


# Viloyat tanlash
REGIONS = ['Barchasi', 'Andijon viloyati', 'Buxoro viloyati', 'Jizzax viloyati',
           'Qashqadaryo viloyati', 'Navoiy viloyati', 'Namangan viloyati',
           'Samarqand viloyati', 'Surxondaryo viloyati', 'Sirdaryo viloyati',
           'Toshkent shahri', 'Toshkent viloyati', "Farg'ona viloyati",
           'Xorazm viloyati', "Qoraqalpog'iston Respublikasi"]


@dp.callback_query_handler(lambda c: c.data in REGIONS)
async def region_handler(call: CallbackQuery):
    user_id = call.from_user.id
    region = call.data

    async with aiosqlite.connect(BASE_DIR) as conn:
        if region == "Barchasi":
            await conn.execute(
                "UPDATE users SET region = NULL, district = NULL WHERE user_id = ?",
                (user_id,)
            )
        else:
            await conn.execute(
                "UPDATE users SET region = ?, district = NULL WHERE user_id = ?",
                (region, user_id)
            )
        await conn.commit()

    try:
        await call.message.delete()
    except:
        pass

    await call.answer("Saqlandi")

    if region == "Barchasi":
        await call.message.answer(
            "Maosh saralashini tanlang",
            reply_markup=await money_btn(user_id)
        )
    else:
        await call.message.answer(
            "Tumanni tanlang",
            reply_markup=await district_btn(user_id)
        )


# Tuman tanlash (500+ variant bo'lgani uchun lambda ishlatamiz)
@dp.callback_query_handler(lambda c: c.data.startswith('Barchasi.') or 
                           'tumani' in c.data.lower())
async def district_handler(call: CallbackQuery):
    user_id = call.from_user.id
    district = call.data

    async with aiosqlite.connect(BASE_DIR) as conn:
        if district == "Barchasi.":
            await conn.execute(
                "UPDATE users SET district = NULL WHERE user_id = ?",
                (user_id,)
            )
        else:
            await conn.execute(
                "UPDATE users SET district = ? WHERE user_id = ?",
                (district, user_id)
            )
        await conn.commit()

    try:
        await call.message.delete()
    except:
        pass

    await call.answer("Saqlandi")
    await call.message.answer(
        "Maosh saralashini tanlang",
        reply_markup=await money_btn(user_id)
    )


# Maosh tanlash
@dp.callback_query_handler(lambda c: c.data in ['0', '2000000', '3000000', 
                                                  '4000000', '5000000'])
async def money_handler(call: CallbackQuery):
    user_id = call.from_user.id
    money = None if call.data == '0' else int(call.data)

    async with aiosqlite.connect(BASE_DIR) as conn:
        await conn.execute(
            "UPDATE users SET money = ? WHERE user_id = ?",
            (money, user_id)
        )
        await conn.commit()

    try:
        await call.message.delete()
    except:
        pass

    await call.answer("Saqlandi")
    await call.message.answer(
        "✅ Filtrlash yakunlandi!\n'💼 Ish qidirish' tugmasini bosing",
        reply_markup=MM_btn
    )


# ============================================
# SAQLANGAN ISHLAR
# ============================================
@dp.message_handler(text="🗂 Saqlangan ishlar")
async def saved_jobs_handler(message: Message):
    user_id = message.from_user.id

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT save_id FROM saves WHERE user_id = ?",
            (user_id,)
        )
        saves = await cursor.fetchall()

    if not saves:
        await message.answer("Saqlangan ishlar yo'q")
        return

    delete_btn = InlineKeyboardMarkup().add(
        InlineKeyboardButton("🗑 Hammasini o'chirish", callback_data="delete_all")
    )

    for save_id, in saves:
        if save_id:
            text = await saves_info(save_id)
            await message.answer(text, reply_markup=delete_btn)


@dp.callback_query_handler(text="delete_all")
async def delete_saved(call: CallbackQuery):
    user_id = call.from_user.id

    async with aiosqlite.connect(BASE_DIR) as conn:
        await conn.execute(
            "DELETE FROM saves WHERE user_id = ?",
            (user_id,)
        )
        await conn.commit()

    try:
        await call.message.delete()
    except:
        pass

    await call.answer("Hammasi o'chirildi")


# ============================================
# NAVIGATSIYA (⬅, ❌, ➡)
# ============================================
@dp.callback_query_handler(lambda c: c.data.startswith(("⬅", "❌", "➡", "🔙", "🗂")))
async def navigation_handler(call: CallbackQuery):
    user_id = call.from_user.id
    data = call.data

    if data.startswith("⬅"):
        page = int(data[1:]) - 1
        if page <= 0:
            await call.answer("Birinchi sahifa")
            return

        texts, ids, current, from_num, last = await search_vakant(user_id, page)
        try:
            await call.message.edit_text(texts)
            await call.message.edit_reply_markup(
                await vacancie_btn(ids, current, from_num)
            )
        except:
            pass

    elif data == "❌":
        await call.answer("Yopildi")
        try:
            await call.message.delete()
        except:
            pass

    elif data.startswith("➡"):
        page = int(data[1:]) + 1
        texts, ids, current, from_num, last = await search_vakant(user_id, page)

        if current > last:
            await call.answer("Oxirgi sahifa")
            return

        try:
            await call.message.edit_text(texts)
            await call.message.edit_reply_markup(
                await vacancie_btn(ids, current, from_num)
            )
        except:
            pass

    elif data.startswith("🔙"):
        page = int(data[1:])
        texts, ids, current, from_num, last = await search_vakant(user_id, page)
        try:
            await call.message.edit_text(texts)
            await call.message.edit_reply_markup(
                await vacancie_btn(ids, current, from_num)
            )
        except:
            pass

    elif data.startswith("🗂"):
        vacancy_id = int(data[1:])

        async with aiosqlite.connect(BASE_DIR) as conn:
            cursor = await conn.execute(
                "SELECT save_id FROM saves WHERE user_id = ? AND save_id = ?",
                (user_id, vacancy_id)
            )
            exists = await cursor.fetchone()

            if exists:
                await call.answer("Allaqachon saqlangan")
            else:
                await conn.execute(
                    "INSERT INTO saves (user_id, save_id) VALUES (?, ?)",
                    (user_id, vacancy_id)
                )
                await conn.commit()
                await call.answer("✅ Saqlandi")


# ============================================
# VAKANSIYA TAFSILOTLARI
# ============================================
@dp.callback_query_handler(lambda c: ':' in c.data)
async def vacancy_detail_handler(call: CallbackQuery):
    try:
        vacancy_id, page = call.data.split(':')
        vacancy_id = int(vacancy_id)
        page = int(page)
    except:
        await call.answer("Xato format")
        return

    try:
        await call.message.delete()
    except:
        pass

    text = await saves_info(vacancy_id)

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📌 Saqlash", callback_data=f"🗂{vacancy_id}"),
        InlineKeyboardButton("⬅ Orqaga", callback_data=f"🔙{page}")
    )

    await call.message.answer(text, reply_markup=keyboard)


# ============================================
# KANAL OBUNA TEKSHIRUVI
# ============================================
@dp.callback_query_handler(text="check")
async def check_subscription(call: CallbackQuery):
    user_id = call.from_user.id

    if await functions.check_on_start(user_id):
        await call.answer("✅ Tasdiqlandi")
        try:
            await call.message.delete()
        except:
            pass
        await call.message.answer(
            "Xush kelibsiz! Botdan foydalanishingiz mumkin",
            reply_markup=MM_btn
        )
    else:
        await call.answer("❌ Barcha kanallarga obuna bo'ling!", show_alert=True)


# ============================================
# STARTUP
# ============================================
async def on_startup(dp):
    """Bot ishga tushganda"""
    from src.middleware.middlewares import StatsMiddleware

    middleware = StatsMiddleware(BASE_DIR)
    await middleware.init_db()
    print("✅ Database initialized")
    print("✅ Bot started successfully")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)