"""
Testlar uchun umumiy sozlash.

`config` import vaqtida TOKEN bo'lmasa xato beradi — shuning uchun boshqa
har qanday import dan OLDIN standart qiymatlarni o'rnatamiz. Haqiqiy .env
mavjud bo'lsa, undagi qiymatlar ustun turadi (load_dotenv override qilmaydi,
lekin biz ham faqat setdefault ishlatamiz).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent

# .env bo'lsa — o'qiymiz; bo'lmasa test qiymatlari ishlaydi.
load_dotenv(_REPO_ROOT / ".env")

os.environ.setdefault("TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("BOT_USERNAME", "bandlikuzbot")
# Testlar hech qachon haqiqiy bazaga tegmasin.
os.environ.setdefault("DB_PATH", str(_REPO_ROOT / "src" / "database" / "database.sqlite3"))

import pytest  # noqa: E402


@pytest.fixture
def uz_lang() -> str:
    return "uz"
