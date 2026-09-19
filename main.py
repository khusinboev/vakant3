# ============================================
# main.py - Aiogram 3.x
# ============================================
import asyncio
import logging

from config import BASE_DIR, bot, dp
from src.functions.auto_post_scheduler import auto_post_loop
from src.functions.notification_scheduler import notification_loop
from src.functions.weekly_stats_scheduler import weekly_stats_loop
from src.handlers import admin, content, start
from src.middleware.middlewares import StatsMiddleware

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Middleware — message va callback_query uchun (ikkalasi ham `lang` oladi)
stats_middleware = StatsMiddleware(BASE_DIR)
dp.message.middleware(stats_middleware)
dp.callback_query.middleware(stats_middleware)


def _log_task_result(name: str):
    def _callback(task: asyncio.Task) -> None:
        if task.cancelled():
            logger.info("%s to'xtatildi", name)
            return
        exc = task.exception()
        if exc is not None:
            logger.error("%s kutilmaganda tugadi: %r", name, exc)
        else:
            logger.warning("%s o'z-o'zidan tugadi", name)

    return _callback


def _start_task(coro_factory, name: str) -> asyncio.Task:
    task = asyncio.create_task(coro_factory(), name=name)
    task.add_done_callback(_log_task_result(name))
    return task


async def main():
    """Bot ishga tushirish"""
    # Database init
    await stats_middleware.init_db()
    logger.info("Database initialized")

    # Routerlarni ulash
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(content.router)

    logger.info("Bot started, polling...")

    # Fon vazifalari: har biri o'z ichida try/except bilan o'ralgan cheksiz sikl.
    tasks = [
        _start_task(auto_post_loop, "auto_post_loop"),
        _start_task(notification_loop, "notification_loop"),
        _start_task(weekly_stats_loop, "weekly_stats_loop"),
    ]

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Bot to'xtatildi")
