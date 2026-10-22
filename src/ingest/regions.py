"""Source locations -> our region SOATO codes (the ``regions`` table, 4 digits).

hh.uz lists ~120 Uzbek *cities* directly under area 97 (Russian names, no
province level), so a hand-written city -> province table is needed. osonish
already uses SOATO codes; its region objects are read defensively and fall
back to a name lookup against the ``regions`` table.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

REGION_SOATO: dict[str, str] = {
    "1703": "Andijon viloyati",
    "1706": "Buxoro viloyati",
    "1708": "Jizzax viloyati",
    "1710": "Qashqadaryo viloyati",
    "1712": "Navoiy viloyati",
    "1714": "Namangan viloyati",
    "1718": "Samarqand viloyati",
    "1722": "Surxondaryo viloyati",
    "1724": "Sirdaryo viloyati",
    "1726": "Toshkent shahri",
    "1727": "Toshkent viloyati",
    "1730": "Farg'ona viloyati",
    "1733": "Xorazm viloyati",
    "1735": "Qoraqalpog'iston Respublikasi",
}

_CITIES_BY_REGION: dict[str, tuple[str, ...]] = {
    "1726": ("ташкент",),
    "1727": (
        "ташкентская область", "алмалык", "ангрен", "бекабад", "чирчик", "янгиюль", "нурафшан", "тойтепа",
        "газалкент", "ахангаран", "паркент", "пскент", "кибрай", "келес", "бука", "чиназ", "зангиата",
        "эшангузар", "дустабад", "аккурган", "таваксай", "назарбек", "янгибазар", "бостанлык", "чарвак",
        "нурафшон",
        "хумсан", "юкоричирчик", "салар", "куйичирчик", "уртачирчик", "акташ", "карасу (ташкентская область)",
    ),
    "1703": (
        "андижанская область", "андижан", "асака", "ханабад", "шахрихан", "ходжаабад", "кургантепа",
        "пахтаабад", "балыкчи", "избаскан", "мархамат", "булакбаши", "джалакудук", "алтынкуль", "улугнор",
        "бустон", "пайтуг", "карасу", "ахунбабаев",
    ),
    "1730": (
        "ферганская область", "фергана", "коканд", "маргилан", "кувасай", "кува", "риштан", "бешарык",
        "алтыарык", "язъяван", "фуркат", "багдад", "ташлак", "учкуприк", "дангара", "сох", "яйпан", "хамза",
    ),
    "1714": (
        "наманганская область", "наманган", "чуст", "чартак", "касансай", "пап", "учкурган", "уйчи",
        "туракурган", "янгикурган", "мингбулак", "нарын", "хаккулабад",
    ),
    "1718": (
        "самаркандская область", "самарканд", "каттакурган", "ургут", "джамбай", "булунгур", "пайарык",
        "иштыхан", "нурабад", "акдарья", "джума", "челек", "зиадин", "лаиш", "кушрабат", "тайлак",
    ),
    "1706": (
        "бухарская область", "бухара", "каган", "гиждуван", "вабкент", "ромитан", "шафиркан", "газли",
        "караулбазар", "алат", "каракуль", "галаасия", "жондор",
    ),
    "1712": (
        "навоийская область", "навои", "навоий", "зарафшан", "учкудук", "кызылтепа", "нурата", "кармана",
        "канимех", "тамды", "янгирабад", "тинчлик",
    ),
    "1710": (
        "кашкадарьинская область", "карши", "шахрисабз", "китаб", "гузар", "мубарек", "камаши", "касан",
        "яккабаг", "чиракчи", "бешкент", "талимарджан", "янги-нишан", "нишан", "касби", "мираки",
    ),
    "1722": (
        "сурхандарьинская область", "термез", "денау", "шерабад", "джаркурган", "шурчи", "байсун",
        "кумкурган", "ангор", "узун", "сариасия", "музрабад", "шаргунь", "халкабад",
    ),
    "1708": (
        "джизакская область", "джизак", "галляарал", "пахтакор", "гагарин", "дустлик", "зафарабад",
        "зарбдар", "учтепа", "мирзачуль", "арнасай", "фориш", "янгиабад", "марджанбулак", "заамин", "даштабад",
    ),
    "1724": (
        "сырдарьинская область", "гулистан", "сырдарья", "янгиер", "ширин", "баяут", "сайхунабад", "бахт",
        "хаваст", "сардоба", "мехнатабад",
    ),
    "1733": (
        "хорезмская область", "ургенч", "хива", "ханка", "питнак", "гурлен", "шават", "багат", "янгиарык",
        "кушкупыр", "хазарасп", "тупроккала",
    ),
    "1735": (
        "республика каракалпакстан", "каракалпакстан", "нукус", "ходжейли", "беруни", "турткуль", "кунград",
        "тахиаташ", "чимбай", "муйнак", "шуманай", "кегейли", "мангит", "тахтакупыр", "караузяк",
        "канлыкуль", "акмангит", "элликкала", "бустан",
    ),
}


def _norm(name: str) -> str:
    name = name.lower().replace("ё", "е").replace("ʻ", "'").replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", name).strip()


HH_CITY_REGION: dict[str, str] = {}
for _soato, _names in _CITIES_BY_REGION.items():
    for _name in _names:
        HH_CITY_REGION.setdefault(_norm(_name), _soato)

#: Province name stems for names not in the table ("Самаркандская обл.", "г. Термез").
_REGION_STEMS: tuple[tuple[str, str], ...] = (
    ("ташкентск", "1727"), ("андижан", "1703"), ("ферган", "1730"), ("наманган", "1714"),
    ("самарканд", "1718"), ("бухар", "1706"), ("навои", "1712"), ("кашкадар", "1710"),
    ("сурхандар", "1722"), ("джизак", "1708"), ("сырдар", "1724"), ("хорезм", "1733"),
    ("каракалпак", "1735"),
)


def hh_area_to_region(area: Any) -> Optional[str]:
    """hh ``area`` object (``{"id", "name"}``) -> region SOATO, or ``None`` when unknown."""
    if not isinstance(area, Mapping):
        return None
    name = area.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    norm = _norm(name)
    if norm in HH_CITY_REGION:
        return HH_CITY_REGION[norm]
    stripped = re.sub(r"^(г\.|город|пос\.|поселок|посёлок)\s*", "", norm)
    stripped = re.sub(r"\s*\(.*\)$", "", stripped).strip()
    if stripped in HH_CITY_REGION:
        return HH_CITY_REGION[stripped]
    for stem, soato in _REGION_STEMS:
        if stem in norm:
            return soato
    return None


def _code(obj: Mapping[str, Any]) -> str:
    for key in ("soato", "code", "soato_code"):
        value = obj.get(key)
        if isinstance(value, (int, str)) and str(value).strip().isdigit():
            return str(value).strip()
    return ""


def osonish_region(
    item: Mapping[str, Any], region_names: Mapping[str, str] | None = None
) -> tuple[Optional[str], Optional[str], str]:
    """``(region_soato, district_soato, region_name)`` from an osonish vacancy.

    ``region_names`` maps lower-cased ``regions.name_uz`` -> soato for the name
    fallback when the object carries no code.
    """
    region_obj = item.get("soato_region") if isinstance(item.get("soato_region"), Mapping) else {}
    district_obj = item.get("soato_district") if isinstance(item.get("soato_district"), Mapping) else {}
    region_name = str(region_obj.get("name_uz") or region_obj.get("name") or "").strip()

    region = _code(region_obj)
    district = _code(district_obj)
    if not region and isinstance(item.get("soato_region"), (int, str)):
        region = str(item.get("soato_region")).strip()
    if not district and isinstance(item.get("soato_district"), (int, str)):
        district = str(item.get("soato_district")).strip()

    region = region[:4] if len(region) >= 4 and region[:4] in REGION_SOATO else ""
    if not region and len(district) >= 4 and district[:4] in REGION_SOATO:
        region = district[:4]
    if not region and region_name and region_names:
        region = region_names.get(region_name.lower(), "")
    if not district.isdigit() or len(district) != 7:
        district = ""
    if not region_name and region:
        region_name = REGION_SOATO[region]
    return (region or None), (district or None), region_name
