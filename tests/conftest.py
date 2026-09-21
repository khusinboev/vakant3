"""
Testlar uchun umumiy sozlash.

`config` import vaqtida TOKEN bo'lmasa xato beradi — shuning uchun boshqa
har qanday import dan OLDIN standart qiymatlarni o'rnatamiz. Haqiqiy .env
mavjud bo'lsa, undagi qiymatlar ustun turadi (load_dotenv override qilmaydi,
lekin biz ham faqat setdefault ishlatamiz).

Istisno: `DB_PATH` va `WEBAPP_SECRET`. Ular `load_dotenv` dan OLDIN
majburlanadi, chunki serverdagi `.env` da `DB_PATH` real bazani ko'rsatadi —
`setdefault` esa .env yuklangandan keyin ishlagani uchun testlar shu real
bazaga yozib yuborishi mumkin edi.
"""
import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent

# --- .env dan OLDIN: baza va maxfiy kalit ------------------------------------
# Har bir test sessiyasi o'zining bir martalik SQLite faylini oladi. Ham
# `config.BASE_DIR` (bot), ham `webapp.core.config.DB_PATH` (API) shu
# o'zgaruvchidan import vaqtida hisoblanadi.
_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="vakant3-tests-"))
os.environ["DB_PATH"] = str(_TEST_DB_DIR / "test.sqlite3")

#: `webapp.main` default kalit bilan ishga tushmaydi; testlar o'z tokenlarini
#: shu kalit bilan imzolaydi, shuning uchun haqiqiy kalit umuman kerak emas.
os.environ.setdefault("WEBAPP_SECRET", "test-webapp-secret-not-a-real-one")
os.environ.setdefault("ALLOW_INSECURE_SECRET", "1")

# .env bo'lsa — o'qiymiz; bo'lmasa test qiymatlari ishlaydi.
load_dotenv(_REPO_ROOT / ".env")

os.environ.setdefault("TOKEN", "test-token")
os.environ.setdefault("ADMIN_IDS", "1")
os.environ.setdefault("BOT_USERNAME", "bandlikuzbot")

#: Testlar hech qachon haqiqiy bazaga tegmasin (yuqoridagi majburlash natijasi).
TEST_DB_PATH = Path(os.environ["DB_PATH"])

import pytest  # noqa: E402


@pytest.fixture
def uz_lang() -> str:
    return "uz"


@pytest.fixture(scope="session", autouse=True)
def _cleanup_test_db_dir():
    """Sessiya oxirida vaqtinchalik baza katalogini o'chiramiz."""
    yield
    shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)
