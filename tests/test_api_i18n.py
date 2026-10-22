"""i18n coverage tests: district_name() / DISTRICT_NAMES for the 205 Uzbekistan districts.

The SOATO list below is a frozen snapshot of ``districts.soato`` from the local DB dump
(regions + districts reference data). It is copied inline (not read from any scratch
file) so this test has no filesystem/network dependency at run time.
"""

from webapp.core.district_names import DISTRICT_NAMES
from webapp.core.i18n import district_name

# All 205 SOATO codes present in the districts table (tumanlar / shaharlar).
KNOWN_DISTRICT_SOATO: tuple[str, ...] = (
    "1703202", "1703203", "1703206", "1703209", "1703210", "1703211", "1703214", "1703217", "1703220", "1703224",
    "1703227", "1703230", "1703232", "1703236", "1703401", "1703408", "1706204", "1706207", "1706212", "1706215",
    "1706219", "1706230", "1706232", "1706240", "1706242", "1706246", "1706258", "1706401", "1706403", "1708201",
    "1708204", "1708209", "1708212", "1708215", "1708218", "1708220", "1708223", "1708225", "1708228", "1708235",
    "1708237", "1708401", "1710207", "1710212", "1710220", "1710224", "1710229", "1710232", "1710233", "1710234",
    "1710235", "1710237", "1710242", "1710245", "1710250", "1710401", "1710405", "1712211", "1712216", "1712230",
    "1712234", "1712238", "1712244", "1712248", "1712251", "1712401", "1712408", "1712412", "1714204", "1714207",
    "1714212", "1714216", "1714219", "1714224", "1714229", "1714234", "1714236", "1714237", "1714242", "1714401",
    "1718203", "1718206", "1718209", "1718212", "1718215", "1718216", "1718218", "1718224", "1718227", "1718230",
    "1718233", "1718235", "1718236", "1718238", "1718401", "1718406", "1722201", "1722202", "1722203", "1722204",
    "1722207", "1722210", "1722212", "1722214", "1722215", "1722217", "1722220", "1722221", "1722223", "1722226",
    "1722401", "1724206", "1724212", "1724216", "1724220", "1724226", "1724228", "1724231", "1724235", "1724401",
    "1724410", "1724413", "1726262", "1726264", "1726266", "1726269", "1726273", "1726277", "1726280", "1726283",
    "1726287", "1726290", "1726292", "1726294", "1727206", "1727212", "1727220", "1727224", "1727228", "1727233",
    "1727237", "1727239", "1727248", "1727249", "1727250", "1727253", "1727256", "1727259", "1727265", "1727401",
    "1727404", "1727407", "1727413", "1727415", "1727419", "1727424", "1730203", "1730206", "1730209", "1730212",
    "1730215", "1730218", "1730221", "1730224", "1730226", "1730227", "1730230", "1730233", "1730236", "1730238",
    "1730242", "1730401", "1730405", "1730408", "1730412", "1733217", "1733204", "1733208", "1733212", "1733220",
    "1733221", "1733223", "1733226", "1733230", "1733233", "1733236", "1733401", "1733406", "1735204", "1735207",
    "1735209", "1735211", "1735212", "1735215", "1735218", "1735222", "1735225", "1735228", "1735230", "1735233",
    "1735236", "1735240", "1735243", "1735250", "1735401",
)


def test_known_district_count() -> None:
    assert len(KNOWN_DISTRICT_SOATO) == 205
    assert len(set(KNOWN_DISTRICT_SOATO)) == 205


def test_district_names_covers_every_known_soato() -> None:
    missing = [soato for soato in KNOWN_DISTRICT_SOATO if soato not in DISTRICT_NAMES]
    assert not missing, f"DISTRICT_NAMES is missing {len(missing)} soato codes: {missing}"


def test_district_names_have_ru_and_en_for_every_entry() -> None:
    for soato, entry in DISTRICT_NAMES.items():
        assert entry.get("ru"), f"{soato} missing ru name"
        assert entry.get("en"), f"{soato} missing en name"


def test_district_name_returns_localized_values() -> None:
    soato = "1726266"  # Yunusobod tumani
    name_uz = "Yunusobod tumani"
    assert district_name(soato, name_uz, "uz") == name_uz
    assert district_name(soato, name_uz, "ru") == DISTRICT_NAMES[soato]["ru"]
    assert district_name(soato, name_uz, "en") == DISTRICT_NAMES[soato]["en"]


def test_district_name_falls_back_to_uz_for_unknown_code() -> None:
    name_uz = "Noma'lum tumani"
    assert district_name("0000000", name_uz, "ru") == name_uz
    assert district_name("0000000", name_uz, "en") == name_uz
    # uz lang always short-circuits to name_uz, known code or not.
    assert district_name("1726266", name_uz, "uz") == name_uz
