# ============================================
# config.py - Aiogram 3.x
# ============================================
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

logger = logging.getLogger(__name__)

_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()]

DEFAULT_DB_PATH = Path(__file__).resolve().parent / "src" / "database" / "database.sqlite3"
BASE_DIR = os.getenv("DB_PATH", str(DEFAULT_DB_PATH))

TOKEN = os.getenv("TOKEN", "")
if not TOKEN:
    raise RuntimeError("TOKEN topilmadi. .env faylga TOKEN= qo'shing.")

BOT_USERNAME = os.getenv("BOT_USERNAME", "bandlikuzbot")

# Mini App manzili. Prod .env da o'zgartirilmasa ham ishlashi uchun default prod URL.
WEBAPP_URL = (os.getenv("WEBAPP_URL") or "https://abitur24.uz/app").rstrip("/")

REDIS_URL = (os.getenv("REDIS_URL") or "").strip()


def build_fsm_storage() -> BaseStorage:
    """Redis FSM storage when REDIS_URL answers a PING, else in-memory.

    MemoryStorage loses every wizard state on restart and cannot be shared, so
    Redis is preferred; an unreachable Redis must never stop the bot.
    """
    if REDIS_URL:
        try:
            import redis  # sync client, only for the reachability probe
            from aiogram.fsm.storage.redis import RedisStorage

            probe = redis.Redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
            try:
                probe.ping()
            finally:
                probe.close()
            logger.info("FSM storage: redis (%s)", REDIS_URL)
            return RedisStorage.from_url(REDIS_URL)
        except Exception as exc:
            logger.warning("FSM storage: redis unavailable (%s), falling back to memory", exc)
    else:
        logger.info("FSM storage: in-memory (REDIS_URL not set)")
    return MemoryStorage()


bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=build_fsm_storage())
