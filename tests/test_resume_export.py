"""Resume rendering tests: date formatting, document building, PDF output, photo policy."""

import io

import pytest

from webapp.resume.i18n import fmt_date, fmt_period
from webapp.resume.normalize import build_resume_document, hex_to_rgb, parse_bullets
from webapp.resume.photos import is_allowed_photo_host
from webapp.resume.render.pdf import generate_pdf_bytes
from webapp.resume.schemas import (
    FREE_TEMPLATES,
    TEMPLATES,
    ResumeEducationItem,
    ResumeExperienceItem,
    ResumeProfileData,
    template_items,
)


def _sample_profile() -> ResumeProfileData:
    return ResumeProfileData(
        full_name="Test Candidate",
        position="Backend Engineer",
        phone="+998901234567",
        email="test@example.com",
        location="Tashkent",
        website="https://example.com",
        summary="Production-ready backend systems builder.",
        experiences=[
            ResumeExperienceItem(
                role="Engineer",
                company="Acme",
                start_date="01/2022",
                end_date="05/2026",
                location="Tashkent",
                description="Built APIs and improved performance.\n- Cut p95 latency in half",
            )
        ],
        educations=[
            ResumeEducationItem(
                school="TUIT",
                degree="BSc",
                start_date="2018",
                end_date="2022",
                description="Computer Science",
            )
        ],
        skills=["Python", "FastAPI", "SQL"],
        languages=["Uzbek", "English"],
    )


def _uzbek_profile() -> ResumeProfileData:
    return ResumeProfileData(
        full_name="Abdullayev Ali Akbar",
        position="Dasturchi",
        phone="+998901234567",
        email="ali@example.com",
        location="Toshkent, O'zbekiston",
        summary="5+ yillik tajribaga ega Python dasturchisi.",
        experiences=[
            ResumeExperienceItem(
                role="Katta Dasturchi",
                company="IT Kompaniya",
                start_date="03/2021",
                end_date="Hozir",
                location="Toshkent",
                description="Mikroservislar arxitekturasi bo'yicha loyihalar.",
            )
        ],
        educations=[
            ResumeEducationItem(
                school="TATU",
                degree="Bakalavr",
                start_date="09/2017",
                end_date="06/2021",
                description="Kompyuter tizimlari va tarmoqlari.",
            )
        ],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        languages=["O'zbek", "Ingliz", "Rus"],
    )


def _russian_profile() -> ResumeProfileData:
    return ResumeProfileData(
        full_name="Абдуллаев Али Акбар",
        position="Разработчик",
        phone="+998901234567",
        email="ali@example.com",
        location="Ташкент, Узбекистан",
        summary="Python-разработчик с опытом более 5 лет.",
        experiences=[
            ResumeExperienceItem(
                role="Ведущий разработчик",
                company="ИТ Компания",
                start_date="03/2021",
                end_date="06/2024",
                location="Ташкент",
                description="Проекты по микросервисной архитектуре.",
            )
        ],
        educations=[ResumeEducationItem(school="ТУИТ", degree="Бакалавр", start_date="09/2017", end_date="06/2021")],
        skills=["Python", "FastAPI"],
        languages=["Узбекский", "Русский"],
    )


# ─── date formatting ──────────────────────────────────────────────────────────

class TestFmtDate:
    def test_mm_yyyy_converted(self):
        assert fmt_date("05/2023") == "May 2023"

    def test_january(self):
        assert fmt_date("01/2020") == "Yanvar 2020"

    def test_december(self):
        assert fmt_date("12/1999") == "Dekabr 1999"

    def test_year_only_passthrough(self):
        assert fmt_date("2023") == "2023"

    def test_hozir_passthrough(self):
        assert fmt_date("Hozir") == "Hozir"
        assert fmt_date("hozir") == "hozir"

    def test_empty_returns_empty(self):
        assert fmt_date("") == ""

    def test_invalid_month_passthrough(self):
        assert fmt_date("13/2023") == "13/2023"

    def test_russian_month(self):
        assert fmt_date("05/2023", "ru") == "Май 2023"

    def test_english_month(self):
        assert fmt_date("05/2023", "en") == "May 2023"
        assert fmt_date("01/2020", "en") == "January 2020"

    def test_unknown_lang_falls_back_to_uz(self):
        assert fmt_date("01/2020", "de") == "Yanvar 2020"


class TestFmtPeriod:
    def test_both_parts_formatted(self):
        assert fmt_period("03/2020", "05/2023") == "Mart 2020 – May 2023"

    def test_end_hozir(self):
        assert fmt_period("01/2022", "Hozir") == "Yanvar 2022 – Hozir"

    def test_only_start(self):
        assert fmt_period("06/2019", "") == "Iyun 2019"

    def test_both_empty(self):
        assert fmt_period("", "") == ""

    def test_russian(self):
        assert fmt_period("03/2020", "05/2023", "ru") == "Март 2020 – Май 2023"


# ─── helpers ──────────────────────────────────────────────────────────────────

class TestHexToRgb:
    def test_green(self):
        assert hex_to_rgb("#0f766e") == (15, 118, 110)

    def test_blue(self):
        assert hex_to_rgb("#2563eb") == (37, 99, 235)

    def test_invalid_falls_back(self):
        assert hex_to_rgb("invalid") == (15, 118, 110)

    def test_without_hash(self):
        assert hex_to_rgb("111827") == (17, 24, 39)


class TestParseBullets:
    def test_dash_becomes_bullet(self):
        assert parse_bullets("- one\n- two") == ["• one", "• two"]

    def test_plain_lines_kept(self):
        assert parse_bullets("one\n\ntwo") == ["one", "two"]


# ─── document model ───────────────────────────────────────────────────────────

