"""Opaque vacancy token: links never name the vacancy source, old links still work."""
from __future__ import annotations

import re

import pytest
from aiogram.methods import SendMessage

from src.functions.vacancy_format import vacancy_app_url, vacancy_deeplink
from src.functions.vacancy_token import (
    MAX_TOKEN_LEN,
    SOURCE_CODES,
    decode_vacancy_token,
    encode_vacancy_token,
    uid_from_start_param,
)
from tests import test_c_bot_ux
from tests.test_c_bot_ux import USER, WEBAPP, _inline

ux = test_c_bot_ux.ux

IDS = ["1", "7", "123", "138492163", "900000000123", "999999999999999", "9007199254740993", "123456789012345678"]
LEAKS = ("hh", "osonish", "vacancy_gov", "vacancy_", "vacancy")


@pytest.mark.parametrize("source", sorted(SOURCE_CODES))
@pytest.mark.parametrize("source_id", IDS)
def test_token_round_trips_for_every_source(source, source_id):
    uid = f"{source}_{source_id}"
    token = encode_vacancy_token(uid)
    assert token is not None and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", token) and len(token) <= MAX_TOKEN_LEN
    assert token[0] == "v" and token[1] == SOURCE_CODES[source]
    assert decode_vacancy_token(token) == uid
    assert uid_from_start_param(token) == uid


def test_token_is_the_documented_base36_form():
    assert encode_vacancy_token("hh_138492163") == "vh2agd8j"
    assert encode_vacancy_token("osonish_35") == "voz"
    assert decode_vacancy_token("voz") == "osonish_35"


@pytest.mark.parametrize("uid", ["osonish_900000000123", "hh_900000000601", "hh_5", "osonish_42"])
def test_built_links_name_no_source(uid):
    for link in (vacancy_deeplink(uid), vacancy_app_url(uid)):
        low = link.lower()
        assert not any(word in low for word in LEAKS), link
    assert vacancy_deeplink(uid).endswith(f"?start={encode_vacancy_token(uid)}")
    assert vacancy_app_url(uid).endswith(f"?go={encode_vacancy_token(uid)}")


def test_old_start_param_form_is_still_accepted():
    assert uid_from_start_param("vacancy_osonish_12345") == "osonish_12345"
    assert uid_from_start_param("vacancy_hh_900000000601") == "hh_900000000601"
    assert uid_from_start_param("vacancy_vacancy_gov_77") == "vacancy_gov_77"


@pytest.mark.parametrize(
    "bad",
    [
        "", "v", "vh", "vx2a", "vh_", "vh2a!", "vh2a ", " vh2a", "VH2A", "v" + "h" + "z" * 15, "vh0", "vh00",
        "hh_5", "osonish_5", "vacancy_", "vacancy_hh_12a", "vacancy_hh_0", "vacancy_hh_05", "vacancy_zz_5",
        "ref_123", "app", None, 5,
    ],
)
def test_invalid_tokens_are_rejected(bad):
    assert uid_from_start_param(bad) is None


@pytest.mark.parametrize("bad", ["", "hh_", "hh_0", "hh_05", "hh_1a", "zz_5", "hh_5 ", "osonish_" + "9" * 19, None, 5])
def test_encode_rejects_unknown_uids(bad):
    assert encode_vacancy_token(bad) is None


def test_unexpected_uid_falls_back_to_plain_links():
    assert vacancy_app_url("osonish_1&go=admin") == WEBAPP
    assert vacancy_deeplink("zz_5").endswith("bandlikuzbot")


async def test_start_with_a_token_opens_the_card_and_the_old_form_still_works(ux):
    token = encode_vacancy_token("osonish_123")
    await ux.send(USER, f"/start {token}")
    card = ux.session.of(SendMessage)[-1]
    assert "Dasturchi &lt;senior&gt;" in card.text
    assert _inline(card.reply_markup)[0].web_app.url == f"{WEBAPP}?go={token}"
    await ux.send(USER, "/start vacancy_osonish_123")
    old = ux.session.of(SendMessage)[-1]
    assert old.text == card.text


async def test_start_with_a_malformed_old_link_is_rejected(ux):
    from src.i18n import t

    await ux.send(USER, "/start vacancy_hh_12a")
    assert ux.session.of(SendMessage)[-1].text == t("uz", "start.bad_vacancy_link")


# ---------------------------------------------------------------- vacancy_gov links


def _gov_row(source_id: str, title: str):
    import time

    from src.ingest.base import NormalizedVacancy

    return NormalizedVacancy(
        source="vacancy_gov", source_id=source_id, title=title, employer="Synthetic Agency", region_soato="1726",
        salary_min=4_000_000, salary_max=6_000_000, currency="UZS", published_at=int(time.time()) - 3600,
        description_text="Talablar: yuqori malaka. " * 10, url=f"https://vacancy.example.test/{source_id}",
    )


def test_parse_vacancy_uid_accepts_vacancy_gov():
    from src.functions.vacancy_format import parse_vacancy_uid

    assert parse_vacancy_uid("vacancy_gov_900000000701") == ("vacancy_gov", "900000000701")
    assert parse_vacancy_uid("vacancy_gov_0") is None and parse_vacancy_uid("vacancy_gov_1a") is None


def test_vacancy_gov_links_are_opaque_and_resolve():
    uid = "vacancy_gov_900000000701"
    for link in (vacancy_deeplink(uid), vacancy_app_url(uid)):
        assert not any(word in link.lower() for word in LEAKS), link
    token = encode_vacancy_token(uid)
    assert token[:2] == "vg" and uid_from_start_param(token) == uid
    assert uid_from_start_param(f"vacancy_{uid}") == uid


async def test_vacancy_gov_channel_token_opens_the_card_in_the_bot(ux):
    from tests.test_store_consumers import _store_rows

    await _store_rows(ux.db_path, _gov_row("900000000701", "Inspektor"))
    token = vacancy_deeplink("vacancy_gov_900000000701").split("?start=", 1)[1]
    await ux.send(USER, f"/start {token}")
    card = ux.session.of(SendMessage)[-1]
    assert "Inspektor" in card.text and "Synthetic Agency" in card.text
    assert _inline(card.reply_markup)[0].web_app.url == f"{WEBAPP}?go={token}"
    await ux.send(USER, "/start vacancy_vacancy_gov_900000000701")  # old form
    assert "Inspektor" in ux.session.of(SendMessage)[-1].text
