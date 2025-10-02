import sqlite3
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from pathlib import Path

# from src.middleware.middlewares import StatsMiddleware

storage = MemoryStorage()

adminStart = 1918760732
adminPanel = [1918760732, 619839487, 5246872049]

BASE_DIR = str(Path(__file__).resolve().parent)+"/src/database/database.sqlite3"

TOKEN = "7855267108:AAFVmpmPaL58OF06mlnozB0YdHQDh-cs_r8"
bot = Bot(token=TOKEN, parse_mode='html')
dp = Dispatcher(bot=bot, storage=storage)
# dp.middleware.setup(StatsMiddleware())


db = sqlite3.connect(BASE_DIR)
sql = db.cursor()
