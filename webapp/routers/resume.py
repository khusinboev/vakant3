import html
import io
import json
import os
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

_MONTH_NAMES_UZ = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
]
_DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _fmt_date(raw: str) -> str:
    """Convert '05/2023' or '2023' → 'May 2023'; 'Hozir' passthrough."""
    if not raw:
        return ""
    stripped = raw.strip()
    if stripped.lower() in ("hozir", "present", "now"):
        return stripped
    parts = stripped.split("/")
    if len(parts) == 2:
        m_str, y_str = parts
        try:
            m_idx = int(m_str) - 1
            if 0 <= m_idx < 12:
                return f"{_MONTH_NAMES_UZ[m_idx]} {y_str}"
        except ValueError:
            pass
    return stripped


def _fmt_period(start: str, end: str) -> str:
    s = _fmt_date(start or "")
    e = _fmt_date(end or "")
    parts = [x for x in [s, e] if x]
    return " – ".join(parts)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return 15, 118, 110
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 15, 118, 110


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
            # Keep legacy "title" key for backward compat with _document_to_lines
            "title": " / ".join([x for x in [item.role, item.company] if x]) or "Lavozim",
            # Separate fields for rich PDF/DOCX rendering
            "role": item.role or "",
            "company": item.company or "",
            "period": _fmt_period(item.start_date, item.end_date),
            "location": item.location or "",
            "description": item.description or "",
        }
        for item in profile.experiences
    ]
    educations = [
        {
            "title": " / ".join([x for x in [item.school, item.degree] if x]) or "Ta'lim",
            "school": item.school or "",
            "degree": item.degree or "",
            "period": _fmt_period(item.start_date, item.end_date),
            "description": item.description or "",
        }
        for item in profile.educations
    ]
    return {
        "name": profile.full_name or "Nomsiz nomzod",
        "position": profile.position or "",
        "contacts": contacts,
        "summary": profile.summary or "",
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


def _generate_pdf_legacy(doc: dict, title: str) -> bytes:
    """Fallback ASCII-only PDF generator used when fpdf2/fonts are unavailable."""
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


# ---------------------------------------------------------------------------
# Bullet-point parser: converts description text lines into display strings.
# Lines starting with  -, –, •, or *  become bullet items.
# ---------------------------------------------------------------------------

def _parse_bullets(text: str) -> list[str]:
    result: list[str] = []
    for raw in (text or "").splitlines():
        s = raw.strip()
        if not s:
            continue
        if s[0] in ("-", "–", "•", "*"):
            result.append("• " + s.lstrip("-–•* ").strip())
        else:
            result.append(s)
    return result


# ---------------------------------------------------------------------------
# PDF generators — three distinct professional layouts.
# ---------------------------------------------------------------------------

def _generate_pdf_fpdf2(doc: dict, accent_hex: str, template_id: str = "clean") -> bytes:  # noqa: C901
    """Render a polished A4 PDF with fpdf2.

    template_id one of: "clean" (default), "modern" (sidebar), "compact" (dense mono).
    """
    from fpdf import FPDF  # type: ignore[import]

    ar, ag, ab = _hex_to_rgb(accent_hex)

    has_reg = os.path.exists(_DEJAVU_REGULAR)
    has_bld = os.path.exists(_DEJAVU_BOLD)
    fam = "DejaVu" if has_reg else "Helvetica"

    # ── Shared font helpers ──────────────────────────────────────────────────
    def _make_pdf(margin_l: float = 18.0, auto_break_margin: float = 15.0) -> FPDF:
        p = FPDF(orientation="P", unit="mm", format="A4")
        p.set_margins(margin_l, 0, margin_l)
        p.set_auto_page_break(auto=True, margin=auto_break_margin)
        if has_reg:
            p.add_font("DejaVu", fname=_DEJAVU_REGULAR)
        if has_bld:
            p.add_font("DejaVu", style="B", fname=_DEJAVU_BOLD)
        return p

    def sf(p: FPDF, bold: bool = False, size: float = 10.0) -> None:
        p.set_font(fam, style="B" if (bold and has_bld) else "", size=size)

    # ── CLEAN / COMPACT ──────────────────────────────────────────────────────
    if template_id in ("clean", "compact"):
        LM = 18.0
        is_compact = template_id == "compact"
        HDR_H = 40.0 if not is_compact else 0.0   # compact has no colored header
        BODY_BREAK = 12.0 if is_compact else 15.0
        BODY_SZ = 9.0 if is_compact else 9.5
        TITLE_SZ = 8.5 if is_compact else 9.0

        pdf = _make_pdf(LM, BODY_BREAK)
        pdf.add_page()
        UW = pdf.w - 2 * LM  # usable width

        # ── Header block ──────────────────────────────────────────────────
        if not is_compact:
            pdf.set_fill_color(ar, ag, ab)
            pdf.rect(0, 0, pdf.w, HDR_H, "F")
            pdf.set_text_color(255, 255, 255)
            pdf.set_xy(LM, 7)
            sf(pdf, bold=True, size=20)
            pdf.cell(0, 8, str(doc.get("name") or "Nomzod"), new_x="LMARGIN", new_y="NEXT")
            pos_text = str(doc.get("position") or "").strip()
            if pos_text:
                pdf.set_x(LM)
                sf(pdf, size=11)
                pdf.set_text_color(235, 255, 252)
                pdf.cell(0, 5, pos_text, new_x="LMARGIN", new_y="NEXT")
            contacts: list[str] = doc.get("contacts") or []
            if contacts:
                pdf.set_x(LM)
                sf(pdf, size=8.5)
                pdf.set_text_color(200, 240, 235)
                pdf.cell(0, 4, " | ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(15, 23, 42)
            pdf.set_y(HDR_H + 5)
        else:
            # Compact: plain text header block
            pdf.set_text_color(15, 23, 42)
            name_text = str(doc.get("name") or "Nomzod")
            pos_text = str(doc.get("position") or "").strip()
            contacts = doc.get("contacts") or []
            pdf.set_xy(LM, 8)
            sf(pdf, bold=True, size=16)
            if pos_text:
                # Name left, position right
                pdf.cell(UW * 0.58, 7, name_text, new_x="RIGHT")
                sf(pdf, size=10)
                pdf.set_text_color(60, 70, 90)
                pdf.cell(UW * 0.42, 7, pos_text, align="R", new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(0, 7, name_text, new_x="LMARGIN", new_y="NEXT")
            if contacts:
                pdf.set_x(LM)
                sf(pdf, size=8)
                pdf.set_text_color(90, 100, 120)
                pdf.cell(0, 4, " · ".join(str(c) for c in contacts), new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            # Hairline separator
            pdf.set_draw_color(150, 150, 150)
            pdf.set_line_width(0.2)
            pdf.line(LM, pdf.get_y() + 2, pdf.w - LM, pdf.get_y() + 2)
            pdf.set_y(pdf.get_y() + 5)

        # ── Section title helper ──────────────────────────────────────────
        def section(title: str) -> None:
            pdf.set_x(LM)
            sf(pdf, bold=True, size=TITLE_SZ)
            if is_compact:
                pdf.set_text_color(30, 30, 30)
                pdf.set_draw_color(120, 120, 120)
                pdf.set_line_width(0.15)
            else:
                pdf.set_text_color(ar, ag, ab)
                pdf.set_draw_color(ar, ag, ab)
                pdf.set_line_width(0.3)
            pdf.cell(0, 5, title.upper(), new_x="LMARGIN", new_y="NEXT")
            pdf.line(LM, pdf.get_y(), pdf.w - LM, pdf.get_y())
            pdf.set_text_color(15, 23, 42)
            pdf.ln(2)

        # ── Multi-cell body helper ────────────────────────────────────────
        def body(text: str, bold: bool = False, size: float = BODY_SZ, indent: float = 0) -> None:
            if not text:
                return
            pdf.set_x(LM + indent)
            sf(pdf, bold=bold, size=size)
            pdf.multi_cell(UW - indent, 4.8, str(text), new_x="LMARGIN", new_y="NEXT")

        # ── Description with bullet lines ─────────────────────────────────
        def desc_block(text: str) -> None:
            indent = 3.0 if not is_compact else 2.0
            for line in _parse_bullets(text):
                pdf.set_x(LM + indent)
                sf(pdf, size=BODY_SZ)
                pdf.multi_cell(UW - indent, 4.5 if is_compact else 4.8, line,
                               new_x="LMARGIN", new_y="NEXT")

        # ── Summary ───────────────────────────────────────────────────────
        summary = str(doc.get("summary") or "").strip()
        if summary:
            section("Qisqacha")
            body(summary)
            pdf.ln(3 if not is_compact else 2)

        # ── Experience ────────────────────────────────────────────────────
        experiences: list[dict] = doc.get("experiences") or []
        if experiences:
            section("Ish Tajribasi")
            for i, item in enumerate(experiences):
                role = str(item.get("role") or "").strip()
                company = str(item.get("company") or "").strip()
                period = str(item.get("period") or "").strip()
                loc = str(item.get("location") or "").strip()
                desc = str(item.get("description") or "").strip()

                # Role (bold) + Period (right-aligned, muted)
                pdf.set_x(LM)
                sf(pdf, bold=True, size=10.5 if not is_compact else 9.5)
                role_label = role or company or "Lavozim"
                if period:
                    pdf.cell(UW * 0.65, 5.5, role_label, new_x="RIGHT")
                    sf(pdf, size=8)
                    pdf.set_text_color(100, 116, 139)
                    pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(15, 23, 42)
                else:
                    pdf.cell(0, 5.5, role_label, new_x="LMARGIN", new_y="NEXT")

                # Company (italic-style smaller text)
                if company and role:
                    pdf.set_x(LM)
                    sf(pdf, size=9)
                    pdf.set_text_color(55, 80, 115)
                    pdf.cell(0, 4.5, company, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(15, 23, 42)

                # Location
                if loc:
                    pdf.set_x(LM)
                    sf(pdf, size=8)
                    pdf.set_text_color(100, 116, 139)
                    pdf.cell(0, 4, loc, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(15, 23, 42)

                # Description
                if desc:
                    pdf.ln(0.8)
                    desc_block(desc)

                if i < len(experiences) - 1:
                    pdf.ln(2.5 if not is_compact else 1.5)
            pdf.ln(2)

        # ── Education ─────────────────────────────────────────────────────
        educations: list[dict] = doc.get("educations") or []
        if educations:
            section("Ta'lim")
            for i, item in enumerate(educations):
                school = str(item.get("school") or "").strip()
                degree = str(item.get("degree") or "").strip()
                period = str(item.get("period") or "").strip()
                desc = str(item.get("description") or "").strip()
                title_label = school or degree or "Ta'lim"

                pdf.set_x(LM)
                sf(pdf, bold=True, size=10.5 if not is_compact else 9.5)
                if period:
                    pdf.cell(UW * 0.65, 5.5, title_label, new_x="RIGHT")
                    sf(pdf, size=8)
                    pdf.set_text_color(100, 116, 139)
                    pdf.cell(UW * 0.35, 5.5, period, align="R", new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(15, 23, 42)
                else:
                    pdf.cell(0, 5.5, title_label, new_x="LMARGIN", new_y="NEXT")

                if degree and school:
                    pdf.set_x(LM)
                    sf(pdf, size=9)
                    pdf.set_text_color(55, 80, 115)
                    pdf.cell(0, 4.5, degree, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(15, 23, 42)

                if desc:
                    pdf.ln(0.8)
                    desc_block(desc)

                if i < len(educations) - 1:
                    pdf.ln(2 if not is_compact else 1.5)
            pdf.ln(2)

        # ── Skills ────────────────────────────────────────────────────────
        skills: list[str] = doc.get("skills") or []
        if skills:
            section("Ko'nikmalar")
            if is_compact:
                body(", ".join(str(s) for s in skills), size=9)
            else:
                # Render skills as tinted chips in rows
                CHIP_PAD_H, CHIP_PAD_V, CHIP_GAP = 3.0, 1.2, 2.0
                CHIP_H = 5.5
                x_pos = LM
                chip_y = pdf.get_y()
                lr = min(255, ar + 195)
                lg = min(255, ag + 195)
                lb = min(255, ab + 195)
                for skill in skills:
                    sf(pdf, size=8.5)
                    tw = pdf.get_string_width(str(skill)) + CHIP_PAD_H * 2
                    if x_pos + tw > pdf.w - LM:
                        chip_y += CHIP_H + CHIP_GAP
                        x_pos = LM
                    pdf.set_fill_color(lr, lg, lb)
                    pdf.set_draw_color(ar, ag, ab)
                    pdf.set_line_width(0.2)
                    pdf.rect(x_pos, chip_y + CHIP_PAD_V, tw, CHIP_H, "FD")
                    pdf.set_text_color(ar, ag, ab)
                    pdf.set_xy(x_pos + CHIP_PAD_H, chip_y + CHIP_PAD_V + 0.5)
                    pdf.cell(tw - CHIP_PAD_H * 2, CHIP_H - 1, str(skill))
                    pdf.set_text_color(15, 23, 42)
                    x_pos += tw + CHIP_GAP
                pdf.set_y(chip_y + CHIP_H + CHIP_GAP + 2)
            pdf.ln(1)

        # ── Languages ─────────────────────────────────────────────────────
        langs: list[str] = doc.get("languages") or []
        if langs:
            section("Tillar")
            body(", ".join(str(ll) for ll in langs))

        return bytes(pdf.output())

    # ── MODERN (sidebar layout) ──────────────────────────────────────────────
    SB_W = 62.0          # sidebar width mm
    SB_M = 7.0           # sidebar inner margin
    SB_UW = SB_W - SB_M * 2
    MAIN_X = SB_W + 6.0  # main column starts here
    MAIN_W = 210.0 - MAIN_X - 10.0  # right margin 10mm
    MAIN_BRK = 15.0

    # Sidebar background uses header() so it redraws on every page
    class _ModernPDF(FPDF):  # type: ignore[misc]
        _sb_w: float = SB_W
        _sb_rgb: tuple[int, int, int] = (ar, ag, ab)

        def header(self) -> None:  # type: ignore[override]
            self.set_fill_color(*self._sb_rgb)
            self.rect(0, 0, self._sb_w, self.h, "F")

    pdf = _ModernPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=MAIN_BRK)
    pdf.set_margins(SB_W + 6.0, 0, 10.0)
    if has_reg:
        pdf.add_font("DejaVu", fname=_DEJAVU_REGULAR)
    if has_bld:
        pdf.add_font("DejaVu", style="B", fname=_DEJAVU_BOLD)

    pdf.add_page()

    # ── Sidebar helper: track sb_y manually (no auto-break in sidebar) ────
    sb_y = 12.0

    def sb_sf(bold: bool = False, size: float = 8.5) -> None:
        pdf.set_font(fam, style="B" if (bold and has_bld) else "", size=size)

    def sb_set(y: float) -> None:
        pdf.set_xy(SB_M, y)

    def sb_text(text: str, bold: bool = False, size: float = 8.5) -> None:
        nonlocal sb_y
        if sb_y > 270:
            return  # silently clip near bottom
        sb_set(sb_y)
        sb_sf(bold=bold, size=size)
        pdf.set_text_color(230, 245, 242)
        pdf.multi_cell(SB_UW, 4.8, str(text), new_x="LMARGIN", new_y="NEXT")
        sb_y = pdf.get_y() + 0.8

    def sb_section_title(title: str) -> None:
        nonlocal sb_y
        sb_y += 4
        sb_set(sb_y)
        sb_sf(bold=True, size=7.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(SB_UW, 4.5, title.upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.15)
        pdf.line(SB_M, pdf.get_y(), SB_W - SB_M, pdf.get_y())
        sb_y = pdf.get_y() + 2.5
        pdf.set_text_color(225, 242, 240)

    # Sidebar: name + position header
    sb_set(sb_y)
    sb_sf(bold=True, size=14)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(SB_UW, 6.5, str(doc.get("name") or "Nomzod"), new_x="LMARGIN", new_y="NEXT")
    sb_y = pdf.get_y() + 1
    pos_text = str(doc.get("position") or "").strip()
    if pos_text:
        sb_set(sb_y)
        sb_sf(size=9)
        pdf.set_text_color(210, 238, 234)
        pdf.multi_cell(SB_UW, 4.8, pos_text, new_x="LMARGIN", new_y="NEXT")
        sb_y = pdf.get_y() + 3

    # Sidebar: contacts
    contacts_sb: list[str] = doc.get("contacts") or []
    if contacts_sb:
        sb_section_title("Aloqa")
        for c in contacts_sb:
            sb_text(str(c))

    # Sidebar: skills
    skills_sb: list[str] = doc.get("skills") or []
    if skills_sb:
        sb_section_title("Ko'nikmalar")
        for sk in skills_sb[:20]:
            sb_text("• " + str(sk))

    # Sidebar: languages
    langs_sb: list[str] = doc.get("languages") or []
    if langs_sb:
        sb_section_title("Tillar")
        for ll in langs_sb:
            sb_text("• " + str(ll))

    # ── Main column helpers ───────────────────────────────────────────────
    pdf.set_text_color(15, 23, 42)
    main_y = 10.0

    def main_set(y: float) -> None:
        pdf.set_xy(MAIN_X, y)

    def main_section(title: str) -> None:
        nonlocal main_y
        main_y += 4
        main_set(main_y)
        sf(pdf, bold=True, size=9)
        pdf.set_text_color(ar, ag, ab)
        pdf.cell(MAIN_W, 5, title.upper(), new_x="LEFT", new_y="NEXT")
        pdf.set_draw_color(ar, ag, ab)
        pdf.set_line_width(0.3)
        pdf.line(MAIN_X, pdf.get_y(), MAIN_X + MAIN_W, pdf.get_y())
        pdf.set_text_color(15, 23, 42)
        pdf.ln(2)
        main_y = pdf.get_y()

    def main_body(text: str, bold: bool = False, size: float = 9.5) -> None:
        nonlocal main_y
        if not text:
            return
        main_set(main_y)
        sf(pdf, bold=bold, size=size)
        pdf.multi_cell(MAIN_W, 4.8, str(text), new_x="LEFT", new_y="NEXT")
        main_y = pdf.get_y()

    def main_desc(text: str) -> None:
        nonlocal main_y
        for line in _parse_bullets(text):
            main_set(main_y)
            sf(pdf, size=9)
            pdf.multi_cell(MAIN_W - 2, 4.6, line, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()

    # Main: summary
    summary_m = str(doc.get("summary") or "").strip()
    if summary_m:
        main_section("Qisqacha")
        main_body(summary_m)
        main_y += 2

    # Main: experience
    experiences_m: list[dict] = doc.get("experiences") or []
    if experiences_m:
        main_section("Ish Tajribasi")
        for i, item in enumerate(experiences_m):
            role = str(item.get("role") or "").strip()
            company = str(item.get("company") or "").strip()
            period = str(item.get("period") or "").strip()
            loc = str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()

            main_set(main_y)
            sf(pdf, bold=True, size=10)
            role_label = role or company or "Lavozim"
            if period:
                pdf.cell(MAIN_W * 0.65, 5.5, role_label, new_x="RIGHT")
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W * 0.35, 5.5, period, align="R", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(MAIN_W, 5.5, role_label, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()

            if company and role:
                main_set(main_y)
                sf(pdf, size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(MAIN_W, 4.5, company, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()

            if loc:
                main_set(main_y)
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W, 4, loc, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()

            if desc:
                main_y += 0.8
                main_desc(desc)

            if i < len(experiences_m) - 1:
                main_y += 3
        main_y += 2

    # Main: education
    educations_m: list[dict] = doc.get("educations") or []
    if educations_m:
        main_section("Ta'lim")
        for i, item in enumerate(educations_m):
            school = str(item.get("school") or "").strip()
            degree = str(item.get("degree") or "").strip()
            period = str(item.get("period") or "").strip()
            desc = str(item.get("description") or "").strip()
            title_label = school or degree or "Ta'lim"

            main_set(main_y)
            sf(pdf, bold=True, size=10)
            if period:
                pdf.cell(MAIN_W * 0.65, 5.5, title_label, new_x="RIGHT")
                sf(pdf, size=8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(MAIN_W * 0.35, 5.5, period, align="R", new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
            else:
                pdf.cell(MAIN_W, 5.5, title_label, new_x="LEFT", new_y="NEXT")
            main_y = pdf.get_y()

            if degree and school:
                main_set(main_y)
                sf(pdf, size=9)
                pdf.set_text_color(55, 80, 115)
                pdf.cell(MAIN_W, 4.5, degree, new_x="LEFT", new_y="NEXT")
                pdf.set_text_color(15, 23, 42)
                main_y = pdf.get_y()

            if desc:
                main_y += 0.8
                main_desc(desc)

            if i < len(educations_m) - 1:
                main_y += 2

    return bytes(pdf.output())


def _generate_pdf_bytes(doc: dict, title: str, accent_hex: str = "#0f766e",
                        template_id: str = "clean") -> bytes:
    """Generate PDF with Unicode support via fpdf2; falls back to legacy ASCII on error."""
    try:
        return _generate_pdf_fpdf2(doc, accent_hex, template_id=template_id)
    except Exception:
        return _generate_pdf_legacy(doc, title)


# ---------------------------------------------------------------------------
# DOCX generator — fully inline-styled, no external style references.
# ---------------------------------------------------------------------------

def _generate_docx_bytes(doc: dict, title: str, accent_hex: str = "#0f766e") -> bytes:  # noqa: C901
    ar, ag, ab = _hex_to_rgb(accent_hex)
    accent_word = f"{ar:02x}{ag:02x}{ab:02x}"  # e.g. "0f766e"
    _WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    # ── XML building helpers ─────────────────────────────────────────────────
    def _rpr(bold: bool = False, size: int = 20, color: str | None = None,
             italic: bool = False) -> str:
        """Run properties. `size` in half-points (20 = 10 pt)."""
        parts = [
            '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Arial"/>',
            f'<w:sz w:val="{size}"/>',
            f'<w:szCs w:val="{size}"/>',
        ]
        if bold:
            parts.append("<w:b/><w:bCs/>")
        if italic:
            parts.append("<w:i/><w:iCs/>")
        if color:
            parts.append(f'<w:color w:val="{color}"/>')
        return "<w:rPr>" + "".join(parts) + "</w:rPr>"

    def _run(text: str, bold: bool = False, size: int = 20,
             color: str | None = None, italic: bool = False) -> str:
        return (
            f"<w:r>{_rpr(bold=bold, size=size, color=color, italic=italic)}"
            f"<w:t xml:space='preserve'>{html.escape(str(text))}</w:t></w:r>"
        )

    def _para(*runs: str, before: int = 0, after: int = 60,
              indent_l: int = 0, indent_h: int = 0,
              border_bottom: bool = False, shade: str | None = None) -> str:
        spacing = f'<w:spacing w:before="{before}" w:after="{after}"/>'
        ind = f'<w:ind w:left="{indent_l}" w:hanging="{indent_h}"/>' if indent_l or indent_h else ""
        bdr = (
            f'<w:pBdr><w:bottom w:val="single" w:sz="4" w:space="1" w:color="{accent_word}"/></w:pBdr>'
            if border_bottom else ""
        )
        shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>' if shade else ""
        ppr = f"<w:pPr>{spacing}{ind}{bdr}{shd}</w:pPr>"
        return f"<w:p>{ppr}{''.join(runs)}</w:p>"

    def _heading(text: str) -> str:
        """Section heading: bold, accent color, bottom border rule."""
        return _para(
            _run(text.upper(), bold=True, size=18, color=accent_word),
            before=160, after=40, border_bottom=True,
        )

    # ── Document body ────────────────────────────────────────────────────────
    parts: list[str] = []

    # Name (large bold)
    parts.append(_para(
        _run(str(doc.get("name") or "Nomzod"), bold=True, size=36, color="0f172a"),
        before=0, after=40,
    ))

    # Position
    pos = str(doc.get("position") or "").strip()
    if pos:
        parts.append(_para(
            _run(pos, size=24, color="334155", italic=True),
            before=0, after=60,
        ))

    # Contacts
    contacts_d: list[str] = doc.get("contacts") or []
    if contacts_d:
        parts.append(_para(
            _run(" | ".join(str(c) for c in contacts_d), size=18, color="64748b"),
            before=0, after=120,
        ))

    # Accent separator
    parts.append(
        f"<w:p><w:pPr>"
        f"<w:pBdr><w:bottom w:val='single' w:sz='8' w:space='1' w:color='{accent_word}'/></w:pBdr>"
        f"<w:spacing w:before='0' w:after='0'/></w:pPr></w:p>"
    )

    # Summary
    summary_d = str(doc.get("summary") or "").strip()
    if summary_d:
        parts.append(_heading("Qisqacha"))
        for line in summary_d.splitlines():
            if line.strip():
                parts.append(_para(_run(line.strip(), size=20), before=0, after=40))

    # Experience
    experiences_d: list[dict] = doc.get("experiences") or []
    if experiences_d:
        parts.append(_heading("Ish Tajribasi"))
        for item in experiences_d:
            role = str(item.get("role") or "").strip()
            company = str(item.get("company") or "").strip()
            period = str(item.get("period") or "").strip()
            loc = str(item.get("location") or "").strip()
            desc = str(item.get("description") or "").strip()

            # Role + period
            role_label = role or company or "Lavozim"
            period_part = _run(f"    {period}", size=18, color="64748b") if period else ""
            parts.append(_para(
                _run(role_label, bold=True, size=22),
                period_part,
                before=100, after=20,
            ))
            if company and role:
                parts.append(_para(_run(company, size=20, color="374151", italic=True),
                                   before=0, after=20))
            if loc:
                parts.append(_para(_run(loc, size=18, color="64748b"), before=0, after=20))
            for bline in _parse_bullets(desc):
                is_blt = bline.startswith("• ")
                text_b = bline[2:] if is_blt else bline
                bullet_run = _run("• ", size=20, color="64748b") if is_blt else ""
                parts.append(_para(
                    bullet_run, _run(text_b, size=20),
                    before=0, after=20,
                    indent_l=360 if is_blt else 0, indent_h=200 if is_blt else 0,
                ))

    # Education
    educations_d: list[dict] = doc.get("educations") or []
    if educations_d:
        parts.append(_heading("Ta'lim"))
        for item in educations_d:
            school = str(item.get("school") or "").strip()
            degree = str(item.get("degree") or "").strip()
            period = str(item.get("period") or "").strip()
            desc = str(item.get("description") or "").strip()
            title_d = school or degree or "Ta'lim"
            period_part = _run(f"    {period}", size=18, color="64748b") if period else ""
            parts.append(_para(
                _run(title_d, bold=True, size=22),
                period_part,
                before=100, after=20,
            ))
            if degree and school:
                parts.append(_para(_run(degree, size=20, color="374151", italic=True),
                                   before=0, after=20))
            for bline in _parse_bullets(desc):
                parts.append(_para(_run(bline, size=20), before=0, after=20))

    # Skills
    skills_d: list[str] = doc.get("skills") or []
    if skills_d:
        parts.append(_heading("Ko'nikmalar"))
        parts.append(_para(_run(", ".join(str(s) for s in skills_d), size=20),
                           before=0, after=60))

    # Languages
    langs_d: list[str] = doc.get("languages") or []
    if langs_d:
        parts.append(_heading("Tillar"))
        parts.append(_para(_run(", ".join(str(ll) for ll in langs_d), size=20),
                           before=0, after=60))

    # ── DOCX ZIP structure ───────────────────────────────────────────────────
    document_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        f"<w:document xmlns:w='{_WNS}'>"
        "<w:body>"
        + "".join(parts)
        + "<w:sectPr>"
        "<w:pgSz w:w='12240' w:h='15840'/>"
        "<w:pgMar w:top='1134' w:right='1134' w:bottom='1134' w:left='1134'/>"
        "</w:sectPr></w:body></w:document>"
    )

    # Minimal styles (Calibri default, ensures clean render in all Word versions)
    styles_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        f"<w:styles xmlns:w='{_WNS}'>"
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        "<w:rFonts w:ascii='Calibri' w:hAnsi='Calibri'/>"
        "<w:sz w:val='20'/><w:lang w:val='uz-UZ' w:eastAsia='uz-UZ' w:bidi='ar-SA'/>"
        "</w:rPr></w:rPrDefault></w:docDefaults>"
        "<w:style w:type='paragraph' w:default='1' w:styleId='Normal'>"
        "<w:name w:val='Normal'/>"
        "<w:rPr><w:rFonts w:ascii='Calibri' w:hAnsi='Calibri'/><w:sz w:val='20'/></w:rPr>"
        "</w:style>"
        "</w:styles>"
    )

    settings_xml = (
        "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>"
        f"<w:settings xmlns:w='{_WNS}'>"
        "<w:compat>"
        "<w:compatSetting w:name='compatibilityMode'"
        " w:uri='http://schemas.microsoft.com/office/word' w:val='15'/>"
        "</w:compat>"
        "</w:settings>"
    )

    content_types = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
        "<Default Extension='xml' ContentType='application/xml'/>"
        "<Override PartName='/word/document.xml'"
        " ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>"
        "<Override PartName='/word/styles.xml'"
        " ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'/>"
        "<Override PartName='/word/settings.xml'"
        " ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml'/>"
        "<Override PartName='/docProps/core.xml'"
        " ContentType='application/vnd.openxmlformats-package.core-properties+xml'/>"
        "<Override PartName='/docProps/app.xml'"
        " ContentType='application/vnd.openxmlformats-officedocument.extended-properties+xml'/>"
        "</Types>"
    )
    root_rels = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        "<Relationship Id='rId1'"
        " Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument'"
        " Target='word/document.xml'/>"
        "<Relationship Id='rId2'"
        " Type='http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties'"
        " Target='docProps/core.xml'/>"
        "<Relationship Id='rId3'"
        " Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties'"
        " Target='docProps/app.xml'/>"
        "</Relationships>"
    )
    word_rels = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        "<Relationship Id='rId1'"
        " Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles'"
        " Target='styles.xml'/>"
        "<Relationship Id='rId2'"
        " Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings'"
        " Target='settings.xml'/>"
        "</Relationships>"
    )
    core_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<cp:coreProperties"
        " xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties'"
        " xmlns:dc='http://purl.org/dc/elements/1.1/'>"
        f"<dc:title>{html.escape(title)}</dc:title>"
        "<dc:creator>Bandlik.uz</dc:creator>"
        "</cp:coreProperties>"
    )
    app_xml = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'>"
        "<Application>Bandlik.uz Resume Builder</Application>"
        "</Properties>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("word/_rels/document.xml.rels", word_rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/styles.xml", styles_xml)
        zf.writestr("word/settings.xml", settings_xml)
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", app_xml)
    return buf.getvalue()


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
        period = _fmt_period(item.start_date, item.end_date)
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
        period = _fmt_period(item.start_date, item.end_date)
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
        accent_hex = _normalize_color(None, template_id)
    else:
        try:
            raw_payload = json.loads(str(row["profile_json"] or "{}"))
        except Exception:
            raw_payload = {}
        profile = _normalize_profile_from_payload(raw_payload, str(user.get("first_name") or ""))
        accent_hex = _normalize_color(
            raw_payload.get("accent_color") if isinstance(raw_payload, dict) else None,
            template_id,
        )

    doc = _build_resume_document(profile)
    file_name = f"resume_{template_id}_{user_id}.pdf"
    export_id = await _create_export_row(db, user_id, "pdf", template_id, "pending")
    await db.commit()

    settings = get_settings()
    if not settings.TOKEN:
        raise HTTPException(status_code=500, detail="Bot token missing")

    endpoint = f"https://api.telegram.org/bot{settings.TOKEN}/sendDocument"
    caption = "Resume tayyor. Faylni yuklab olib ishlatishingiz mumkin."
    file_bytes = _generate_pdf_bytes(doc, str(doc.get("name") or "Resume"),
                                      accent_hex=accent_hex, template_id=template_id)

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
        accent_hex = _normalize_color(None, template_id)
    else:
        try:
            raw_payload = json.loads(str(row["profile_json"] or "{}"))
        except Exception:
            raw_payload = {}
        profile = _normalize_profile_from_payload(raw_payload, str(user.get("first_name") or ""))
        accent_hex = _normalize_color(
            raw_payload.get("accent_color") if isinstance(raw_payload, dict) else None,
            template_id,
        )

    doc = _build_resume_document(profile)
    export_id = await _create_export_row(db, user_id, payload.format, template_id, "pending")
    await db.commit()

    try:
        if payload.format == "pdf":
            file_bytes = _generate_pdf_bytes(doc, str(doc.get("name") or "Resume"),
                                              accent_hex=accent_hex, template_id=template_id)
            filename = f"resume_{template_id}_{user_id}.pdf"
            content_type = "application/pdf"
        else:
            file_bytes = _generate_docx_bytes(doc, str(doc.get("name") or "Resume"),
                                               accent_hex=accent_hex)
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
