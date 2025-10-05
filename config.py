# ============================================
# config.py - Aiogram 3.x
# ============================================
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from pathlib import Path

# Admin'lar
ADMIN_IDS = [1918760732, 619839487, 5246872049]

# Database
BASE_DIR = str(Path(__file__).resolve().parent) + "/src/database/database.sqlite3"

# Token
TOKEN = "7855267108:AAG1DRIP6cpfe5VDVWd1b2HGlb6WWFaCxDo "

# Bot va Dispatcher
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())