import html
import json
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from webapp.core.config import get_settings
from webapp.core.database import get_db
from webapp.core.session import get_current_user

router = APIRouter(prefix="/resume", tags=["resume"])


class ResumeProfileData(BaseModel):
    full_name: str = ""
    position: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    website: str = ""
    summary: str = ""
    experience: str = ""
    education: str = ""
    skills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ResumeProfileResponse(BaseModel):
    profile: ResumeProfileData
    selected_template: str
    updated_at: int | None = None


class ResumeProfileUpsertRequest(BaseModel):
    profile: ResumeProfileData
    selected_template: str = "clean"


class ResumeTemplateItem(BaseModel):
    id: str
    title: str
    description: str


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
    ),
    "modern": ResumeTemplateItem(
        id="modern",
        title="Modern Accent",
        description="Qisqa va zamonaviy blokli uslub.",
    ),
    "compact": ResumeTemplateItem(
        id="compact",
        title="Compact One-Page",
        description="Bir sahifaga sig'adigan ixcham format.",
    ),
}


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


def _render_lines(values: list[str]) -> str:
    cleaned = _normalize_items(values)
    if not cleaned:
        return "<p class='muted'>Ko'rsatilmagan</p>"
    rows = "".join(f"<li>{_safe_text(item)}</li>" for item in cleaned)
    return f"<ul>{rows}</ul>"


def _render_resume_html(profile: ResumeProfileData, template_id: str) -> str:
    palette = {
        "clean": {"accent": "#0f766e", "bg": "#f8fafc"},
        "modern": {"accent": "#2563eb", "bg": "#f8fafc"},
        "compact": {"accent": "#7c3aed", "bg": "#ffffff"},
    }.get(template_id, {"accent": "#0f766e", "bg": "#f8fafc"})

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
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin: 4px 0; }}
    .block {{ white-space: pre-wrap; line-height: 1.5; }}
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
      <p class=\"block\">{_safe_text(profile.experience or 'Tajriba kiritilmagan')}</p>
    </section>

    <section class=\"section\">
      <h2>Ta'lim</h2>
      <p class=\"block\">{_safe_text(profile.education or 'Ta\'lim ma\'lumoti kiritilmagan')}</p>
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
            updated_at=None,
        )

    try:
        payload = json.loads(str(row["profile_json"] or "{}"))
    except Exception:
        payload = {}

    profile = ResumeProfileData(**payload)
    return ResumeProfileResponse(
        profile=profile,
        selected_template=str(row["selected_template"] or "clean"),
        updated_at=int(row["updated_at"] or 0),
    )


@router.put("/profile", response_model=ResumeProfileResponse)
async def put_profile(payload: ResumeProfileUpsertRequest, current=Depends(get_current_user), db=Depends(get_db)) -> ResumeProfileResponse:
    user_id = int(current["user"]["user_id"])
    template_id = (payload.selected_template or "clean").strip().lower()
    if template_id not in TEMPLATES:
        raise HTTPException(status_code=400, detail="Unknown template")

    normalized_profile = payload.profile.model_copy(
        update={
            "skills": _normalize_items(payload.profile.skills),
            "languages": _normalize_items(payload.profile.languages),
        }
    )

    now = int(time.time())
    profile_json = json.dumps(normalized_profile.model_dump(), ensure_ascii=False)

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

    return ResumeProfileResponse(profile=normalized_profile, selected_template=template_id, updated_at=now)


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
    else:
        try:
            raw_payload = json.loads(str(row["profile_json"] or "{}"))
        except Exception:
            raw_payload = {}
        profile = ResumeProfileData(**raw_payload)

    rendered = _render_resume_html(profile, template_id)
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
