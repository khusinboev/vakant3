"""Self-healing premium emoji fallback (``src/ui/emoji_fallback.py``).

A fake session plays a Telegram that rejects ANY request carrying custom emoji;
requests go through a real ``Bot`` so the session middleware chain is the one
production uses. No request leaves the process.
"""
from __future__ import annotations

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery,
    CopyMessage,
    EditMessageReplyMarkup,
    EditMessageText,
    SendMessage,
    SendPhoto,
)
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from src.buttons.buttuns import button_text, key_button, key_inline
from src.filters.text_key import TextKey
from src.i18n import t
from src.ui import emoji
from src.ui.emoji_fallback import PremiumEmojiFallback, has_custom_emoji
from tests import test_b1_bot_admin as b1

CHAT = 900000000301


class RejectingSession(b1.RecordingSession):
    """Rejects custom emoji (and anything containing ``boom``) like Telegram would."""

    def __init__(self) -> None:
        super().__init__()
        self.rejected: list = []
        self.always_fail = False

    async def make_request(self, bot, method, timeout=None):
        if self.always_fail or "boom" in str(getattr(method, "text", "") or ""):
            self.rejected.append(method)
            raise TelegramBadRequest(method=method, message="Bad Request: something unrelated")
        if has_custom_emoji(method):
            self.rejected.append(method)
            raise TelegramBadRequest(method=method, message="Bad Request: some wording we do not parse")
        return await super().make_request(bot, method, timeout)


@pytest.fixture
def fb(monkeypatch):
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "1")
    emoji.reset_premium_kill_switch()
    session = RejectingSession()
    session.middleware(PremiumEmojiFallback())
    bot = Bot(b1.TOKEN, session=session, default=DefaultBotProperties(parse_mode="HTML"))
    yield bot, session
    emoji.reset_premium_kill_switch()


def _premium_markup():
    return InlineKeyboardMarkup(inline_keyboard=[[key_inline("uz", "start.btn.jobs", url="https://abitur24.uz/app")]])


async def test_first_send_heals_via_plain_retry_then_premium_is_off(fb, caplog):
    bot, session = fb
    text = t("uz", "start.greeting", name="Ali")
    assert "<tg-emoji" in text
    await bot.send_message(CHAT, text, reply_markup=_premium_markup())
    assert len(session.rejected) == 1
    sent = session.of(SendMessage)
    assert len(sent) == 1
    assert sent[0].text == t("uz", "start.greeting", name="Ali", plain_emoji=True)
    button = sent[0].reply_markup.inline_keyboard[0][0]
    assert button.icon_custom_emoji_id is None
    assert button.text == f"{emoji.ICONS['search'].fallback} {t('uz', 'start.btn.jobs')}"
    assert emoji.premium_enabled() is False
    assert [r.levelname for r in caplog.records if "premium emoji rejected" in r.message] == ["WARNING"]

    # Later messages are built plain: no failing first attempt any more.
    await bot.send_message(CHAT, t("uz", "start.greeting", name="Ali"), reply_markup=_premium_markup())
    assert len(session.rejected) == 1
    assert len(session.of(SendMessage)) == 2
    assert [r.levelname for r in caplog.records if "premium emoji rejected" in r.message] == ["WARNING"]


async def test_error_without_custom_emoji_is_reraised_untouched(fb):
    bot, session = fb
    with pytest.raises(TelegramBadRequest, match="something unrelated"):
        await bot.send_message(CHAT, "boom")
    assert len(session.rejected) == 1  # no retry
    assert emoji.premium_enabled() is True


async def test_failed_retry_raises_and_keeps_premium(fb):
    bot, session = fb
    session.always_fail = True
    with pytest.raises(TelegramBadRequest):
        await bot.send_message(CHAT, emoji.e("job") + " x")
    assert len(session.rejected) == 2  # one original + exactly one retry
    assert emoji.premium_enabled() is True


async def test_reply_keyboard_icon_becomes_the_prefixed_label_that_textkey_matches(fb):
    bot, session = fb
    markup = ReplyKeyboardMarkup(keyboard=[[key_button("ru", "menu.laws")]], resize_keyboard=True)
    assert markup.keyboard[0][0].icon_custom_emoji_id
    await bot.send_message(CHAT, "menu", reply_markup=markup)
    sent = session.of(SendMessage)[-1].reply_markup.keyboard[0][0]
    assert sent.icon_custom_emoji_id is None
    assert sent.text == button_text("ru", "menu.laws")  # premium now off -> the non-premium label
    assert sent.text == f"{emoji.ICONS['laws'].fallback} {t('ru', 'menu.laws')}"
    assert await TextKey("menu.laws")(type("M", (), {"text": sent.text})()) is True


@pytest.mark.parametrize(
    "build",
    [
        lambda m, k: EditMessageText(chat_id=CHAT, message_id=1, text=m, reply_markup=k),
        lambda m, k: EditMessageReplyMarkup(chat_id=CHAT, message_id=1, reply_markup=k),
        lambda m, k: SendPhoto(chat_id=CHAT, photo="file-id", caption=m, reply_markup=k),
        lambda m, k: CopyMessage(chat_id=CHAT, from_chat_id=CHAT, message_id=1, caption=m, reply_markup=k),
        lambda m, k: AnswerCallbackQuery(callback_query_id="1", text=m),
    ],
    ids=["edit_text", "edit_markup", "send_photo", "copy_message", "answer_callback"],
)
async def test_every_method_shape_is_healed(fb, build):
    bot, session = fb
    method = build(f"{emoji.e('job')} Ish", _premium_markup())
    assert has_custom_emoji(method)
    await bot(method)
    assert len(session.rejected) == 1
    accepted = session.requests[-1]
    assert type(accepted) is type(method)
    assert not has_custom_emoji(accepted)
    for field in ("text", "caption"):
        value = getattr(accepted, field, None)
        if value:
            assert value == "💼 Ish"
    assert emoji.premium_enabled() is False


def test_production_bot_has_the_middleware():
    import config

    assert any(isinstance(m, PremiumEmojiFallback) for m in config.bot.session.middleware._middlewares)
