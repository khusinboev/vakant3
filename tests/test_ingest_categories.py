"""Canonical vacancy categories: per-source mapping, store column, m026 backfill, category search."""
from __future__ import annotations

import aiosqlite
import pytest

from src.db.connection import apply_pragmas
from src.db.migrate import run_migrations
from src.db.migrations import m026_vacancy_category
from src.ingest import categories as cat
from src.ingest import repo
from src.ingest.base import NormalizedVacancy
from src.ingest.sources import hh as hh_mod
from src.ingest.sources import osonish as os_mod
from src.ingest.sources import vacancy_gov as gov_mod
from webapp.core.i18n import SPECS

NOW = 1_792_213_200


@pytest.fixture
async def conn(tmp_path):
    async with aiosqlite.connect(tmp_path / "cat.sqlite3") as c:
        await apply_pragmas(c)
        await run_migrations(c)
        yield c


def vac(source, sid, title, category_id=None, **kw) -> NormalizedVacancy:
    return NormalizedVacancy(
        source=source, source_id=sid, title=title, employer=f"Synthetic {source} {sid}", region_soato="1726",
        salary_min=4_000_000, salary_max=6_000_000, currency="UZS", published_at=NOW - int(sid) * 60,
        url=f"https://example.test/{source}/{sid}", category_id=category_id, **kw,
    )


# ---------------------------------------------------------------- taxonomy


def test_canonical_ids_are_the_mini_app_specs():
    assert cat.CANONICAL_IDS == {int(s["id"].split(":", 1)[1]) for s in SPECS}
    assert set(cat.HH_ROLE_CATEGORY.values()) <= cat.CANONICAL_IDS


@pytest.mark.parametrize("raw, expected", [
    ("spec:12", 12), ("12", 12), (47, 47), ("spec:999", None), ("", None), (None, None), ("spec:x", None),
])
def test_spec_to_category(raw, expected):
    assert cat.spec_to_category(raw) == expected


# ---------------------------------------------------------------- keyword classifier


@pytest.mark.parametrize("title, expected", [
    ("Vrach terapevt", cat.HEALTHCARE),
    ("Tibbiyot hamshirasi", cat.HEALTHCARE),
    ("Медицинская сестра", cat.HEALTHCARE),
    ("Ingliz tili o‘qituvchisi", cat.EDUCATION_CULTURE_SPORT),
    ("Ўқитувчи", cat.EDUCATION_CULTURE_SPORT),
    ("Maktab direktori", cat.EDUCATION_CULTURE_SPORT),
    ("Frontend dasturchi", cat.IT),
    ("Программист 1С", cat.IT),
    ("Bosh buxgalter", cat.FINANCE_MANAGEMENT),
    ("Bo‘lim boshlig‘i", cat.FINANCE_MANAGEMENT),
    ("Менеджер по продажам", cat.SALES_MARKETING),
    ("Sotuvchi-konsultant", cat.SALES_MARKETING),
    ("Haydovchi-ekspeditor", cat.TRANSPORT),
    ("Avtoslesar", cat.TRANSPORT),
    ("Slesar-santexnik", cat.INDUSTRY),
    ("Payvandchi", cat.INDUSTRY),
    ("Qurilish ustasi", cat.CONSTRUCTION),
    ("Oshpaz yordamchisi", cat.SERVICES),
    ("Agronom", cat.AGRICULTURE),
    ("Veterinariya vrachi", cat.AGRICULTURE),
    # "agent" is a whole word: an "agentlik" (state agency) post is not a sales agent.
    ("Agentlik bosh mutaxassisi", cat.FINANCE_MANAGEMENT),
    ("Sug'urta agenti", cat.SALES_MARKETING),
])
def test_classify_text_titles(title, expected):
    assert cat.classify_text(title) == expected


def test_classify_text_tiers_occupation_beats_employer_sector():
    # The title's occupation wins over the employer's sector ...
    assert cat.classify_text("Bosh buxgalter", "Tuman tibbiyot birlashmasi") == cat.FINANCE_MANAGEMENT
    # ... a generic title falls through to the employer's sector ...
    assert cat.classify_text("Laborant", "Tuman tibbiyot birlashmasi") == cat.HEALTHCARE
    assert cat.classify_text("Texnik xodim", "12-umumiy o‘rta ta’lim maktabi") == cat.EDUCATION_CULTURE_SPORT
    # ... and a generic title alone uses the generic tier.
    assert cat.classify_text("Laborant") == cat.INDUSTRY
    assert cat.classify_text("Xyz qwerty") is None
    assert cat.classify_text("", None, 5) is None


