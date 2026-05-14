# ============================================
# src/handlers/start.py - Aiogram 3.x
# ============================================
import aiosqlite
import secrets
import time
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from config import BASE_DIR, bot, ADMIN_IDS, WEBAPP_URL
from src.buttons.buttuns import MM_btn
from src.functions.functions import functions
from src.functions.vacancy_format import format_vacancy_message_html
from src.functions.scraping import fetch_osonish_detail

router = Router()


@router.message(CommandStart())
async def welcome(message: Message):
    """Start handler"""
    user_id = message.from_user.id

    args = (message.text or "").split()
    start_param = args[1] if len(args) > 1 else ""

    # ── Vacancy deeplink: /start vacancy_osonish_12345 ──────────────────
    if start_param.startswith("vacancy_osonish_"):
        uid = start_param[len("vacancy_"):]   # "osonish_12345"
        try:
            raw_id = int(uid.split("_", 1)[1])
        except (IndexError, ValueError):
            await message.answer("❌ Noto'g'ri vakansiya havolasi.")
            return

        await message.answer("⏳ Vakansiya ma'lumotlari yuklanmoqda...")
        detail = await fetch_osonish_detail(raw_id)
        if not isinstance(detail, dict):
            await message.answer("❌ Vakansiya topilmadi yoki ma'lumot olishda xato.")
            return

        text = format_vacancy_message_html(uid, detail)
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)
        return
    # ────────────────────────────────────────────────────────────────────

    if start_param.startswith("ref_"):
        try:
            inviter_id = int(start_param[4:])
        except ValueError:
            inviter_id = 0

        if inviter_id and inviter_id != user_id:
            async with aiosqlite.connect(BASE_DIR) as conn:
                await conn.execute(
                    "UPDATE users SET ref_by = ? WHERE user_id = ? AND ref_by IS NULL",
                    (inviter_id, user_id),
                )
                await conn.commit()

    is_subscribed = await functions.check_on_start(user_id, bot)

    if is_subscribed:
        now_ts = int(time.time())
        async with aiosqlite.connect(BASE_DIR) as conn:
            # Ensure user row exists for handoff -> /auth/me profile hydration.
            await conn.execute(
                "INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, ?)",
                (user_id, now_ts, "uz"),
            )
            await conn.commit()

        # /start uchun userga alohida bir martalik handoff token
        handoff_token = secrets.token_urlsafe(32)
        expires_at = now_ts + 300  # 5 daqiqa
        async with aiosqlite.connect(BASE_DIR) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO bot_handoff_tokens (token, user_id, used, expires_at) VALUES (?, ?, 0, ?)",
                (handoff_token, user_id, expires_at),
            )
            await conn.commit()

        webapp_base = WEBAPP_URL.rstrip("/")
        if webapp_base.startswith("http://"):
            webapp_base = f"https://{webapp_base[len('http://'):]}"
        if not webapp_base.startswith("https://"):
            webapp_base = f"https://{webapp_base}"
        webapp_url = f"{webapp_base}/handoff?token={handoff_token}&uid={user_id}"
        open_webapp_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🌐 WebAppni ochish", web_app=WebAppInfo(url=webapp_url))]
            ]
        )

        await message.answer(
            f"Assalomu alaykum, {message.from_user.first_name}!\n"
            f"Botimizga xush kelibsiz. Kerakli bo'limni tanlang!",
            reply_markup=MM_btn,
        )

        await message.answer(
            "🌐 Veb ilovaga kirish uchun tugmani bosing:",
            reply_markup=open_webapp_kb,
        )
    else:
        join_keyboard = await build_channel_keyboard()

        if join_keyboard:
            await message.answer(
                "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                reply_markup=join_keyboard
            )
        else:
            await message.answer(
                f"Assalomu alaykum, {message.from_user.first_name}!\n"
                f"Botimizga xush kelibsiz. Kerakli bo'limni tanlang!",
                reply_markup=MM_btn
            )


async def build_channel_keyboard() -> InlineKeyboardMarkup:
    """Kanallar keyboard"""
    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT id FROM channels")
        channels = await cursor.fetchall()

    if not channels:
        return None

    buttons = []
    added_count = 0

    for idx, (channel_id,) in enumerate(channels, 1):
        try:
            chat = await bot.get_chat(chat_id=channel_id)
            invite_link = chat.invite_link

            if not invite_link:
                try:
                    invite_link = await bot.export_chat_invite_link(channel_id)
                except:
                    continue

            buttons.append([InlineKeyboardButton(
                text=f"{idx}. {chat.title or 'Kanal'}",
                url=invite_link
            )])
            added_count += 1
        except:
            continue

    if added_count == 0:
        return None

    buttons.append([InlineKeyboardButton(
        text="✅ Obuna bo'ldim",
        callback_data="check"
    )])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "check")
async def check_subscription(call: CallbackQuery):
    """Obuna tekshirish"""
    user_id = call.from_user.id
    is_subscribed = await functions.check_on_start(user_id, bot)

    if is_subscribed:
        await call.answer("✅ Tasdiqlandi!", show_alert=False)

        try:
            await call.message.delete()
        except:
            pass

        await call.message.answer(
            f"Xush kelibsiz, {call.from_user.first_name}!\n"
            f"Endi botdan to'liq foydalanishingiz mumkin.",
            reply_markup=MM_btn
        )
    else:
        await call.answer(
            "❌ Siz hali barcha kanallarga obuna bo'lmadingiz!\n"
            "Iltimos, barcha kanallarga obuna bo'ling.",
            show_alert=True
        )


@router.message(Command("check_channels"))
async def diagnose_channels(message: Message):
    """Kanallar diagnostikasi"""
    if message.from_user.id not in ADMIN_IDS:
        return

    async with aiosqlite.connect(BASE_DIR) as conn:
        cursor = await conn.execute("SELECT id FROM channels")
        channels = await cursor.fetchall()

    if not channels:
        await message.answer("❌ Bazada kanallar yo'q")
        return

    report = "📊 Kanallar holati:\n\n"

    for idx, (channel_id,) in enumerate(channels, 1):
        try:
            chat = await bot.get_chat(chat_id=channel_id)
            bot_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot.id)
            is_admin = bot_member.status in ['administrator', 'creator']

            report += f"{idx}. ✅ {chat.title}\n"
            report += f"   ID: {channel_id}\n"
            report += f"   Admin: {'Ha' if is_admin else 'Yo`q'}\n"
            report += f"   Link: {'Bor' if chat.invite_link else 'Yo`q'}\n\n"
        except Exception as e:
            report += f"{idx}. ❌ {channel_id}\n"
            report += f"   Xato: {str(e)[:50]}\n\n"

    await message.answer(report)


@router.message(Command("developer", "coder", "programmer"))
async def coder(message: Message):
    await message.reply(
        "Bot dasturchisi @coder_admin_py\n\nPowered by @coder_admin_py"
    )
