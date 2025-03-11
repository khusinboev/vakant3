import datetime
from src.functions.functions import *
from src.buttons.buttuns import *
import pytz
from config import sql, db


@dp.message_handler(commands='start')
async def welcome(message: types.Message):
    sql.execute("SELECT id FROM channels")
    rows = sql.fetchall()
    join_inline = types.InlineKeyboardMarkup(row_width=1)
    title = 1
    for row in rows:
        all_details = await dp.bot.get_chat(chat_id=row[0])
        url = all_details['invite_link']
        join_inline.insert(InlineKeyboardButton(f"{title} - kanal", url=url))
        title += 1
    join_inline.add(InlineKeyboardButton("✅Obuna bo'ldim", callback_data="check"))
    if await functions.check_on_start(message.chat.id):
        await message.answer(f"""Assalomu alaykum, botimizga xush kelibsiz. Kerakli bo‘limni tanlang!""", reply_markup=MM_btn)
    else:
        await message.answer("Botimizdan foydalanish uchun kanalimizga azo bo'ling", reply_markup=join_inline)

@dp.callback_query_handler(text="check")
async def check(call: CallbackQuery):
    user_id = call.from_user.id
    if await functions.check_on_start(user_id):
        await call.answer()
        await call.message.delete()
        await call.message.answer("Assalomu alaykum, botimizga xush kelibsiz. Kerakli bo‘limni tanlang!", reply_markup=MM_btn)
    else:
        await call.answer(show_alert=True, text="Botimizdan foydalanish uchun kanalimizga azo bo'ling")