# ---------------------------------------------------------------- osonish


def os_item(i: int, **over):
    item = {
        "id": 900000000000 + i, "title": "Ishchi", "company": {"name": "Synthetic MCHJ"},
        "min_salary": 3_000_000, "max_salary": 4_000_000,
        "soato_region": {"soato": "1703", "name_uz": "Andijon viloyati"},
        "created_at": "2026-10-17T05:00:00Z",
    }
    item.update(over)
    return item


#: The real osonish shape (prod raw_json): a LIST of field ids plus group/position objects.
REAL_SHAPE = {
    "mmk_group_id": 441, "mmk_position_id": 5168,
    "mmk_position": {"id": 5168, "position_name": "Ishchi", "mmk_code": "9999"},
    "mmk_group": {"id": 441, "cat1": "Xyz", "cat2": "Xyz", "cat3": "Xyz"},
}


@pytest.mark.parametrize("over, expected", [
    ({**REAL_SHAPE, "mmk_group_field_ids": [12]}, 12),
    # Several ids: the first one in our taxonomy wins (3 is not one of ours).
    ({**REAL_SHAPE, "mmk_group_field_ids": [3, 47, 12]}, 47),
    # Empty list / only foreign ids: keywords over title, position_name and cat1..cat3.
    ({**REAL_SHAPE, "mmk_group_field_ids": []}, cat.INDUSTRY),
    ({**REAL_SHAPE, "mmk_group_field_ids": [3], "mmk_position": {"position_name": "Haydovchi"}}, cat.TRANSPORT),
    ({**REAL_SHAPE, "mmk_group_field_ids": [], "title": "Xyz",
      "mmk_group": {"cat1": "Ta'lim", "cat2": "Xyz", "cat3": "Xyz"}}, cat.EDUCATION_CULTURE_SPORT),
    ({"mmk_group_field_id": 12}, 12),
    ({"mmk_group_field": {"id": 47, "name_uz": "Sog'liqni saqlash"}}, 47),
    ({"mmk_group": {"id": 501, "mmk_group_field_id": 41, "name_uz": "Quruvchilar"}}, 41),
    ({"mmk_position": {"id": 7001, "name": "Tikuvchi", "mmk_group": {"field_id": "21"}}}, 21),
    # A field id outside our taxonomy falls back to the keywords of the position name.
    ({"mmk_group_field_id": 99, "mmk_position": {"name": "Haydovchi"}}, cat.TRANSPORT),
    ({"title": "Oshpaz", "mmk_group": {"name_uz": "Umumiy ovqatlanish"}}, cat.SERVICES),
    ({"title": "Xyz"}, None),
])
def test_osonish_category_shapes(over, expected):
    assert cat.osonish_category(os_item(1, **over)) == expected
    v = os_mod.normalize(os_item(1, **over))
    assert v.category_id == expected


# ---------------------------------------------------------------- hh


def hh_item(i: int, title: str, roles: list[tuple[str, str]]):
    return {
        "id": str(100000 + i), "name": title, "area": {"id": "2759", "name": "Ташкент"},
        "employer": {"name": "Synthetic LLC"}, "published_at": "2026-10-17T10:00:00+0500",
        "alternate_url": f"https://hh.uz/vacancy/{100000 + i}", "archived": False,
        "professional_roles": [{"id": rid, "name": name} for rid, name in roles],
    }


@pytest.mark.parametrize("title, roles, expected", [
    ("Senior Python Developer", [("96", "Программист, разработчик")], cat.IT),
    ("QA Engineer", [("124", "Тестировщик")], cat.IT),
    ("Менеджер по продажам B2B", [("70", "Менеджер по продажам, менеджер по работе с клиентами")],
     cat.SALES_MARKETING),
    ("Врач-стоматолог", [("24", "Врач")], cat.HEALTHCARE),
    ("Учитель английского", [("132", "Учитель, преподаватель, педагог")], cat.EDUCATION_CULTURE_SPORT),
    ("Водитель категории C", [("21", "Водитель, экспедитор")], cat.TRANSPORT),
    ("Главный бухгалтер", [("18", "Бухгалтер")], cat.FINANCE_MANAGEMENT),
    ("HR generalist", [("69", "Менеджер по персоналу")], cat.FINANCE_MANAGEMENT),
    ("Прораб", [("100", "Прораб, мастер СМР")], cat.CONSTRUCTION),
    ("Сварщик", [("109", "Сварщик")], cat.INDUSTRY),
    ("Повар горячего цеха", [("94", "Повар, пекарь, кондитер")], cat.SERVICES),
    ("Агроном", [("7", "Агроном")], cat.AGRICULTURE),
    # "Другое" is unmapped: the title decides; the first mapped role wins over later ones.
    ("Продавец в магазин", [("40", "Другое")], cat.SALES_MARKETING),
    ("Something", [("40", "Другое"), ("96", "Программист, разработчик")], cat.IT),
    ("Something", [("40", "Другое")], None),
])
def test_hh_category(title, roles, expected):
    item = hh_item(1, title, roles)
    assert cat.hh_category(item) == expected
    assert hh_mod.normalize(item).category_id == expected


