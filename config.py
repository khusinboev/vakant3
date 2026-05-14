# ============================================
# config.py - Aiogram 3.x
# ============================================
import os
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()]

BASE_DIR = str(Path(__file__).resolve().parent / "src" / "database" / "database.sqlite3")

TOKEN = os.getenv("TOKEN", "")
if not TOKEN:
    raise RuntimeError("TOKEN topilmadi. .env faylga TOKEN= qo'shing.")

BOT_USERNAME = os.getenv("BOT_USERNAME", "bandlikuzbot")

WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:5174")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
