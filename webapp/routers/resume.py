import html
import io
import json
import re
import time
import zipfile
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.identity import resolve_user_id_from_init_data
from webapp.core.limiter import limiter
from webapp.core.session import get_optional_current_user

router = APIRouter(prefix="/resume", tags=["resume"])


class ResumeExperienceItem(BaseModel):
    role: str = Field(default="", max_length=120)
    company: str = Field(default="", max_length=120)
    start_date: str = Field(default="", max_length=30)
    end_date: str = Field(default="", max_length=30)
    location: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=2400)


class ResumeEducationItem(BaseModel):
    school: str = Field(default="", max_length=160)
    degree: str = Field(default="", max_length=160)
    start_date: str = Field(default="", max_length=30)
    end_date: str = Field(default="", max_length=30)
    description: str = Field(default="", max_length=1600)


class ResumeProfileData(BaseModel):
    full_name: str = Field(default="", max_length=120)
    position: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=80)
    email: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    website: str = Field(default="", max_length=240)
    summary: str = Field(default="", max_length=2400)
    experiences: list[ResumeExperienceItem] = Field(default_factory=list, max_length=12)
    educations: list[ResumeEducationItem] = Field(default_factory=list, max_length=8)
    skills: list[str] = Field(default_factory=list, max_length=40)
    languages: list[str] = Field(default_factory=list, max_length=20)


class ResumeProfileResponse(BaseModel):
    profile: ResumeProfileData
    selected_template: str
    accent_color: str
    updated_at: int | None = None


class ResumeProfileUpsertRequest(BaseModel):
    profile: ResumeProfileData
    selected_template: str = "clean"
    accent_color: str | None = None


class ResumeTemplateItem(BaseModel):
    id: str
    title: str
    description: str
    supports_color: bool = True
    supports_sidebar: bool = False
    supports_photo: bool = False
    preview_variant: str = "single"
    palette: list[str] = Field(default_factory=list)


class ResumeTemplatesResponse(BaseModel):
    items: list[ResumeTemplateItem]


class ResumeSendRequest(BaseModel):
    template_id: str


class ResumeSendResponse(BaseModel):
    ok: bool
    message: str


class ResumeExportRequest(BaseModel):
    format: Literal["pdf", "docx"] = "pdf"
    template_id: str | None = None


class ResumeEventRequest(BaseModel):
    event_name: str = Field(min_length=2, max_length=64)
    step: str | None = Field(default=None, max_length=64)
    meta_json: str | None = Field(default=None, max_length=2000)


TEMPLATES: dict[str, ResumeTemplateItem] = {
    "clean": ResumeTemplateItem(
        id="clean",
        title="Clean Classic",
        description="Soddaroq klassik ko'rinish, barcha sohalar uchun.",
        supports_color=True,
        preview_variant="single",
        palette=["#0f766e", "#2563eb", "#b45309", "#be123c", "#374151"],
    ),
    "modern": ResumeTemplateItem(
        id="modern",
        title="Modern Accent",
        description="Qisqa va zamonaviy blokli uslub.",
        supports_color=True,
        supports_sidebar=True,
        supports_photo=True,
        preview_variant="split",
        palette=["#2563eb", "#7c3aed", "#0f766e", "#ea580c", "#334155"],
    ),
    "compact": ResumeTemplateItem(
        id="compact",
        title="Compact One-Page",
        description="Bir sahifaga sig'adigan ixcham format.",
        supports_color=False,
        preview_variant="mono",
        palette=["#111827"],
    ),
}

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
IDEMPOTENCY_RE = re.compile(r"^[a-zA-Z0-9_.:-]{8,120}$")
MAX_PROFILE_BYTES = 64 * 1024


def _default_profile(first_name: str) -> ResumeProfileData:
    return ResumeProfileData(full_name=first_name)


