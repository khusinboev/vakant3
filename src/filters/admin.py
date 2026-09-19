# ============================================================
# src/filters/admin.py
# Admin tekshiruvi — har bir handler ichida takrorlash o'rniga router filtri.
# ============================================================
from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

import config


class IsAdmin(BaseFilter):
    """Faqat ADMIN_IDS ichidagi foydalanuvchilarni o'tkazadi."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in config.ADMIN_IDS)
