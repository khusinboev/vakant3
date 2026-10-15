"""
Testlar uchun umumiy sozlash — hermetik: `.env` UMUMAN o'qilmaydi.

`config` va `webapp.core.config` import vaqtida muhitni o'qiydi, shuning uchun
har qanday import dan OLDIN hamma kalitni majburan (setdefault emas) sun'iy
qiymatga o'rnatamiz. Avval `.env` yuklanib, undagi haqiqiy TOKEN/ADMIN_IDS/
REDIS_URL testlarga tushardi: mock qilinmagan Telegram chaqiruvi haqiqiy bot
nomidan ketishi mumkin edi, CI esa (`.env` yo'q) "test-token" ni aiogram rad
etgani uchun yiqilardi.

- `PYTHON_DOTENV_DISABLED=1` — `config.py` dagi `load_dotenv()` hech narsa qilmaydi.
- pydantic-settings `.env` faylini o'zi o'qiydi, lekin muhit o'zgaruvchilari
  undan ustun — shuning uchun uning har bir maydoni quyida berilgan.
- `DB_PATH` — har sessiyaga bir martalik SQLite fayli (real bazaga hech qachon).
- `REDIS_URL=""` — kesh va limiter o'zining in-memory zaxira yo'lida ishlaydi.
"""
import os
import shutil
import tempfile
from pathlib import Path


_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="vakant3-tests-"))

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ.update(
    {
        "DB_PATH": str(_TEST_DB_DIR / "test.sqlite3"),
        # Valid aiogram format (`<digits>:<secret>`), never a real bot.
        "TOKEN": "123456789:TEST-dummy-token-never-valid-on-telegram",
        "ADMIN_IDS": "1",
        "BOT_USERNAME": "bandlikuzbot",
        # `webapp.main` refuses the default secret; tests sign their own tokens with this one.
        "WEBAPP_SECRET": "test-webapp-secret-not-a-real-one",
        "ALLOW_INSECURE_SECRET": "1",
        "WEBAPP_ORIGIN": "http://localhost:5173",
        "WEBAPP_URL": "https://abitur24.uz/app",
        "REDIS_URL": "",
        # Plain fallback emoji by default; premium-emoji tests switch it on explicitly.
        "BOT_PREMIUM_EMOJI": "0",
        # Payments off unless a test sets fake Click credentials on get_settings();
        # empty values also shadow any real CLICK_* in a developer's .env.
        "CLICK_SERVICE_ID": "",
        "CLICK_MERCHANT_ID": "",
        "CLICK_SECRET_KEY": "",
        "CLICK_MERCHANT_USER_ID": "",
    }
)

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