# ---------------------------------------------------------------- vacancy.gov.uz


def gov_item(i: int, position: str, organization: str, structure: str = "", position_type=None):
    return {
        "id": 900000 + i, "position_name": position, "organization": organization, "structure_name": structure,
        "position_type": position_type, "region": "Namangan viloyati , Yangiqo‘rg‘on tumani",
        "position_salary": 3_265_185, "date_start": "2026-10-16T00:00:00", "date_stop": "2026-10-26T00:00:00",
        "is_published": True, "organizationFull": {"name": organization},
    }


@pytest.mark.parametrize("position, org, structure, expected", [
    ("Vrach terapevt", "Synthetic tuman tibbiyot birlashmasi", "Ko`p tarmoqli markaziy poliklinika",
     cat.HEALTHCARE),
    ("Bosh mutaxassis", "Namangan viloyati hokimligi", "Iqtisodiyot bo‘limi", cat.FINANCE_MANAGEMENT),
    ("Yetakchi mutaxassis", "Sog‘liqni saqlash vazirligi", "", cat.HEALTHCARE),
    ("Boshlang‘ich sinf o‘qituvchisi", "Xalq ta’limi bo‘limi", "", cat.EDUCATION_CULTURE_SPORT),
    ("Kutubxonachi", "Axborot-kutubxona markazi", "", cat.EDUCATION_CULTURE_SPORT),
    ("Haydovchi", "Synthetic tuman hokimligi", "", cat.TRANSPORT),
    ("Bosh buxgalter", "Madaniyat bo‘limi", "", cat.FINANCE_MANAGEMENT),
    ("Agronom", "Qishloq xo‘jaligi bo‘limi", "", cat.AGRICULTURE),
    ("Sektor mudiri", "Synthetic tuman madaniyat markazi", "", cat.EDUCATION_CULTURE_SPORT),
    ("Xyz", "Qwerty", "", None),
])
def test_vacancy_gov_category(position, org, structure, expected):
    item = gov_item(1, position, org, structure)
    assert cat.vacancy_gov_category(item) == expected
    assert gov_mod.normalize(item, NOW).category_id == expected


def test_categorize_dispatch_and_label_fallback():
    assert cat.categorize("hh", {"professional_roles": [{"id": "96"}]}, "x") == cat.IT
    assert cat.categorize("vacancy_gov", {}, "Bosh buxgalter") == cat.FINANCE_MANAGEMENT
    assert cat.categorize("unknown", None, "", "Программист, разработчик") == cat.IT
    assert cat.categorize("osonish", None, "") is None


# ---------------------------------------------------------------- store


async def test_upserts_store_category_and_a_miss_never_erases_it(conn):
    await repo.upsert_batch(conn, [vac("osonish", "1", "Ishchi", category_id=12)], NOW)
    # A later sighting (list or detail) whose payload lacks the field keeps the stored id.
    await repo.upsert_batch(conn, [vac("osonish", "1", "Ishchi", category_id=None)], NOW + 10)
    await repo.apply_detail(conn, vac("osonish", "1", "Ishchi", category_id=None), NOW + 20)
    cur = await conn.execute("SELECT category_id FROM vacancies WHERE uid = 'osonish_1'")
    assert (await cur.fetchone())[0] == 12
    await repo.apply_detail(conn, vac("osonish", "1", "Ishchi", category_id=47), NOW + 30)
    cur = await conn.execute("SELECT category_id FROM vacancies WHERE uid = 'osonish_1'")
    assert (await cur.fetchone())[0] == 47