def _normalize_items(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def _safe_text(value: str) -> str:
    return html.escape(value or "")


def _normalize_color(raw: str | None, template_id: str) -> str:
    template = TEMPLATES.get(template_id)
    if not template:
        return "#0f766e"

    if not template.supports_color:
        return template.palette[0] if template.palette else "#111827"

    color = str(raw or "").strip()
    if HEX_COLOR_RE.match(color):
        return color.lower()
    return (template.palette[0] if template.palette else "#0f766e").lower()


def _normalize_experiences(values: list[ResumeExperienceItem]) -> list[ResumeExperienceItem]:
    out: list[ResumeExperienceItem] = []
    for item in values:
        normalized = ResumeExperienceItem(
            role=str(item.role or "").strip(),
            company=str(item.company or "").strip(),
            start_date=str(item.start_date or "").strip(),
            end_date=str(item.end_date or "").strip(),
            location=str(item.location or "").strip(),
            description=str(item.description or "").strip(),
        )
        if any([normalized.role, normalized.company, normalized.start_date, normalized.end_date, normalized.location, normalized.description]):
            out.append(normalized)
    return out


def _normalize_educations(values: list[ResumeEducationItem]) -> list[ResumeEducationItem]:
    out: list[ResumeEducationItem] = []
    for item in values:
        normalized = ResumeEducationItem(
            school=str(item.school or "").strip(),
            degree=str(item.degree or "").strip(),
            start_date=str(item.start_date or "").strip(),
            end_date=str(item.end_date or "").strip(),
            description=str(item.description or "").strip(),
        )
        if any([normalized.school, normalized.degree, normalized.start_date, normalized.end_date, normalized.description]):
            out.append(normalized)
    return out


def _normalize_profile_from_payload(raw: dict, first_name_fallback: str) -> ResumeProfileData:
    if not isinstance(raw, dict):
        raw = {}

    # Legacy compatibility: old schema had plain experience/education text fields.
    legacy_experience = str(raw.get("experience") or "").strip()
    legacy_education = str(raw.get("education") or "").strip()

    experiences_raw = raw.get("experiences") if isinstance(raw.get("experiences"), list) else []
    educations_raw = raw.get("educations") if isinstance(raw.get("educations"), list) else []

    experiences: list[ResumeExperienceItem] = []
    for item in experiences_raw:
        if isinstance(item, dict):
            experiences.append(ResumeExperienceItem(**item))
    if not experiences and legacy_experience:
        experiences = [ResumeExperienceItem(description=legacy_experience)]

    educations: list[ResumeEducationItem] = []
    for item in educations_raw:
        if isinstance(item, dict):
            educations.append(ResumeEducationItem(**item))
    if not educations and legacy_education:
        educations = [ResumeEducationItem(description=legacy_education)]

    profile = ResumeProfileData(
        full_name=str(raw.get("full_name") or first_name_fallback),
        position=str(raw.get("position") or ""),
        phone=str(raw.get("phone") or ""),
        email=str(raw.get("email") or ""),
        location=str(raw.get("location") or ""),
        website=str(raw.get("website") or ""),
        summary=str(raw.get("summary") or ""),
        experiences=experiences,
        educations=educations,
        skills=[str(x) for x in (raw.get("skills") or []) if str(x).strip()],
        languages=[str(x) for x in (raw.get("languages") or []) if str(x).strip()],
    )

    return ResumeProfileData(
        full_name=profile.full_name.strip(),
        position=profile.position.strip(),
        phone=profile.phone.strip(),
        email=profile.email.strip(),
        location=profile.location.strip(),
        website=profile.website.strip(),
        summary=profile.summary.strip(),
        experiences=_normalize_experiences(profile.experiences),
        educations=_normalize_educations(profile.educations),
        skills=_normalize_items(profile.skills),
        languages=_normalize_items(profile.languages),
    )


def _render_lines(values: list[str]) -> str:
    cleaned = _normalize_items(values)
    if not cleaned:
        return "<p class='muted'>Ko'rsatilmagan</p>"
    rows = "".join(f"<li>{_safe_text(item)}</li>" for item in cleaned)
    return f"<ul>{rows}</ul>"


def _build_resume_document(profile: ResumeProfileData) -> dict:
    contacts = [x for x in [profile.phone, profile.email, profile.location, profile.website] if (x or "").strip()]
    experiences = [
        {
            "title": " / ".join([x for x in [item.role, item.company] if x]) or "Lavozim",
            "period": " - ".join([x for x in [item.start_date, item.end_date] if x]).strip(" -"),
            "location": item.location,
            "description": item.description,
        }
        for item in profile.experiences
    ]
    educations = [
        {
            "title": " / ".join([x for x in [item.school, item.degree] if x]) or "Ta'lim",
            "period": " - ".join([x for x in [item.start_date, item.end_date] if x]).strip(" -"),
            "description": item.description,
        }
        for item in profile.educations
    ]
    return {
        "name": profile.full_name or "Nomsiz nomzod",
        "position": profile.position or "Lavozim ko'rsatilmagan",
        "contacts": contacts,
        "summary": profile.summary or "Qisqacha ma'lumot kiritilmagan",
        "experiences": experiences,
        "educations": educations,
        "skills": profile.skills,
        "languages": profile.languages,
    }


def _document_to_lines(doc: dict) -> list[str]:
    lines: list[str] = []
    lines.append(str(doc.get("name") or "Nomsiz nomzod"))
    lines.append(str(doc.get("position") or "Lavozim"))
    contacts = doc.get("contacts") or []
    if contacts:
        lines.append(" | ".join(str(x) for x in contacts))
    lines.append("")
    lines.append("QISQACHA")
    lines.extend(str(doc.get("summary") or "").splitlines() or ["-"])
    lines.append("")
    lines.append("TAJRIBA")
    for item in doc.get("experiences") or []:
        lines.append(f"- {item.get('title')}")
        period = " | ".join([x for x in [item.get("location"), item.get("period")] if x])
        if period:
            lines.append(f"  {period}")
        for part in str(item.get("description") or "").splitlines():
            if part.strip():
                lines.append(f"  {part.strip()}")
    lines.append("")
    lines.append("TA'LIM")
    for item in doc.get("educations") or []:
        lines.append(f"- {item.get('title')}")
        if item.get("period"):
            lines.append(f"  {item.get('period')}")
        for part in str(item.get("description") or "").splitlines():
            if part.strip():
                lines.append(f"  {part.strip()}")
    lines.append("")
    lines.append("KO'NIKMALAR")
    skills = doc.get("skills") or []
    lines.append(", ".join(str(x) for x in skills) if skills else "-")
    lines.append("")
    lines.append("TILLAR")
    langs = doc.get("languages") or []
    lines.append(", ".join(str(x) for x in langs) if langs else "-")
    return lines


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _generate_pdf_bytes(doc: dict, title: str) -> bytes:
    lines = _document_to_lines(doc)[:90]
    y_start = 795
    content_parts = ["BT", "/F1 11 Tf", f"50 {y_start} Td"]
    for line in lines:
        content_parts.append(f"({_pdf_escape(line[:140])}) Tj")
        content_parts.append("T*")
    content_parts.append("ET")
    stream = "\n".join(content_parts).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n")
    objects.append(b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n")
    objects.append(f"4 0 obj << /Length {len(stream)} >> stream\n".encode("latin-1") + stream + b"\nendstream endobj\n")
    objects.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(result))
        result.extend(obj)

    xref_start = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    result.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        result.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    result.extend(
        (
            "trailer\n"
            f"<< /Size {len(offsets)} /Root 1 0 R /Info << /Title ({_pdf_escape(title)}) >> >>\n"
            f"startxref\n{xref_start}\n%%EOF"
        ).encode("latin-1", errors="replace")
    )
    return bytes(result)


def _generate_docx_bytes(doc: dict, title: str) -> bytes:
    def p(text: str) -> str:
        return f"<w:p><w:r><w:t xml:space='preserve'>{html.escape(text)}</w:t></w:r></w:p>"

    lines = _document_to_lines(doc)
    body = "".join(p(line) for line in lines)
    document_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
        f"<w:body>{body}<w:sectPr/></w:body></w:document>"
    )
    content_types = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
        "<Default Extension='xml' ContentType='application/xml'/>"
        "<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
        "<Override PartName='/docProps/core.xml' ContentType='application/vnd.openxmlformats-package.core-properties+xml'/>"
        "<Override PartName='/docProps/app.xml' ContentType='application/vnd.openxmlformats-officedocument.extended-properties+xml'/>"
        "</Types>"
    )
    rels = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/>"
        "<Relationship Id='rId2' Type='http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties' Target='docProps/core.xml'/>"
        "<Relationship Id='rId3' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties' Target='docProps/app.xml'/>"
        "</Relationships>"
    )
    core_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<cp:coreProperties xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties' "
        "xmlns:dc='http://purl.org/dc/elements/1.1/' xmlns:dcterms='http://purl.org/dc/terms/' "
        "xmlns:dcmitype='http://purl.org/dc/dcmitype/' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'>"
        f"<dc:title>{html.escape(title)}</dc:title><dc:creator>Vakant3</dc:creator></cp:coreProperties>"
    )
    app_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/extended-properties' "
        "xmlns:vt='http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes'>"
        "<Application>Vakant3</Application></Properties>"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", app_xml)
    return buffer.getvalue()