class TestBuildResumeDocument:
    def test_basic_fields(self):
        doc = build_resume_document(_sample_profile())
        assert doc["name"] == "Test Candidate"
        assert doc["position"] == "Backend Engineer"
        assert "test@example.com" in doc["contacts"]
        assert len(doc["experiences"]) == 1
        assert len(doc["educations"]) == 1
        assert doc["skills"] == ["Python", "FastAPI", "SQL"]

    def test_period_formatted(self):
        doc = build_resume_document(_sample_profile())
        assert doc["experiences"][0]["period"] == "Yanvar 2022 – May 2026"

    def test_uzbek_profile_period(self):
        doc = build_resume_document(_uzbek_profile())
        assert doc["experiences"][0]["period"] == "Mart 2021 – Hozir"
        assert doc["educations"][0]["period"] == "Sentabr 2017 – Iyun 2021"

    def test_language_reaches_document(self):
        doc = build_resume_document(_russian_profile(), "ru")
        assert doc["lang"] == "ru"
        assert doc["experiences"][0]["period"] == "Март 2021 – Июнь 2024"

    def test_empty_name_uses_localized_fallback(self):
        assert build_resume_document(ResumeProfileData(), "en")["name"] == "Unnamed candidate"
        assert build_resume_document(ResumeProfileData(), "ru")["name"] == "Без имени"


# ─── template catalogue ───────────────────────────────────────────────────────

class TestTemplates:
    def test_free_templates_are_not_premium(self):
        items = {item.id: item for item in template_items("uz")}
        assert set(items) == set(TEMPLATES)
        for template_id, item in items.items():
            assert item.is_premium == (template_id not in FREE_TEMPLATES)

    def test_titles_localized(self):
        uz = {item.id: item.description for item in template_items("uz")}
        ru = {item.id: item.description for item in template_items("ru")}
        en = {item.id: item.description for item in template_items("en")}
        assert uz["clean"] != ru["clean"] != en["clean"]

    def test_unknown_lang_falls_back_to_uz(self):
        assert template_items("de")[0].description == template_items("uz")[0].description


# ─── PDF generation ───────────────────────────────────────────────────────────

class TestPdfGeneration:
    def test_pdf_markers(self):
        payload = generate_pdf_bytes(build_resume_document(_sample_profile()))
        assert payload.startswith(b"%PDF-")
        assert b"%%EOF" in payload
        assert len(payload) > 5000  # fpdf2 embeds the font subset

    def test_uzbek_chars_do_not_raise(self):
        payload = generate_pdf_bytes(build_resume_document(_uzbek_profile()))
        assert payload.startswith(b"%PDF-")
        assert len(payload) > 5000

    def test_cyrillic_renders(self):
        doc = build_resume_document(_russian_profile(), "ru")
        payload = generate_pdf_bytes(doc, accent_hex="#2563eb", template_id="clean", lang="ru")
        assert payload.startswith(b"%PDF-")
        assert len(payload) > 5000

    def test_accent_colors_accepted(self):
        doc = build_resume_document(_sample_profile())
        for color in ("#2563eb", "#7c3aed", "#111827"):
            assert generate_pdf_bytes(doc, accent_hex=color).startswith(b"%PDF-")

    @pytest.mark.parametrize("template_id", sorted(TEMPLATES))
    def test_every_template_renders(self, template_id):
        doc = build_resume_document(_uzbek_profile())
        payload = generate_pdf_bytes(doc, accent_hex="#0f766e", template_id=template_id)
        assert payload.startswith(b"%PDF-")
        assert b"%%EOF" in payload

    @pytest.mark.parametrize("lang", ["uz", "ru", "en"])
    def test_every_language_renders(self, lang):
        doc = build_resume_document(_russian_profile(), lang)
        payload = generate_pdf_bytes(doc, template_id="executive", lang=lang)
        assert payload.startswith(b"%PDF-")

    def test_unknown_template_uses_classic_renderer(self):
        doc = build_resume_document(_sample_profile())
        assert generate_pdf_bytes(doc, template_id="does-not-exist").startswith(b"%PDF-")

    @pytest.mark.parametrize("template_id", ["photo_classic", "photo_sidebar", "europass"])
    def test_photo_templates_embed_prefetched_bytes(self, template_id):
        """The router pre-fetches the photo; renderers must consume doc['photo_bytes']."""
        pil = pytest.importorskip("PIL.Image")
        buffer = io.BytesIO()
        pil.new("RGB", (240, 300), (40, 90, 160)).save(buffer, format="PNG")

        doc = build_resume_document(_sample_profile())
        doc["photo_url"] = "https://t.me/i/userpic/320/test.jpg"
        doc["photo_bytes"] = buffer.getvalue()
        payload = generate_pdf_bytes(doc, template_id=template_id)
        assert payload.startswith(b"%PDF-")

    def test_render_failure_propagates(self):
        """There is no silent ASCII fallback any more — failures must raise."""
        with pytest.raises(Exception):
            generate_pdf_bytes({"name": "X", "experiences": [None]}, template_id="clean")


# ─── photo policy ─────────────────────────────────────────────────────────────

class TestPhotoHostPolicy:
    @pytest.mark.parametrize(
        "url",
        [
            "https://t.me/i/userpic/320/abc.jpg",
            "https://cdn4.telesco.pe/file/abc.jpg",
            "https://api.telegram.org/file/bot123/photos/x.jpg",
        ],
    )
    def test_allowed(self, url):
        assert is_allowed_photo_host(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.example.com/x.jpg",
            "http://t.me/x.jpg",
            "https://127.0.0.1/x.jpg",
            "https://t.me.evil.com/x.jpg",
            "",
        ],
    )
    def test_blocked(self, url):
        assert is_allowed_photo_host(url) is False
