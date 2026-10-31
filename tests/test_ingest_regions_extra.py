"""hh.uz city names that were missing from the city -> region table (prod gaps)."""
from __future__ import annotations

import pytest

from src.ingest.regions import REGION_SOATO, hh_area_to_region


@pytest.mark.parametrize(
    "name,soato,region_name",
    [
        ("Нурафшон", "1727", "Toshkent viloyati"),
        ("Бустан", "1735", "Qoraqalpog'iston Respublikasi"),
        ("Тинчлик", "1712", "Navoiy viloyati"),
        ("Даштабад", "1708", "Jizzax viloyati"),
    ],
)
def test_missing_hh_cities_map_to_their_region(name, soato, region_name):
    assert hh_area_to_region({"id": "1", "name": name}) == soato
    assert REGION_SOATO[soato] == region_name