async def _create_export_row(db, user_id: int, fmt: str, template_id: str, status: str = "pending") -> int:
    now = int(time.time())
    cursor = await db.execute(
        """
        INSERT INTO resume_exports (user_id, fmt, template_id, status, error_text, created_at, completed_at)
        VALUES (?, ?, ?, ?, NULL, ?, NULL)
        """,
        (user_id, fmt, template_id, status, now),
    )
    return int(cursor.lastrowid)


async def _complete_export_row(db, export_id: int, status: str, error_text: str | None = None) -> None:
    now = int(time.time())
    await db.execute(
        """
        UPDATE resume_exports
        SET status = ?, error_text = ?, completed_at = ?
        WHERE id = ?
        """,
        (status, error_text, now, export_id),
    )


def _render_experience_blocks(values: list[ResumeExperienceItem]) -> str:
    if not values:
        return "<p class='muted'>Tajriba kiritilmagan</p>"

    blocks = []
    for item in values:
        period = " - ".join([x for x in [item.start_date, item.end_date] if x]).strip(" -")
        head_left = " / ".join([x for x in [item.role, item.company] if x]) or "Lavozim"
        head_right = " | ".join([x for x in [item.location, period] if x])
        blocks.append(
            """
            <div class='entry'>
              <div class='entry-head'>
                <strong>{left}</strong>
                <span>{right}</span>
              </div>
              <p class='block'>{desc}</p>
            </div>
            """.format(left=_safe_text(head_left), right=_safe_text(head_right), desc=_safe_text(item.description or ""))
        )
    return "".join(blocks)


