# ============================================
# src/handlers/admin.py - Aiogram 3.x (1-qism)
# ============================================
import aiosqlite
import pytz
import datetime
import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, ContentType
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest
from config import BASE_DIR, bot, ADMIN_IDS
from src.buttons.buttuns import main_btn, channel_btn, reklama_btn, back_btn
from src.functions.functions import panel_func

logger = logging.getLogger(__name__)

router = Router()


class AdminStates(StatesGroup):
    channel_add = State()
    channel_delete = State()
    send_msg = State()
    forward_msg = State()


@router.message(Command("admin", "panel"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Assalomu alaykum admin", reply_markup=main_btn)


@router.message(F.text == "🔙Orqaga qaytish")
async def back_handler(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    await state.clear()
    await message.reply("Bosh menyu", reply_markup=main_btn)


@router.message(F.text == "📊Statistika")
async def statistics_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    tz_uzbekistan = pytz.timezone("Asia/Tashkent")
    now = datetime.datetime.now(tz_uzbekistan)

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        three_months_ago = now - datetime.timedelta(days=90)
        three_months_ago_ts = int(three_months_ago.timestamp())

        cursor = await conn.execute(
            "SELECT COUNT(*) FROM users WHERE date >= ?",
            (three_months_ago_ts,)
        )
        last_3_months_users = (await cursor.fetchone())[0]

        months_stats = {}
        for i in range(3):
            first_day = (now.replace(day=1) - datetime.timedelta(days=30 * i)).replace(day=1)
            last_day = (first_day + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(seconds=1)
            month_name = first_day.strftime("%B")

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM users WHERE date BETWEEN ? AND ?",
                (int(first_day.timestamp()), int(last_day.timestamp()))
            )
            months_stats[month_name] = (await cursor.fetchone())[0]

        last_7_days = {}
        for i in range(7):
            date = now - datetime.timedelta(days=i)
            date_str = date.strftime("%d-%m-%Y")

            start_ts = int(date.replace(hour=0, minute=0, second=0).timestamp())
            end_ts = int(date.replace(hour=23, minute=59, second=59).timestamp())

            cursor = await conn.execute(
                "SELECT COUNT(*) FROM users WHERE date BETWEEN ? AND ?",
                (start_ts, end_ts)
            )
            last_7_days[date_str] = (await cursor.fetchone())[0]

    stat_text = f"""📊 **Foydalanuvchilar statistikasi** 📊

Jami: {total_users} ta
So'nggi 3 oy (Jami: {last_3_months_users} ta):
""" + "\n".join([f"🔹 {month}: {count} ta" for month, count in months_stats.items()]) + f"""

So'nggi 7 kun ({sum(last_7_days.values())} ta):
""" + "\n".join([f"🔹 {date}: {count} ta" for date, count in last_7_days.items()])

    await message.answer(stat_text)


@router.message(F.text == '🔧Kanallar')
async def channels_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("Tanlang", reply_markup=channel_btn)


@router.message(F.text == "➕Kanal qo'shish")
async def channel_add_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.reply(
        "Kanal qo'shish uchun kanalning userini yuboring.\n"
        "Misol: @coder_admin",
        reply_markup=back_btn
    )
    await state.set_state(AdminStates.channel_add)


@router.message(AdminStates.channel_add)
async def channel_add_process(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    if message.text == "🔙Orqaga qaytish":
        await state.clear()
        await message.reply("Bekor qilindi", reply_markup=main_btn)
        return

    channel_username = message.text.strip().upper()

    if not channel_username.startswith('@'):
        await message.reply(
            "Kanal useri xato! @coder_admin formatida kiriting",
            reply_markup=channel_btn
        )
        await state.clear()
        return

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT id FROM channels WHERE id = ?",
            (channel_username,)
        )
        exists = await cursor.fetchone()

    if exists:
        await message.reply("Bu kanal allaqachon qo'shilgan", reply_markup=channel_btn)
    else:
        await panel_func.channel_add(channel_username)
        await message.reply("Kanal qo'shildi 🎉", reply_markup=channel_btn)

    await state.clear()


@router.message(F.text == "❌Kanalni olib tashlash")
async def channel_delete_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.reply(
        "O'chiriladigan kanalning userini yuboring.\n"
        "Misol: @coder_admin",
        reply_markup=back_btn
    )
    await state.set_state(AdminStates.channel_delete)


@router.message(AdminStates.channel_delete)
async def channel_delete_process(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    if message.text == "🔙Orqaga qaytish":
        await state.clear()
        await message.reply("Bekor qilindi", reply_markup=main_btn)
        return

    channel_username = message.text.strip().upper()

    if not channel_username.startswith('@'):
        await message.reply(
            "Kanal useri xato! @coder_admin formatida kiriting",
            reply_markup=channel_btn
        )
        await state.clear()
        return

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute(
            "SELECT id FROM channels WHERE id = ?",
            (channel_username,)
        )
        exists = await cursor.fetchone()

    if not exists:
        await message.reply("Bunday kanal yo'q", reply_markup=channel_btn)
    else:
        await panel_func.channel_delete(channel_username)
        await message.reply("Kanal o'chirildi", reply_markup=channel_btn)

    await state.clear()


@router.message(F.text == "📋 Kanallar ro'yxati")
async def channel_list_handler(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    channels_info = await panel_func.channel_list(bot)

    if len(channels_info) > 3:
        await message.reply(channels_info)
    else:
        await message.reply("Hozircha kanallar yo'q")


@router.message(F.text == "📤Reklama")
async def broadcast_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.reply(
        "Foydalanuvchilarga xabar yuborish bo'limi",
        reply_markup=reklama_btn
    )


@router.message(F.text == "📨Forward xabar yuborish")
async def forward_broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Forward yuboriladigan xabarni yuboring",
        reply_markup=back_btn
    )
    await state.set_state(AdminStates.forward_msg)


@router.message(AdminStates.forward_msg)
async def forward_broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    if message.text == "🔙Orqaga qaytish":
        await state.clear()
        await message.reply("Bekor qilindi", reply_markup=main_btn)
        return

    await state.clear()

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()

    success_count = 0
    failed_count = 0

    status_msg = await message.answer(f"Yuborilmoqda... 0/{len(users)}")

    for idx, (user_id,) in enumerate(users, 1):
        try:
            await bot.forward_message(user_id, message.chat.id, message.message_id)
            success_count += 1
        except TelegramRetryAfter as e:
            logger.warning("Broadcast forward: flood wait %ss", e.retry_after)
            await asyncio.sleep(e.retry_after)
            failed_count += 1
        except TelegramForbiddenError:
            failed_count += 1
        except Exception as e:
            logger.error("Broadcast forward: user_id=%s xato: %s", user_id, e)
            failed_count += 1

        if idx % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"Yuborilmoqda... {idx}/{len(users)}\n"
                    f"✅ Muvaffaqiyatli: {success_count}\n"
                    f"❌ Xato: {failed_count}"
                )
            except TelegramBadRequest:
                pass

        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Yuborish yakunlandi!\n\n"
        f"📊 Jami: {len(users)} ta\n"
        f"✅ Yuborildi: {success_count} ta\n"
        f"❌ Yuborilmadi: {failed_count} ta"
    )


@router.message(F.text == "📬Oddiy xabar yuborish")
async def copy_broadcast_start(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    await message.answer(
        "Yuborilishi kerak bo'lgan xabarni yuboring",
        reply_markup=back_btn
    )
    await state.set_state(AdminStates.send_msg)


@router.message(AdminStates.send_msg)
async def copy_broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    if message.text == "🔙Orqaga qaytish":
        await state.clear()
        await message.reply("Bekor qilindi", reply_markup=main_btn)
        return

    await state.clear()

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT user_id FROM users")
        users = await cursor.fetchall()

    success_count = 0
    failed_count = 0

    status_msg = await message.answer(f"Yuborilmoqda... 0/{len(users)}")

    for idx, (user_id,) in enumerate(users, 1):
        try:
            await bot.copy_message(user_id, message.chat.id, message.message_id)
            success_count += 1
        except TelegramRetryAfter as e:
            logger.warning("Broadcast copy: flood wait %ss", e.retry_after)
            await asyncio.sleep(e.retry_after)
            failed_count += 1
        except TelegramForbiddenError:
            failed_count += 1
        except Exception as e:
            logger.error("Broadcast copy: user_id=%s xato: %s", user_id, e)
            failed_count += 1

        if idx % 50 == 0:
            try:
                await status_msg.edit_text(
                    f"Yuborilmoqda... {idx}/{len(users)}\n"
                    f"✅ Muvaffaqiyatli: {success_count}\n"
                    f"❌ Xato: {failed_count}"
                )
            except TelegramBadRequest:
                pass

        await asyncio.sleep(0.05)

    await status_msg.edit_text(
        f"✅ Yuborish yakunlandi!\n\n"
        f"📊 Jami: {len(users)} ta\n"
        f"✅ Yuborildi: {success_count} ta\n"
        f"❌ Yuborilmadi: {failed_count} ta"
    )