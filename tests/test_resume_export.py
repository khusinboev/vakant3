from webapp.routers.resume import (
    ResumeEducationItem,
    ResumeExperienceItem,
    ResumeProfileData,
    _build_resume_document,
    _generate_docx_bytes,
    _generate_pdf_bytes,
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


def test_resume_document_model_contains_expected_fields():
    doc = _build_resume_document(_sample_profile())
    assert doc["name"] == "Test Candidate"
    assert doc["position"] == "Backend Engineer"
    assert "test@example.com" in doc["contacts"]
    assert len(doc["experiences"]) == 1
    assert len(doc["educations"]) == 1
    assert doc["skills"] == ["Python", "FastAPI", "SQL"]


def test_pdf_generation_has_pdf_signature_and_content():
    doc = _build_resume_document(_sample_profile())
    payload = _generate_pdf_bytes(doc, "Resume Test")
    assert payload.startswith(b"%PDF-1.4")
    assert b"startxref" in payload
    assert len(payload) > 300


def test_docx_generation_has_zip_signature_and_required_parts():
    doc = _build_resume_document(_sample_profile())
    payload = _generate_docx_bytes(doc, "Resume Test")
    assert payload.startswith(b"PK")
    assert b"word/document.xml" in payload
    assert b"[Content_Types].xml" in payload
    assert len(payload) > 500