def _render_education_blocks(values: list[ResumeEducationItem]) -> str:
    if not values:
        return "<p class='muted'>Ta'lim ma'lumoti kiritilmagan</p>"

    blocks = []
    for item in values:
        period = " - ".join([x for x in [item.start_date, item.end_date] if x]).strip(" -")
        head_left = " / ".join([x for x in [item.school, item.degree] if x]) or "Ta'lim"
        blocks.append(
            """
            <div class='entry'>
              <div class='entry-head'>
                <strong>{left}</strong>
                <span>{right}</span>
              </div>
              <p class='block'>{desc}</p>
            </div>
            """.format(left=_safe_text(head_left), right=_safe_text(period), desc=_safe_text(item.description or ""))
        )
    return "".join(blocks)


def _render_resume_html(profile: ResumeProfileData, template_id: str, accent_color: str) -> str:
    doc = _build_resume_document(profile)
    palette = {
        "clean": {"accent": "#0f766e", "bg": "#f8fafc"},
        "modern": {"accent": "#2563eb", "bg": "#f8fafc"},
        "compact": {"accent": "#111827", "bg": "#ffffff"},
    }.get(template_id, {"accent": "#0f766e", "bg": "#f8fafc"})

    palette["accent"] = accent_color

    contact_parts = [str(part).strip() for part in (doc.get("contacts") or []) if str(part).strip()]
    contact_line = " | ".join(_safe_text(part) for part in contact_parts) or "Kontakt kiritilmagan"

    return f"""
<!doctype html>
<html lang=\"uz\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Resume - {_safe_text(str(doc.get('name') or profile.full_name))}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: {palette['bg']}; color: #0f172a; }}
    .page {{ max-width: 850px; margin: 24px auto; background: #fff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; }}
    .head {{ padding: 28px; background: linear-gradient(135deg, {palette['accent']}, #0f172a); color: #fff; }}
    .head h1 {{ margin: 0 0 4px 0; font-size: 30px; }}
    .head p {{ margin: 0; opacity: 0.9; }}
    .section {{ padding: 18px 24px; border-top: 1px solid #e2e8f0; }}
    .section h2 {{ margin: 0 0 10px 0; font-size: 16px; color: {palette['accent']}; text-transform: uppercase; letter-spacing: .08em; }}
    .muted {{ color: #64748b; margin: 0; }}
    .entry {{ margin-bottom: 12px; }}
    .entry-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: baseline; font-size: 14px; color: #111827; }}
    .entry-head span {{ color: #64748b; font-size: 12px; }}
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin: 4px 0; }}
    .block {{ white-space: pre-wrap; line-height: 1.5; margin: 4px 0 0; }}
  </style>
</head>
<body>
  <main class=\"page\">
    <header class=\"head\">
    <h1>{_safe_text(str(doc.get('name') or 'Nomsiz nomzod'))}</h1>
    <p>{_safe_text(str(doc.get('position') or 'Lavozim ko\'rsatilmagan'))}</p>
      <p>{contact_line}</p>
    </header>

    <section class=\"section\">
      <h2>Qisqacha</h2>
    <p class=\"block\">{_safe_text(str(doc.get('summary') or 'Qisqacha ma\'lumot kiritilmagan'))}</p>
    </section>

    <section class=\"section\">
      <h2>Tajriba</h2>
      {_render_experience_blocks(profile.experiences)}
    </section>

    <section class=\"section\">
      <h2>Ta'lim</h2>
      {_render_education_blocks(profile.educations)}
    </section>

    <section class=\"section\">
      <h2>Ko'nikmalar</h2>
      {_render_lines(profile.skills)}
    </section>

    <section class=\"section\">
      <h2>Tillar</h2>
      {_render_lines(profile.languages)}
    </section>
  </main>
</body>
</html>
""".strip()


