"""Premium emoji registry, i18n tokens, button labels and reply-keyboard matching."""
from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from src.buttons import buttuns
from src.buttons.buttuns import BUTTON_ICONS, button_text, key_button, key_inline, main_menu_kb
from src.filters.text_key import TextKey, text_matches
from src.i18n import LANGS, key_for_text, t
from src.i18n.en import STRINGS as EN
from src.i18n.ru import STRINGS as RU
from src.i18n.uz import STRINGS as UZ
from src.ui import emoji
from src.ui.emoji import ICONS, TOKEN_RE, clip, e, inline_button, labelled, render_tokens, strip_leading_emoji

DICTS = {"uz": UZ, "ru": RU, "en": EN}


@pytest.fixture
def premium(monkeypatch):
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "1")


# ── registry and flag ────────────────────────────────────────────────────

def test_flag_defaults_on_and_conftest_turns_it_off(monkeypatch):
    assert emoji.premium_enabled() is False  # tests/conftest.py
    monkeypatch.delenv("BOT_PREMIUM_EMOJI")
    assert emoji.premium_enabled() is True  # no server .env change needed
    for off in ("0", "false", "OFF", "no"):
        monkeypatch.setenv("BOT_PREMIUM_EMOJI", off)
        assert emoji.premium_enabled() is False


def test_registry_ids_are_numeric_and_fallbacks_are_emoji():
    for key, icon in ICONS.items():
        assert icon.fallback and strip_leading_emoji(icon.fallback) == "", key
        assert icon.id is None or icon.id.isdigit(), key


def test_e_renders_tg_emoji_only_when_enabled(premium, monkeypatch):
    assert e("job") == '<tg-emoji emoji-id="6332307572845971158">💼</tg-emoji>'
    assert e("job", plain=True) == "💼"
    assert e("profile") == "👤"  # no custom id -> fallback
    assert e("nope") == ""
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "0")
    assert e("job") == "💼"


def test_tokens_render_before_format_so_values_are_never_scanned(premium):
    out = t("uz", "start.greeting", name="{e:job}")
    assert "<b>{e:job}</b>" in out  # user value left untouched
    assert out.startswith('<tg-emoji emoji-id="6332573100609111421">👋</tg-emoji>')
    assert "{e:" not in t("uz", "start.greeting", name="x", plain_emoji=True).replace("{e:job}", "")
    assert t("uz", "start.greeting", name="x", plain_emoji=True).startswith("👋 ")


def test_every_token_in_dictionaries_is_known_and_same_per_language():
    for key, uz_value in UZ.items():
        tokens = sorted(TOKEN_RE.findall(uz_value))
        for name in tokens:
            assert name in ICONS, (key, name)
        for lang in ("ru", "en"):
            assert sorted(TOKEN_RE.findall(DICTS[lang][key])) == tokens, (lang, key)


def test_alert_texts_carry_no_tokens():
    """callback.answer() shows plain text: a tg-emoji tag would be printed raw."""
    for key in ("start.check.ok", "start.check.fail", "admin.denied", "bc.queued", "bc.test_sent",
                "bc.expired", "bc.state_changed", "bc.empty_segment", "content.laws.not_found"):
        for d in DICTS.values():
            assert "{e:" not in d[key], key
    for key in UZ:
        if key.startswith("bc.status."):  # used inside alerts via bc.state_changed
            for d in DICTS.values():
                assert "{e:" not in d[key], key


def test_button_label_keys_are_bare_in_all_languages():
    for key in BUTTON_ICONS:
        for lang, d in DICTS.items():
            value = d[key]
            assert "{e:" not in value, (lang, key)
            assert strip_leading_emoji(value) == value.strip(), (lang, key, value)
            assert BUTTON_ICONS[key] in ICONS


# ── buttons ──────────────────────────────────────────────────────────────

def test_label_uses_icon_field_or_prefix_never_both(premium, monkeypatch):
    assert labelled("job", "Ish") == {"text": "Ish", "icon_custom_emoji_id": "6332307572845971158"}
    assert labelled("job", "Ish", plain=True) == {"text": "💼 Ish"}
    assert labelled("profile", "Profil") == {"text": "👤 Profil"}
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "0")
    assert labelled("job", "Ish") == {"text": "💼 Ish"}


