import time
from unittest.mock import patch

import pytest


# ─── Tarmoqqa chiqadigan testlar (pytest.ini bo'yicha default o'tkazib yuboriladi) ───

@pytest.mark.network
@pytest.mark.asyncio
async def test_osonish_returns_results():
    from src.functions.scraping import fetch_osonish_list

    items, last_page = await fetch_osonish_list(page=1, salary=0, soato_region="")
    assert len(items) > 0
    assert last_page > 0
    v = items[0]
    assert v.uid.startswith("osonish_")
    assert v.title
    assert v.source == "osonish"


# ─── Unit testlar ─────────────────────────────────────────────────────────────

def test_normalize_uid_backward_compat():
    from src.functions.vacancy_format import normalize_uid

    assert normalize_uid("12345") == "osonish_12345"
    assert normalize_uid("ishapi_12345") == "osonish_12345"
    assert normalize_uid("osonish_99") == "osonish_99"
    assert normalize_uid("") == ""


def test_cache_mem_ttl_expiry():
    with patch("src.functions.cache.get_redis", return_value=None):
        from src.functions.cache import _mem_get, _mem_set
        import src.functions.cache as cache_module

        _mem_set("test_key", "test_value", ttl=1)
        assert _mem_get("test_key") == "test_value"

        cache_module._mem_cache["test_key"] = ("test_value", time.monotonic() - 1)
        assert _mem_get("test_key") is None


def test_spec_legacy_mapping_to_osonish_field():
    from src.functions.functions import normalize_osonish_field_id

    assert normalize_osonish_field_id("22,322,323,324") == 47
    assert normalize_osonish_field_id("213,312") == 12
    assert normalize_osonish_field_id("spec:42") == 42
    assert normalize_osonish_field_id("64") == 64
    assert normalize_osonish_field_id("") is None


# ─── i18n ─────────────────────────────────────────────────────────────────────

def test_normalize_lang_maps_every_input():
    from src.i18n import DEFAULT_LANG, normalize_lang

    assert normalize_lang("ru") == "ru"
    assert normalize_lang("RU-ru") == "ru"
    assert normalize_lang("ru_RU") == "ru"
    assert normalize_lang("en-US") == "en"
    assert normalize_lang("uz-Latn") == "uz"
    assert normalize_lang("kk") == DEFAULT_LANG
    assert normalize_lang(None) == DEFAULT_LANG
    assert normalize_lang(123) == DEFAULT_LANG
    assert normalize_lang("") == DEFAULT_LANG


def test_t_returns_translation_per_lang():
    from src.i18n import t

    assert t("uz", "common.yes") == "Ha"
    assert t("ru", "common.yes") == "Да"
    assert t("en", "common.yes") == "Yes"


def test_t_falls_back_to_uz_then_key():
    from src.i18n import _DICTS, t

    # Faqat uz da mavjud kalit ru uchun ham uz matnini beradi.
    key = "__test_only_uz__"
    _DICTS["uz"][key] = "faqat uz"
    try:
        assert t("ru", key) == "faqat uz"
        assert t("en", key) == "faqat uz"
    finally:
        del _DICTS["uz"][key]

    # Umuman yo'q kalit — kalitning o'zi qaytadi.
    assert t("ru", "__missing_key__") == "__missing_key__"


def test_t_formats_and_survives_bad_placeholders():
    from src.i18n import t

    assert "5" in t("uz", "admin.stats.total", count=5)
    # Yetishmayotgan placeholder bo'lsa ham xato bermaydi.
    assert isinstance(t("uz", "admin.progress"), str)


def test_all_langs_share_the_same_keys():
    from src.i18n import LANGS, _DICTS

    uz_keys = set(_DICTS["uz"])
    for lang in LANGS:
        assert set(_DICTS[lang]) == uz_keys, f"{lang} kalitlari uz dan farq qiladi"


def test_key_for_text_reverse_lookup():
    from src.i18n import key_for_text, t

    assert key_for_text(t("uz", "menu.laws")) == "menu.laws"
    assert key_for_text(t("ru", "menu.laws")) == "menu.laws"
    assert key_for_text(t("en", "menu.hr")) == "menu.hr"
    assert key_for_text("shunday matn yo'q") is None
    assert key_for_text(None) is None