async def _load_resume_row(db, user_id: int):
    cursor = await db.execute(
        "SELECT profile_json, selected_template, updated_at FROM resume_profiles WHERE user_id = ?",
        (user_id,),
    )
    return await cursor.fetchone()


async def _get_idempotent_response(db, user_id: int, action: str, key: str) -> ResumeProfileResponse | None:
    cursor = await db.execute(
        """
        SELECT response_json FROM resume_idempotency
        WHERE idempotency_key = ? AND user_id = ? AND action = ?
        """,
        (key, user_id, action),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    try:
        payload = json.loads(str(row["response_json"] or "{}"))
        return ResumeProfileResponse(**payload)
    except Exception:
        return None


async def _save_idempotent_response(db, user_id: int, action: str, key: str, response_obj: ResumeProfileResponse) -> None:
    await db.execute(
        """
        INSERT OR REPLACE INTO resume_idempotency (idempotency_key, user_id, action, response_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            key,
            user_id,
            action,
            json.dumps(response_obj.model_dump(), ensure_ascii=False),
            int(time.time()),
        ),
    )


async def _resolve_user_from_request(request: Request, db) -> dict:
    auth_header = request.headers.get("Authorization")
    optional = await get_optional_current_user(authorization=auth_header, db=db)
    if optional and optional.get("user"):
        return optional["user"]

    settings = get_settings()
    init_data = (request.headers.get("X-Telegram-Init-Data") or "").strip()
    user_id: int | None = None
    if init_data:
        user_id = resolve_user_id_from_init_data(init_data, settings.TOKEN)

    # Final fallback for Telegram WebView edge-cases where initData can be empty.
    if not user_id:
        fallback_user_id = (request.headers.get("X-Telegram-User-Id") or "").strip()
        if fallback_user_id.isdigit():
            user_id = int(fallback_user_id)

    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    cursor = await db.execute(
        "SELECT user_id, lang, first_name, username, photo_url, date, region, district, specs, money FROM users WHERE user_id = ?",
        (int(user_id),),
    )
    user_row = await cursor.fetchone()
    if user_row:
        return dict(user_row)

    now = int(time.time())
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, date, lang) VALUES (?, ?, ?)",
        (int(user_id), now, "uz"),
    )
    await db.commit()
    cursor = await db.execute(
        "SELECT user_id, lang, first_name, username, photo_url, date, region, district, specs, money FROM users WHERE user_id = ?",
        (int(user_id),),
    )
    user_row = await cursor.fetchone()
    if not user_row:
        raise HTTPException(status_code=401, detail="User not found")
    return dict(user_row)


@router.get("/templates", response_model=ResumeTemplatesResponse)
async def get_templates() -> ResumeTemplatesResponse:
    return ResumeTemplatesResponse(items=list(TEMPLATES.values()))


@router.get("/profile", response_model=ResumeProfileResponse)
@limiter.limit("120/minute")
async def get_profile(request: Request, db=Depends(get_db)) -> ResumeProfileResponse:
    user = await _resolve_user_from_request(request, db)
    user_id = int(user["user_id"])
    row = await _load_resume_row(db, user_id)

    if not row:
        return ResumeProfileResponse(
            profile=_default_profile(str(user.get("first_name") or "")),
            selected_template="clean",
            accent_color="#0f766e",
            updated_at=None,
        )

    try:
        payload = json.loads(str(row["profile_json"] or "{}"))
    except Exception:
        payload = {}

    selected_template = str(row["selected_template"] or "clean")
    profile = _normalize_profile_from_payload(payload, str(user.get("first_name") or ""))
    accent_color = _normalize_color(payload.get("accent_color") if isinstance(payload, dict) else None, selected_template)

    return ResumeProfileResponse(
        profile=profile,
        selected_template=selected_template,
        accent_color=accent_color,
        updated_at=int(row["updated_at"] or 0),
    )


@router.put("/profile", response_model=ResumeProfileResponse)
@limiter.limit("30/minute")
async def put_profile(payload: ResumeProfileUpsertRequest, request: Request, db=Depends(get_db)) -> ResumeProfileResponse:
    user = await _resolve_user_from_request(request, db)
    user_id = int(user["user_id"])
    idempotency_key = (request.headers.get("X-Idempotency-Key") or "").strip()
    if idempotency_key:
        if not IDEMPOTENCY_RE.match(idempotency_key):
            raise HTTPException(status_code=400, detail="Invalid idempotency key")
        cached = await _get_idempotent_response(db, user_id, "resume_profile_save", idempotency_key)
        if cached:
            return cached

    template_id = (payload.selected_template or "clean").strip().lower()
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown template")

    normalized_profile = ResumeProfileData(
        full_name=str(payload.profile.full_name or "").strip(),
        position=str(payload.profile.position or "").strip(),
        phone=str(payload.profile.phone or "").strip(),
        email=str(payload.profile.email or "").strip(),
        location=str(payload.profile.location or "").strip(),
        website=str(payload.profile.website or "").strip(),
        summary=str(payload.profile.summary or "").strip(),
        experiences=_normalize_experiences(payload.profile.experiences),
        educations=_normalize_educations(payload.profile.educations),
        skills=_normalize_items(payload.profile.skills),
        languages=_normalize_items(payload.profile.languages),
    )

    accent_color = _normalize_color(payload.accent_color, template_id)

    now = int(time.time())
    profile_json = json.dumps(
        {
            **normalized_profile.model_dump(),
            "accent_color": accent_color,
        },
        ensure_ascii=False,
    )
    if len(profile_json.encode("utf-8")) > MAX_PROFILE_BYTES:
        raise HTTPException(status_code=413, detail="Resume payload too large")

    await db.execute(
        """
        INSERT INTO resume_profiles (user_id, profile_json, selected_template, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            profile_json = excluded.profile_json,
            selected_template = excluded.selected_template,
            updated_at = excluded.updated_at
        """,
        (user_id, profile_json, template_id, now),
    )
    response_obj = ResumeProfileResponse(
        profile=normalized_profile,
        selected_template=template_id,
        accent_color=accent_color,
        updated_at=now,
    )
    if idempotency_key:
        await _save_idempotent_response(db, user_id, "resume_profile_save", idempotency_key, response_obj)
    await db.commit()

    return response_obj


@router.post("/send-telegram", response_model=ResumeSendResponse)
@limiter.limit("10/minute")
async def send_resume_to_telegram(payload: ResumeSendRequest, request: Request, db=Depends(get_db)) -> ResumeSendResponse:
    user = await _resolve_user_from_request(request, db)
    user_id = int(user["user_id"])
    template_id = (payload.template_id or "").strip().lower()
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown template")

    row = await _load_resume_row(db, user_id)
    if not row:
        profile = _default_profile(str(user.get("first_name") or ""))
    else:
        try:
            raw_payload = json.loads(str(row["profile_json"] or "{}"))
        except Exception:
            raw_payload = {}
        profile = _normalize_profile_from_payload(raw_payload, str(user.get("first_name") or ""))

    doc = _build_resume_document(profile)
    file_name = f"resume_{template_id}_{user_id}.pdf"
    export_id = await _create_export_row(db, user_id, "pdf", template_id, "pending")
    await db.commit()

    settings = get_settings()
    if not settings.TOKEN:
        raise HTTPException(status_code=500, detail="Bot token missing")

    endpoint = f"https://api.telegram.org/bot{settings.TOKEN}/sendDocument"
    caption = "Resume tayyor. Faylni yuklab olib ishlatishingiz mumkin."
    file_bytes = _generate_pdf_bytes(doc, str(doc.get("name") or "Resume"))

    response = None
    for _ in range(2):
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                endpoint,
                data={"chat_id": str(user_id), "caption": caption},
                files={"document": (file_name, file_bytes, "application/pdf")},
            )
        if response.status_code < 500:
            break

    if response is None or response.status_code >= 400:
        await _complete_export_row(db, export_id, "failed", "telegram_http_error")
        await db.commit()
        raise HTTPException(status_code=502, detail="Telegramga yuborishda xatolik")

    body = response.json() if response.content else {}
    if not body.get("ok"):
        await _complete_export_row(db, export_id, "failed", "telegram_api_error")
        await db.commit()
        raise HTTPException(status_code=502, detail="Telegram API xatolik qaytardi")

    await _complete_export_row(db, export_id, "completed")
    await db.commit()

    return ResumeSendResponse(ok=True, message="Resume Telegramga yuborildi")


@router.post("/export")
@limiter.limit("20/minute")
async def export_resume(payload: ResumeExportRequest, request: Request, db=Depends(get_db)) -> Response:
    user = await _resolve_user_from_request(request, db)
    user_id = int(user["user_id"])
    row = await _load_resume_row(db, user_id)

    template_id = (payload.template_id or "").strip().lower() or (str(row["selected_template"] or "clean") if row else "clean")
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown template")

    if not row:
        profile = _default_profile(str(user.get("first_name") or ""))
    else:
        try:
            raw_payload = json.loads(str(row["profile_json"] or "{}"))
        except Exception:
            raw_payload = {}
        profile = _normalize_profile_from_payload(raw_payload, str(user.get("first_name") or ""))

    doc = _build_resume_document(profile)
    export_id = await _create_export_row(db, user_id, payload.format, template_id, "pending")
    await db.commit()

    try:
        if payload.format == "pdf":
            file_bytes = _generate_pdf_bytes(doc, str(doc.get("name") or "Resume"))
            filename = f"resume_{template_id}_{user_id}.pdf"
            content_type = "application/pdf"
        else:
            file_bytes = _generate_docx_bytes(doc, str(doc.get("name") or "Resume"))
            filename = f"resume_{template_id}_{user_id}.docx"
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    except Exception:
        await _complete_export_row(db, export_id, "failed", "export_generation_error")
        await db.commit()
        raise HTTPException(status_code=500, detail="Export generation failed")

    await _complete_export_row(db, export_id, "completed")
    await db.commit()

    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/events", response_model=ResumeSendResponse)
@limiter.limit("60/minute")
async def track_resume_event(payload: ResumeEventRequest, request: Request, db=Depends(get_db)) -> ResumeSendResponse:
    user = await _resolve_user_from_request(request, db)
    user_id = int(user["user_id"])
    now = int(time.time())
    await db.execute(
        """
        INSERT INTO resume_events (user_id, event_name, step, meta_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            payload.event_name.strip().lower(),
            (payload.step or "").strip().lower() or None,
            payload.meta_json,
            now,
        ),
    )
    await db.commit()
    return ResumeSendResponse(ok=True, message="Event logged")
