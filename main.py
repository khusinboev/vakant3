# ============================================
# main.py - Aiogram 3.x
# ============================================
import asyncio
import logging
from config import dp, bot, BASE_DIR
from src.functions.auto_post_scheduler import auto_post_loop
from src.middleware.middlewares import StatsMiddleware
from src.handlers import start, admin, search

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Middleware
stats_middleware = StatsMiddleware(BASE_DIR)
dp.message.middleware(stats_middleware)


async def main():
    """Bot ishga tushirish"""
    # Database init
    await stats_middleware.init_db()
    print("✅ Database initialized")

    # Routerlarni ulash
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(search.router)

    print("✅ Bot started successfully")
    print("🤖 Polling started...")

    # Background scheduler: sends high-salary jobs to configured channel at random daily times.
    scheduler_task = asyncio.create_task(auto_post_loop())

    # Polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Bot to'xtatildi")