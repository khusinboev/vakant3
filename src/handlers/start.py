# ============================================
# src/handlers/start.py - Aiogram 3.x
# ============================================
import aiosqlite
import time
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonWebApp, WebAppInfo
from config import BASE_DIR, bot, ADMIN_IDS, WEBAPP_URL
from src.buttons.buttuns import MM_btn
from src.functions.functions import functions
from src.functions.vacancy_format import format_vacancy_message_html
from src.functions.scraping import fetch_osonish_detail

router = Router()


def get_webapp_url() -> str:
    """WEBAPP_URL ni majburiy HTTPS ga o'girib /app path bilan qaytaradi."""
    base = WEBAPP_URL.rstrip("/")
    if base.startswith("http://"):
        base = f"https://{base[len('http://'):]}"
    if not base.startswith("https://"):
        base = f"https://{base}"
    return f"{base}/app"


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
            await conn.execute(
                "INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, ?)",
                (user_id, now_ts, "uz"),
            )
            await conn.commit()

        webapp_url = get_webapp_url()
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

        # Chat input pastida doimiy WebApp tugmasi (persistent menu button)
        try:
            await bot.set_chat_menu_button(
                chat_id=user_id,
                menu_button=MenuButtonWebApp(
                    text="🔍 Ish qidirish",
                    web_app=WebAppInfo(url=webapp_url),
                ),
            )
        except Exception:
            pass
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

        # Chat input pastida doimiy WebApp tugmasi (persistent menu button)
        try:
            await bot.set_chat_menu_button(
                chat_id=call.from_user.id,
                menu_button=MenuButtonWebApp(
                    text="🔍 Ish qidirish",
                    web_app=WebAppInfo(url=get_webapp_url()),
                ),
            )
        except Exception:
            pass
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