def test_inline_button_validation(premium):
    btn = inline_button("job", "Ish", url="https://t.me/x", style="primary")
    assert btn.icon_custom_emoji_id and btn.text == "Ish" and btn.style == "primary"
    with pytest.raises(ValueError):
        inline_button(None, "x", callback_data="a" * 65)
    with pytest.raises(ValueError):
        inline_button(None, "x")
    with pytest.raises(ValueError):
        inline_button(None, "x", url="https://a", callback_data="b")
    with pytest.raises(ValueError):
        inline_button(None, "x", url="https://a", style="green")
    # 64 bytes, multi-byte characters counted as bytes
    inline_button(None, "x", callback_data="a" * 64)
    with pytest.raises(ValueError):
        inline_button(None, "x", callback_data="ы" * 33)


def test_clip_counts_code_points_and_never_splits_an_emoji():
    assert clip("  a   b  ", 10) == "a b"
    s = "😀" * 10
    out = clip(s, 5)
    assert out == "😀😀😀😀…"
    out.encode("utf-16-le")  # no lone surrogate
    assert clip("abc", 0) == ""


def test_key_inline_and_reply_buttons(premium):
    b = key_button("ru", "menu.laws")
    assert b.text == "Законодательство" and b.icon_custom_emoji_id == ICONS["laws"].id
    kb = buttuns.bc_preview_kb("en", 5, 3)
    send = kb.inline_keyboard[1][0]
    assert send.text == "✅ Send to 3" and send.style == "success"  # success has no custom id
    stop = buttuns.bc_progress_kb("en", 5, "running", confirm_stop=True).inline_keyboard[0][0]
    assert stop.style == "danger"
    assert key_inline("uz", "start.btn.open_app", web_app="https://abitur24.uz/app").web_app.url


def test_button_text_matches_the_button(premium, monkeypatch):
    for lang in LANGS:
        kb = main_menu_kb(lang, 900000000201)
        assert [b.text for b in kb.keyboard[2]] == [button_text(lang, "menu.laws"), button_text(lang, "menu.hr")]
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "0")
    assert button_text("uz", "menu.laws") == "📚 Qonunchilik"


# ── reply-keyboard matching ──────────────────────────────────────────────

@pytest.mark.parametrize("lang", LANGS)
async def test_textkey_matches_bare_prefixed_and_legacy_labels(lang, monkeypatch):
    flt = TextKey("menu.laws")
    bare = t(lang, "menu.laws")
    for text in (
        bare,                                   # custom emoji icon: Telegram sends the bare label
        button_text(lang, "menu.laws"),         # fallback-prefixed label
        f"⚖️ {bare}",                           # keyboard sent before the label change
        f"⚖️{bare}  ",
        bare.upper(),
    ):
        assert await flt(SimpleNamespace(text=text)) is True, text
    for text in ("", "⚖️", f"{bare} x", None, t(lang, "menu.hr")):
        assert await flt(SimpleNamespace(text=text)) is False, text
    monkeypatch.setenv("BOT_PREMIUM_EMOJI", "1")
    assert await flt(SimpleNamespace(text=key_button(lang, "menu.laws").text)) is True


@pytest.mark.parametrize("lang", LANGS)
def test_admin_back_matches_in_every_language_despite_common_back_collision(lang):
    # ru/en "common.back" and "btn.admin.back" have the same bare text.
    assert text_matches(t(lang, "btn.admin.back"), "btn.admin.back")
    assert text_matches(button_text(lang, "btn.admin.back"), "btn.admin.back")
    assert text_matches(f"🔙{t(lang, 'btn.admin.back')}", "btn.admin.back")
    assert not text_matches(t(lang, "btn.admin.stats"), "btn.admin.back")


def test_key_for_text_strips_leading_emoji():
    assert key_for_text("📚 Qonunchilik") == "menu.laws"
    assert key_for_text("⚖️ Labour law") == "menu.laws"
    assert key_for_text("💡HR-советы") == "menu.hr"
    assert key_for_text("⚖️") is None


def test_strip_leading_emoji_handles_flags_keycaps_and_joiners():
    assert strip_leading_emoji("🇺🇿 O'zbekcha") == "O'zbekcha"
    assert strip_leading_emoji("👨‍💻 Dev") == "Dev"
    assert strip_leading_emoji("👍🏽 ok ") == "ok"
    assert strip_leading_emoji("1. Kanal") == "1. Kanal"
    assert strip_leading_emoji("Ish 💼") == "Ish 💼"


def test_render_tokens_is_noop_without_tokens():
    assert render_tokens("a {b}") == "a {b}"
    assert re.fullmatch(r"💼 x", render_tokens("{e:job} x", plain=True))
