"""Click configuration, limits and input rules (SlaydX ``env.ts`` click block,
``lib/topup-limits.ts``, ``lib/click-input.ts``, ``lib/payment-bonus.ts``).

Credentials are read on every call from ``get_settings()`` (pydantic reads the
env and ``.env``), so tests switch payments on by setting fake values on the
settings object; nothing is captured at import time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlsplit

from webapp.core.config import get_settings

#: Every order id Click sees is ``vk-<uuid>``: SlaydX owns the Click service
#: and forwards exactly these requests to us.
ORDER_PREFIX = "vk-"

#: Owner decision (same as SlaydX 2026-10-09): free amount, 1 000 – 10 000 000 so'm.
MIN_TOPUP_SOUM = 1_000
MAX_TOPUP_SOUM = 10_000_000

PAYMENT_BONUS_MIN = 0
PAYMENT_BONUS_MAX = 50

CLICK_METHODS = ("page", "card", "phone", "app")

UUID_RE = re.compile(r"^[0-9a-f-]{36}$", re.IGNORECASE)


@dataclass(frozen=True)
class ClickConfig:
    service_id: str
    merchant_id: str
    secret_key: str
    merchant_user_id: str


def click_config() -> ClickConfig | None:
    """The Click credentials, or None when any of the four is missing (payments off)."""
    settings = get_settings()
    values = (
        str(getattr(settings, "CLICK_SERVICE_ID", "") or "").strip(),
        str(getattr(settings, "CLICK_MERCHANT_ID", "") or "").strip(),
        str(getattr(settings, "CLICK_SECRET_KEY", "") or "").strip(),
        str(getattr(settings, "CLICK_MERCHANT_USER_ID", "") or "").strip(),
    )
    if not all(values):
        return None
    return ClickConfig(*values)


def shop_credentials() -> tuple[str, str] | None:
    """(service_id, secret_key) for the Shop API callback, as in SlaydX's route.

    The callback needs only these two: a payment Click already charged must
    still settle even if a Merchant API value was removed meanwhile (new
    orders are refused by :func:`click_config` in that case).
    """
    settings = get_settings()
    service_id = str(getattr(settings, "CLICK_SERVICE_ID", "") or "").strip()
    secret = str(getattr(settings, "CLICK_SECRET_KEY", "") or "").strip()
    return (service_id, secret) if service_id and secret else None


def payments_enabled() -> bool:
    return click_config() is not None


def click_order_ref(order_id: str) -> str:
    """``merchant_trans_id`` / ``transaction_param`` Click receives for an order."""
    return f"{ORDER_PREFIX}{order_id}"


def order_id_from_ref(merchant_trans_id: str) -> str | None:
    """The order id inside ``vk-<uuid>``, or None for anything else (foreign or malformed)."""
    raw = str(merchant_trans_id or "")
    if not raw.startswith(ORDER_PREFIX):
        return None
    order_id = raw[len(ORDER_PREFIX):]
    return order_id.lower() if UUID_RE.match(order_id) else None


def topup_amount_valid(amount: int) -> bool:
    return MIN_TOPUP_SOUM <= amount <= MAX_TOPUP_SOUM


def payment_bonus_amount(amount_soum: int, percent: int) -> int:
    """floor(amount × percent / 100); 0 for a bad amount or a percent outside 1–50."""
    if not isinstance(amount_soum, int) or amount_soum <= 0:
        return 0
    if not isinstance(percent, int) or percent <= PAYMENT_BONUS_MIN or percent > PAYMENT_BONUS_MAX:
        return 0
    return (amount_soum * percent) // 100


# ---------------------------------------------------------------------------
# Input rules for the direct methods (SlaydX lib/click-input.ts)
# ---------------------------------------------------------------------------

CARD_MIN_DIGITS = 16
CARD_MAX_DIGITS = 19


def digits_of(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def normalize_card_number(value: str) -> str | None:
    """16–19 digits, no prefix allow-list (Click's card_token/request is the check)."""
    d = digits_of(value)
    return d if CARD_MIN_DIGITS <= len(d) <= CARD_MAX_DIGITS else None


def parse_expiry(value: str, today: date | None = None) -> tuple[str | None, str | None]:
    """``MM/YY`` / ``MMYY`` -> (``MMYY``, None) or (None, reason).

    A card is valid through the last day of its month, so the current month passes.
    Reasons: ``required``, ``format``, ``month``, ``expired``.
    """
    d = digits_of(value)
    if not d:
        return None, "required"
    if len(d) != 4:
        return None, "format"
    month = int(d[:2])
    year = 2000 + int(d[2:])
    if month < 1 or month > 12:
        return None, "month"
    now = today or date.today()
    if year * 12 + (month - 1) < now.year * 12 + (now.month - 1):
        return None, "expired"
    return d, None


def normalize_phone(value: str) -> str | None:
    """Click's ``phone_number``: ``998`` + 9 digits (also accepts the bare 9 digits)."""
    d = digits_of(value)
    if len(d) == 9:
        return f"998{d}"
    return d if re.fullmatch(r"998\d{9}", d) else None


def normalize_sms_code(value: str) -> str | None:
    d = digits_of(value)
    return d if 4 <= len(d) <= 8 else None


# ---------------------------------------------------------------------------
# Paynet provider endpoint (webapp/payments/paynet.py)
# ---------------------------------------------------------------------------

#: The payer id a user types at a Paynet agent is ``vk-<user id>`` (``vk_`` is
#: accepted too). Same prefix family as Click's ``vk-<order uuid>``.
PAYNET_PAYER_PREFIXES = ("vk-", "vk_")

#: Our ``providerTrnId`` = this + ``payment_orders.seq``. SlaydX numbers its own
#: Paynet transactions from 1, and Paynet sees both statements merged.
PAYNET_TRN_OFFSET = 1_000_000_000


@dataclass(frozen=True)
class PaynetConfig:
    username: str
    password: str
    service_ids: frozenset[int]
    client_param: str


def paynet_config() -> PaynetConfig | None:
    """Credentials + service ids, or None when any is missing (every call is then a 401)."""
    settings = get_settings()
    username = str(getattr(settings, "PAYNET_USERNAME", "") or "")
    password = str(getattr(settings, "PAYNET_PASSWORD", "") or "")
    raw_ids = str(getattr(settings, "PAYNET_SERVICE_IDS", "") or "")
    service_ids = frozenset(
        int(item) for item in (part.strip() for part in raw_ids.split(",")) if item.isascii() and item.isdigit()
    )
    client_param = str(getattr(settings, "PAYNET_CLIENT_PARAM", "") or "").strip() or "client_id"
    if not username or not password or not service_ids:
        return None
    return PaynetConfig(username, password, service_ids, client_param)


def paynet_enabled() -> bool:
    return paynet_config() is not None


def paynet_app_url() -> str | None:
    """``PAYNET_APP_URL`` when it is a plain ``https://`` URL, else None (button hidden)."""
    raw = str(getattr(get_settings(), "PAYNET_APP_URL", "") or "").strip()
    if not raw or any(ch.isspace() for ch in raw):
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    return raw if parts.scheme == "https" and parts.hostname else None


def paynet_payer_id(user_id: int) -> str:
    return f"{PAYNET_PAYER_PREFIXES[0]}{int(user_id)}"
