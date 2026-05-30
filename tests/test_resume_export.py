import zipfile

import pytest

from webapp.routers.resume import (
    ResumeEducationItem,
    ResumeExperienceItem,
    ResumeProfileData,
    _build_resume_document,
    _fmt_date,
    _fmt_period,
    _generate_docx_bytes,
    _generate_pdf_bytes,
    _generate_pdf_fpdf2,
    _generate_pdf_legacy,
    _hex_to_rgb,
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
                description="Built APIs and improved performance.",
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


# ─── _fmt_date / _fmt_period ──────────────────────────────────────────────────

class TestFmtDate:
    def test_mm_yyyy_converted(self):
        assert _fmt_date("05/2023") == "May 2023"

    def test_january(self):
        assert _fmt_date("01/2020") == "Yanvar 2020"

    def test_december(self):
        assert _fmt_date("12/1999") == "Dekabr 1999"

    def test_year_only_passthrough(self):
        assert _fmt_date("2023") == "2023"

    def test_hozir_passthrough(self):
        assert _fmt_date("Hozir") == "Hozir"
        assert _fmt_date("hozir") == "hozir"

    def test_empty_returns_empty(self):
        assert _fmt_date("") == ""

    def test_invalid_month_passthrough(self):
        assert _fmt_date("13/2023") == "13/2023"


class TestFmtPeriod:
    def test_both_parts_formatted(self):
        result = _fmt_period("03/2020", "05/2023")
        assert result == "Mart 2020 – May 2023"

    def test_end_hozir(self):
        result = _fmt_period("01/2022", "Hozir")
        assert result == "Yanvar 2022 – Hozir"

    def test_only_start(self):
        result = _fmt_period("06/2019", "")
        assert result == "Iyun 2019"

    def test_both_empty(self):
        assert _fmt_period("", "") == ""


# ─── _hex_to_rgb ──────────────────────────────────────────────────────────────

class TestHexToRgb:
    def test_green(self):
        assert _hex_to_rgb("#0f766e") == (15, 118, 110)

    def test_blue(self):
        assert _hex_to_rgb("#2563eb") == (37, 99, 235)

    def test_invalid_falls_back(self):
        assert _hex_to_rgb("invalid") == (15, 118, 110)

    def test_without_hash(self):
        assert _hex_to_rgb("111827") == (17, 24, 39)


# ─── Document model ───────────────────────────────────────────────────────────

class TestBuildResumeDocument:
    def test_basic_fields(self):
        doc = _build_resume_document(_sample_profile())
        assert doc["name"] == "Test Candidate"
        assert doc["position"] == "Backend Engineer"
        assert "test@example.com" in doc["contacts"]
        assert len(doc["experiences"]) == 1
        assert len(doc["educations"]) == 1
        assert doc["skills"] == ["Python", "FastAPI", "SQL"]

    def test_period_formatted(self):
        doc = _build_resume_document(_sample_profile())
        # "01/2022" → "Yanvar 2022", "05/2026" → "May 2026"
        assert doc["experiences"][0]["period"] == "Yanvar 2022 – May 2026"

    def test_uzbek_profile_period(self):
        doc = _build_resume_document(_uzbek_profile())
        assert doc["experiences"][0]["period"] == "Mart 2021 – Hozir"
        assert doc["educations"][0]["period"] == "Sentabr 2017 – Iyun 2021"


# ─── PDF generation ───────────────────────────────────────────────────────────

class TestPdfGeneration:
    def test_pdf_starts_with_pdf_marker(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_pdf_bytes(doc, "Resume Test")
        assert payload.startswith(b"%PDF-")

    def test_pdf_ends_with_eof(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_pdf_bytes(doc, "Resume Test")
        assert b"%%EOF" in payload

    def test_pdf_minimum_size(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_pdf_bytes(doc, "Resume Test")
        assert len(payload) > 5000  # fpdf2 embeds fonts, much larger than legacy

    def test_uzbek_chars_do_not_cause_exception(self):
        """Uzbek text must not raise an exception (was corrupted with latin-1 encoding)."""
        doc = _build_resume_document(_uzbek_profile())
        payload = _generate_pdf_bytes(doc, "Ali Rezyumesi")
        assert payload.startswith(b"%PDF-")
        assert len(payload) > 5000

    def test_accent_color_parameter_accepted(self):
        doc = _build_resume_document(_sample_profile())
        for color in ("#2563eb", "#7c3aed", "#111827"):
            payload = _generate_pdf_bytes(doc, "Test", accent_hex=color)
            assert payload.startswith(b"%PDF-")

    def test_fpdf2_path_preferred(self):
        """_generate_pdf_fpdf2 should succeed and return valid PDF bytes."""
        doc = _build_resume_document(_uzbek_profile())
        payload = _generate_pdf_fpdf2(doc, accent_hex="#0f766e")
        assert payload.startswith(b"%PDF-")
        assert b"%%EOF" in payload

    def test_legacy_fallback_still_works(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_pdf_legacy(doc, "Legacy Test")
        assert payload.startswith(b"%PDF-1.4")
        assert b"startxref" in payload


# ─── DOCX generation ─────────────────────────────────────────────────────────

class TestDocxGeneration:
    def test_docx_zip_signature(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_docx_bytes(doc, "Resume Test")
        assert payload.startswith(b"PK")

    def test_docx_has_document_xml(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_docx_bytes(doc, "Resume Test")
        with zipfile.ZipFile(zipfile.io.BytesIO(payload)) as zf:
            names = zf.namelist()
        assert "word/document.xml" in names

    def test_docx_has_word_rels_file(self):
        """OOXML spec requires word/_rels/document.xml.rels — was missing before."""
        doc = _build_resume_document(_sample_profile())
        payload = _generate_docx_bytes(doc, "Resume Test")
        with zipfile.ZipFile(zipfile.io.BytesIO(payload)) as zf:
            names = zf.namelist()
        assert "word/_rels/document.xml.rels" in names

    def test_docx_has_content_types(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_docx_bytes(doc, "Resume Test")
        with zipfile.ZipFile(zipfile.io.BytesIO(payload)) as zf:
            names = zf.namelist()
        assert "[Content_Types].xml" in names

    def test_docx_minimum_size(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_docx_bytes(doc, "Resume Test")
        assert len(payload) > 1000

    def test_docx_uzbek_chars_in_document_xml(self):
        """Uzbek characters must survive in the DOCX document body."""
        doc = _build_resume_document(_uzbek_profile())
        payload = _generate_docx_bytes(doc, "Ali Rezyumesi")
        with zipfile.ZipFile(zipfile.io.BytesIO(payload)) as zf:
            body = zf.read("word/document.xml").decode("utf-8")
        assert "Abdullayev Ali Akbar" in body
        assert "Toshkent" in body

    def test_docx_has_bold_name(self):
        doc = _build_resume_document(_sample_profile())
        payload = _generate_docx_bytes(doc, "Test")
        with zipfile.ZipFile(zipfile.io.BytesIO(payload)) as zf:
            body = zf.read("word/document.xml").decode("utf-8")
        # Name paragraph uses bold rPr
        assert "<w:b/>" in body
        assert "Test Candidate" in body
