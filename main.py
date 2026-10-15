# ============================================
# main.py - Aiogram 3.x
# ============================================
import asyncio
import logging

from config import ADMIN_IDS, BASE_DIR, WEBAPP_URL, bot, dp
from src.db.connection import connect
from src.db.migrate import run_migrations
from src.functions.auto_post_scheduler import auto_post_loop
from src.functions.bot_jobs import bot_jobs_loop
from src.functions.bot_setup import setup_bot_ui
from src.functions.broadcast_worker import broadcast_worker_loop
from src.functions.daily_rollup import daily_rollup_loop
from src.functions.notification_scheduler import notification_loop
from src.functions.weekly_stats_scheduler import weekly_stats_loop
from src.handlers import admin, content, membership, start
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


def include_routers(dispatcher) -> None:
    """Attach every handler router (membership first: it handles update types the others do not)."""
    dispatcher.include_router(membership.router)
    dispatcher.include_router(start.router)
    dispatcher.include_router(admin.router)
    dispatcher.include_router(content.router)


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
    async with connect() as conn:
        applied = await run_migrations(conn)
    if applied:
        logger.info("Migratsiyalar qo'llandi: %s", ", ".join(applied))
    logger.info("Database initialized")

    # Routerlarni ulash
    include_routers(dp)

    # Menu button + command lists; best effort, never fatal.
    try:
        await setup_bot_ui(bot, WEBAPP_URL, ADMIN_IDS)
    except Exception as exc:
        logger.warning("bot UI setup skipped: %s", exc)

    logger.info("Bot started, polling...")

    # Fon vazifalari: har biri o'z ichida try/except bilan o'ralgan cheksiz sikl.
    tasks = [
        _start_task(auto_post_loop, "auto_post_loop"),
        _start_task(notification_loop, "notification_loop"),
        _start_task(weekly_stats_loop, "weekly_stats_loop"),
        _start_task(broadcast_worker_loop, "broadcast_worker_loop"),
        _start_task(bot_jobs_loop, "bot_jobs_loop"),
        _start_task(daily_rollup_loop, "daily_rollup_loop"),
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
