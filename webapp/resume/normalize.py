"""Profile normalization and the render-ready resume document."""

from typing import Any

from webapp.core.i18n import DEFAULT_LANG
from webapp.resume.i18n import fmt_date, fmt_period, t
from webapp.resume.schemas import (
    HEX_COLOR_RE,
    ResumeEducationItem,
    ResumeExperienceItem,
    ResumeProfileData,
    template_palette,
    template_supports_color,
    template_exists,
)

__all__ = [
    "build_resume_document",
    "default_profile",
    "fmt_date",
    "fmt_period",
    "hex_to_rgb",
    "normalize_color",
    "normalize_educations",
    "normalize_experiences",
    "normalize_items",
    "normalize_profile_from_payload",
    "parse_bullets",
]


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return 15, 118, 110
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 15, 118, 110


def parse_bullets(text: str) -> list[str]:
    """Turn a description into display lines; -, –, • or * start a bullet."""
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


def default_profile(first_name: str) -> ResumeProfileData:
    return ResumeProfileData(full_name=first_name)


def normalize_items(items: list[str]) -> list[str]:
    out: list[str] = []
    for item in items:
        value = str(item or "").strip()
        if value and value not in out:
            out.append(value)
    return out


def normalize_color(raw: str | None, template_id: str) -> str:
    if not template_exists(template_id):
        return "#0f766e"

    palette = template_palette(template_id)
    if not template_supports_color(template_id):
        return palette[0] if palette else "#111827"

    color = str(raw or "").strip()
    if HEX_COLOR_RE.match(color):
        return color.lower()
    return (palette[0] if palette else "#0f766e").lower()


def normalize_experiences(values: list[ResumeExperienceItem]) -> list[ResumeExperienceItem]:
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
        if any(
            [
                normalized.role,
                normalized.company,
                normalized.start_date,
                normalized.end_date,
                normalized.location,
                normalized.description,
            ]
        ):
            out.append(normalized)
    return out


def normalize_educations(values: list[ResumeEducationItem]) -> list[ResumeEducationItem]:
    out: list[ResumeEducationItem] = []
    for item in values:
        normalized = ResumeEducationItem(
            school=str(item.school or "").strip(),
            degree=str(item.degree or "").strip(),
            start_date=str(item.start_date or "").strip(),
            end_date=str(item.end_date or "").strip(),
            description=str(item.description or "").strip(),
        )
        if any(
            [
                normalized.school,
                normalized.degree,
                normalized.start_date,
                normalized.end_date,
                normalized.description,
            ]
        ):
            out.append(normalized)
    return out


def normalize_profile_from_payload(raw: dict, first_name_fallback: str) -> ResumeProfileData:
    if not isinstance(raw, dict):
        raw = {}

    # Legacy compatibility: the old schema had plain experience/education text fields.
    legacy_experience = str(raw.get("experience") or "").strip()
    legacy_education = str(raw.get("education") or "").strip()

    experiences_raw = raw.get("experiences") if isinstance(raw.get("experiences"), list) else []
    educations_raw = raw.get("educations") if isinstance(raw.get("educations"), list) else []

    experiences: list[ResumeExperienceItem] = []
    for item in experiences_raw:
        if isinstance(item, dict):
            try:
                experiences.append(ResumeExperienceItem(**item))
            except Exception:
                pass  # skip malformed legacy items
    if not experiences and legacy_experience:
        experiences = [ResumeExperienceItem(description=legacy_experience)]

    educations: list[ResumeEducationItem] = []
    for item in educations_raw:
        if isinstance(item, dict):
            try:
                educations.append(ResumeEducationItem(**item))
            except Exception:
                pass  # skip malformed legacy items
    if not educations and legacy_education:
        educations = [ResumeEducationItem(description=legacy_education)]

    return ResumeProfileData(
        full_name=str(raw.get("full_name") or first_name_fallback).strip(),
        position=str(raw.get("position") or "").strip(),
        phone=str(raw.get("phone") or "").strip(),
        email=str(raw.get("email") or "").strip(),
        location=str(raw.get("location") or "").strip(),
        website=str(raw.get("website") or "").strip(),
        summary=str(raw.get("summary") or "").strip(),
        experiences=normalize_experiences(experiences),
        educations=normalize_educations(educations),
        skills=normalize_items([str(x) for x in (raw.get("skills") or []) if str(x).strip()]),
        languages=normalize_items([str(x) for x in (raw.get("languages") or []) if str(x).strip()]),
        photo_url=str(raw.get("photo_url") or "").strip(),
    )


def build_resume_document(profile: ResumeProfileData, lang: str = DEFAULT_LANG) -> dict[str, Any]:
    """Flatten a profile into the dict the PDF renderers consume, localized."""
    contacts = [x for x in [profile.phone, profile.email, profile.location, profile.website] if (x or "").strip()]
    experiences = [
        {
            "title": " / ".join([x for x in [item.role, item.company] if x]) or t(lang, "default_role"),
            "role": item.role or "",
            "company": item.company or "",
            "period": fmt_period(item.start_date, item.end_date, lang),
            "location": item.location or "",
            "description": item.description or "",
        }
        for item in profile.experiences
    ]
    educations = [
        {
            "title": " / ".join([x for x in [item.school, item.degree] if x]) or t(lang, "default_education"),
            "school": item.school or "",
            "degree": item.degree or "",
            "period": fmt_period(item.start_date, item.end_date, lang),
            "description": item.description or "",
        }
        for item in profile.educations
    ]
    return {
        "lang": lang,
        "name": profile.full_name or t(lang, "unnamed"),
        "position": profile.position or "",
        "contacts": contacts,
        "summary": profile.summary or "",
        "experiences": experiences,
        "educations": educations,
        "skills": profile.skills,
        "languages": profile.languages,
        "photo_url": profile.photo_url or "",
        # Filled in by the router before rendering (see webapp/resume/photos.py).
        "photo_bytes": None,
    }