async def test_search_by_category_returns_rows_of_every_source(conn):
    await repo.upsert_batch(conn, [
        vac("hh", "1", "Python developer", category_id=cat.IT),
        vac("osonish", "2", "Dasturchi", category_id=cat.IT),
        vac("vacancy_gov", "3", "Axborot texnologiyalari bo‘yicha mutaxassis", category_id=cat.IT),
        vac("hh", "4", "Врач", category_id=cat.HEALTHCARE),
        vac("vacancy_gov", "5", "Something", category_id=None),
    ], NOW)
    result = await repo.search(conn, category_id=cat.IT, with_total=True)
    assert {i["source"] for i in result["items"]} == {"hh", "osonish", "vacancy_gov"}
    assert result["total"] == 3 and all(i["category_id"] == cat.IT for i in result["items"])
    assert (await repo.search(conn, category_id=cat.HEALTHCARE))["total"] == 1
    assert (await repo.search(conn))["total"] == 5


async def test_category_search_uses_the_partial_index(conn):
    cur = await conn.execute(
        "EXPLAIN QUERY PLAN SELECT id FROM vacancies v WHERE v.status = 'open' AND v.dup_of IS NULL "
        "AND v.category_id = ? ORDER BY v.published_at DESC", (12,)
    )
    plan = " ".join(str(r[3]) for r in await cur.fetchall())
    assert "idx_vacancies_open_category" in plan


# ---------------------------------------------------------------- m026 backfill


async def _insert_legacy(conn, source, sid, title, label, raw):
    """A row as stored before m026 (no category_id)."""
    await repo.upsert_batch(conn, [vac(source, sid, title, category=label, raw=raw)], NOW)
    await conn.execute("UPDATE vacancies SET category_id = NULL WHERE uid = ?", (f"{source}_{sid}",))
    await conn.commit()


async def test_m026_backfills_from_raw_title_and_label_and_reapply_is_safe(conn):
    await _insert_legacy(conn, "hh", "1", "Lead", "Программист, разработчик",
                         {"professional_roles": [{"id": "96", "name": "Программист, разработчик"}]})
    await _insert_legacy(conn, "osonish", "2", "Ishchi", "", {"mmk_group_field_ids": [3, 47], "mmk_group_id": 441})
    await _insert_legacy(conn, "vacancy_gov", "3", "Bosh mutaxassis", "",
                         {"organization": "Synthetic tuman hokimligi"})
    await _insert_legacy(conn, "hh", "4", "Something", "Другое", {"professional_roles": [{"id": "40"}]})
    # A row an adapter already classified is never overwritten by the backfill.
    await repo.upsert_batch(conn, [vac("osonish", "5", "Haydovchi", category_id=cat.IT)], NOW)

    for _ in range(2):  # the second run is the re-apply: same result, nothing new
        await conn.execute("BEGIN IMMEDIATE")
        await m026_vacancy_category.apply(conn)
        await conn.commit()
        cur = await conn.execute("SELECT uid, category_id FROM vacancies ORDER BY uid")
        assert {r[0]: r[1] for r in await cur.fetchall()} == {
            "hh_1": cat.IT, "osonish_2": cat.HEALTHCARE, "vacancy_gov_3": cat.FINANCE_MANAGEMENT,
            "hh_4": None, "osonish_5": cat.IT,
        }
    cur = await conn.execute("SELECT 1 FROM schema_migrations WHERE id = 'm026_vacancy_category'")
    assert await cur.fetchone() is not None


async def test_m026_backfill_walks_in_chunks(conn, monkeypatch):
    monkeypatch.setattr(m026_vacancy_category, "CHUNK", 2)
    for i in range(1, 6):
        await _insert_legacy(conn, "vacancy_gov", str(i), "Vrach", "", {})
    await conn.execute("BEGIN IMMEDIATE")
    assert await m026_vacancy_category.backfill(conn) == 5
    await conn.commit()
    cur = await conn.execute("SELECT COUNT(*) FROM vacancies WHERE category_id = ?", (cat.HEALTHCARE,))
    assert (await cur.fetchone())[0] == 5


async def test_m026_without_the_store_table_is_a_noop(tmp_path):
    async with aiosqlite.connect(tmp_path / "empty.sqlite3") as c:
        await m026_vacancy_category.apply(c)
        cur = await c.execute("SELECT name FROM sqlite_master WHERE name = 'vacancies'")
        assert await cur.fetchone() is None
