import html
import json
import re
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.session import get_current_user

router = APIRouter(prefix="/resume", tags=["resume"])


class ResumeExperienceItem(BaseModel):
    role: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    description: str = ""


class ResumeEducationItem(BaseModel):
    school: str = ""
    degree: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class ResumeProfileData(BaseModel):
    full_name: str = ""
    position: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    website: str = ""
    summary: str = ""
    experiences: list[ResumeExperienceItem] = Field(default_factory=list)
    educations: list[ResumeEducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


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
    preview_variant: str = "single"
    palette: list[str] = Field(default_factory=list)


class ResumeTemplatesResponse(BaseModel):
    items: list[ResumeTemplateItem]


class ResumeSendRequest(BaseModel):
    template_id: str


class ResumeSendResponse(BaseModel):
    ok: bool
    message: str


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
    palette = {
        "clean": {"accent": "#0f766e", "bg": "#f8fafc"},
        "modern": {"accent": "#2563eb", "bg": "#f8fafc"},
        "compact": {"accent": "#111827", "bg": "#ffffff"},
    }.get(template_id, {"accent": "#0f766e", "bg": "#f8fafc"})

    palette["accent"] = accent_color

    contact_parts = [
        part.strip()
        for part in [profile.phone, profile.email, profile.location, profile.website]
        if part and part.strip()
    ]
    contact_line = " | ".join(_safe_text(part) for part in contact_parts) or "Kontakt kiritilmagan"

    return f"""
<!doctype html>
<html lang=\"uz\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Resume - {_safe_text(profile.full_name)}</title>
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
      <h1>{_safe_text(profile.full_name or 'Nomsiz nomzod')}</h1>
      <p>{_safe_text(profile.position or 'Lavozim ko\'rsatilmagan')}</p>
      <p>{contact_line}</p>
    </header>

    <section class=\"section\">
      <h2>Qisqacha</h2>
      <p class=\"block\">{_safe_text(profile.summary or 'Qisqacha ma\'lumot kiritilmagan')}</p>
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


@router.get("/templates", response_model=ResumeTemplatesResponse)
async def get_templates() -> ResumeTemplatesResponse:
    return ResumeTemplatesResponse(items=list(TEMPLATES.values()))


@router.get("/profile", response_model=ResumeProfileResponse)
async def get_profile(current=Depends(get_current_user), db=Depends(get_db)) -> ResumeProfileResponse:
    user = current["user"]
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
async def put_profile(payload: ResumeProfileUpsertRequest, current=Depends(get_current_user), db=Depends(get_db)) -> ResumeProfileResponse:
    user_id = int(current["user"]["user_id"])
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
    await db.commit()

    return ResumeProfileResponse(
        profile=normalized_profile,
        selected_template=template_id,
        accent_color=accent_color,
        updated_at=now,
    )


@router.post("/send-telegram", response_model=ResumeSendResponse)
async def send_resume_to_telegram(payload: ResumeSendRequest, current=Depends(get_current_user), db=Depends(get_db)) -> ResumeSendResponse:
    user = current["user"]
    user_id = int(user["user_id"])
    template_id = (payload.template_id or "").strip().lower()
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown template")

    row = await _load_resume_row(db, user_id)
    if not row:
        profile = _default_profile(str(user.get("first_name") or ""))
        accent_color = _normalize_color(None, template_id)
    else:
        try:
            raw_payload = json.loads(str(row["profile_json"] or "{}"))
        except Exception:
            raw_payload = {}
        profile = _normalize_profile_from_payload(raw_payload, str(user.get("first_name") or ""))
        accent_color = _normalize_color(raw_payload.get("accent_color") if isinstance(raw_payload, dict) else None, template_id)

    rendered = _render_resume_html(profile, template_id, accent_color)
    file_name = f"resume_{template_id}_{user_id}.html"

    settings = get_settings()
    if not settings.TOKEN:
        raise HTTPException(status_code=500, detail="Bot token missing")

    endpoint = f"https://api.telegram.org/bot{settings.TOKEN}/sendDocument"
    caption = "Resume tayyor. Faylni yuklab olib ishlatishingiz mumkin."

    async with httpx.AsyncClient(timeout=25) as client:
        response = await client.post(
            endpoint,
            data={"chat_id": str(user_id), "caption": caption},
            files={"document": (file_name, rendered.encode("utf-8"), "text/html")},
        )

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Telegramga yuborishda xatolik")

    body = response.json() if response.content else {}
    if not body.get("ok"):
        raise HTTPException(status_code=502, detail="Telegram API xatolik qaytardi")

    return ResumeSendResponse(ok=True, message="Resume Telegramga yuborildi")
