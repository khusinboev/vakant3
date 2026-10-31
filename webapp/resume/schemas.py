"""Request/response models and the template catalogue for the resume builder."""

import re
from typing import Any

from pydantic import BaseModel, Field

from webapp.core.i18n import DEFAULT_LANG, normalize_lang

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
IDEMPOTENCY_RE = re.compile(r"^[a-zA-Z0-9_.:-]{8,120}$")
MAX_PROFILE_BYTES = 512 * 1024
MAX_PHOTO_URL_CHARS = 400_000

FREE_TEMPLATES: frozenset[str] = frozenset({"clean", "modern", "compact"})

# Event names the Mini App is allowed to report (see ResumeStudio.tsx).
ALLOWED_EVENT_NAMES: frozenset[str] = frozenset(
    {
        "builder_opened",
        "builder_ready",
        "save_success",
        "save_error",
        "autosave_success",
        "autosave_error",
        "send_success",
        "send_error",
        "export_success",
        "export_error",
    }
)
ALLOWED_EVENT_STEPS: frozenset[str] = frozenset(
    {"basic", "experience", "education", "skills", "summary", "template", "final"}
)


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
    # Data URI (resized by the Mini App) or an https URL on an allowlisted host.
    photo_url: str = Field(default="", max_length=MAX_PHOTO_URL_CHARS)


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
    is_premium: bool = False


class ResumeTemplatesResponse(BaseModel):
    items: list[ResumeTemplateItem]


class ResumeSendRequest(BaseModel):
    template_id: str


class ResumeSendResponse(BaseModel):
    ok: bool
    status: str = "SENT"


class ResumeEventRequest(BaseModel):
    event_name: str = Field(min_length=2, max_length=64)
    step: str | None = Field(default=None, max_length=64)
    meta_json: str | None = Field(default=None, max_length=2000)


class ResumeEventResponse(BaseModel):
    ok: bool = True


# ---------------------------------------------------------------------------
# Template catalogue. `title`/`description` are localized per request language.
# ---------------------------------------------------------------------------

TEMPLATES: dict[str, dict[str, Any]] = {
    "clean": {
        "title": {"uz": "Clean Classic", "ru": "Clean Classic", "en": "Clean Classic"},
        "description": {
            "uz": "Sodda klassik ko'rinish, barcha sohalar uchun.",
            "ru": "Простой классический вид, подходит для любой сферы.",
            "en": "Simple classic layout that fits any field.",
        },
        "supports_color": True,
        "preview_variant": "single",
        "palette": ["#0f766e", "#2563eb", "#b45309", "#be123c", "#374151"],
    },
    "modern": {
        "title": {"uz": "Modern Accent", "ru": "Modern Accent", "en": "Modern Accent"},
        "description": {
            "uz": "Qisqa va zamonaviy blokli uslub.",
            "ru": "Компактный современный стиль с боковой панелью.",
            "en": "Compact modern style with a sidebar.",
        },
        "supports_color": True,
        "supports_sidebar": True,
        "preview_variant": "split",
        "palette": ["#2563eb", "#7c3aed", "#0f766e", "#ea580c", "#334155"],
    },
    "compact": {
        "title": {"uz": "Compact One-Page", "ru": "Compact One-Page", "en": "Compact One-Page"},
        "description": {
            "uz": "Bir sahifaga sig'adigan ixcham format.",
            "ru": "Плотный формат, помещается на одну страницу.",
            "en": "Dense format that fits on a single page.",
        },
        "supports_color": False,
        "preview_variant": "mono",
        "palette": ["#111827"],
    },
    "executive": {
        "title": {"uz": "Executive Dark", "ru": "Executive Dark", "en": "Executive Dark"},
        "description": {
            "uz": "Korporativ uslub: to'q sarlavha va ikki ustunli ko'nikmalar.",
            "ru": "Корпоративный стиль: тёмная шапка и навыки в две колонки.",
            "en": "Corporate style: dark header and two-column skills.",
        },
        "supports_color": True,
        "preview_variant": "single",
        "palette": ["#1e3a5f", "#7c2d12", "#164e63", "#3b0764", "#1c1917"],
    },
    "timeline": {
        "title": {"uz": "Timeline Classic", "ru": "Timeline Classic", "en": "Timeline Classic"},
        "description": {
            "uz": "Tajriba bo'ylab vertikal chiziq va doira belgilari bilan vaqt o'qi.",
            "ru": "Хронология опыта с вертикальной линией и точками.",
            "en": "A timeline of your experience with a vertical line and dots.",
        },
        "supports_color": True,
        "preview_variant": "single",
        "palette": ["#0f766e", "#2563eb", "#7c3aed", "#b45309", "#065f46"],
    },
    "minimal": {
        "title": {"uz": "Minimal Pure", "ru": "Minimal Pure", "en": "Minimal Pure"},
        "description": {
            "uz": "Faqat tipografiya, rangli bloklarsiz sof professional ko'rinish.",
            "ru": "Только типографика, без цветных блоков — чистый профессиональный вид.",
            "en": "Typography only, no colour blocks — a clean professional look.",
        },
        "supports_color": False,
        "preview_variant": "mono",
        "palette": ["#111827"],
    },
    "creative": {
        "title": {"uz": "Creative Stripe", "ru": "Creative Stripe", "en": "Creative Stripe"},
        "description": {
            "uz": "Chap tomonda qalin rang zolagi — kreativ va dizayn sohalari uchun.",
            "ru": "Широкая цветная полоса слева — для креативных и дизайнерских профессий.",
            "en": "A bold colour stripe on the left — for creative and design roles.",
        },
        "supports_color": True,
        "preview_variant": "single",
        "palette": ["#7c3aed", "#ea580c", "#be123c", "#0f766e", "#1d4ed8"],
    },
    "photo_classic": {
        "title": {"uz": "Photo Classic", "ru": "Photo Classic", "en": "Photo Classic"},
        "description": {
            "uz": "Sarlavhaning o'ng qismida profil rasmi bo'lgan klassik uslub.",
            "ru": "Классический стиль с фото в правой части шапки.",
            "en": "Classic layout with a profile photo in the top-right corner.",
        },
        "supports_color": True,
        "supports_photo": True,
        "preview_variant": "single",
        "palette": ["#0f766e", "#2563eb", "#b45309", "#be123c", "#374151"],
    },
    "photo_sidebar": {
        "title": {"uz": "Photo Sidebar", "ru": "Photo Sidebar", "en": "Photo Sidebar"},
        "description": {
            "uz": "Keng qo'shimcha panel: yuqorida rasm, asosiy maydonda tajriba va ta'lim.",
            "ru": "Широкая боковая панель: фото сверху, опыт и образование в основной колонке.",
            "en": "Wide sidebar: photo on top, experience and education in the main column.",
        },
        "supports_color": True,
        "supports_sidebar": True,
        "supports_photo": True,
        "preview_variant": "split",
        "palette": ["#2563eb", "#7c3aed", "#0f766e", "#ea580c", "#334155"],
    },
    "europass": {
        "title": {"uz": "Europass Grid", "ru": "Europass Grid", "en": "Europass Grid"},
        "description": {
            "uz": "Europass uslubida ikki ustunli jadval tuzilishi va ixtiyoriy rasm.",
            "ru": "Двухколоночная сетка в стиле Europass с опциональным фото.",
            "en": "Europass-style two-column grid with an optional photo.",
        },
        "supports_color": True,
        "supports_photo": True,
        "preview_variant": "split",
        "palette": ["#1e40af", "#065f46", "#7c2d12", "#4c1d95", "#374151"],
    },
    "infographic": {
        "title": {"uz": "Infographic Visual", "ru": "Infographic Visual", "en": "Infographic Visual"},
        "description": {
            "uz": "Vizual ko'nikma panellari, rangli bo'limlar va accent belgilari.",
            "ru": "Визуальные шкалы навыков, цветные секции и акцентные маркеры.",
            "en": "Visual skill bars, coloured sections and accent markers.",
        },
        "supports_color": True,
        "preview_variant": "single",
        "palette": ["#0f766e", "#2563eb", "#ea580c", "#7c3aed", "#1e3a5f"],
    },
}


def template_exists(template_id: str) -> bool:
    return template_id in TEMPLATES


def template_palette(template_id: str) -> list[str]:
    meta = TEMPLATES.get(template_id) or {}
    return list(meta.get("palette") or [])


def template_supports_color(template_id: str) -> bool:
    meta = TEMPLATES.get(template_id) or {}
    return bool(meta.get("supports_color", True))


def _localized(value: dict[str, str], lang: str) -> str:
    return value.get(lang) or value.get(DEFAULT_LANG) or ""


def template_items(lang: str = DEFAULT_LANG) -> list[ResumeTemplateItem]:
    lang = normalize_lang(lang)
    items: list[ResumeTemplateItem] = []
    for template_id, meta in TEMPLATES.items():
        items.append(
            ResumeTemplateItem(
                id=template_id,
                title=_localized(meta["title"], lang),
                description=_localized(meta["description"], lang),
                supports_color=bool(meta.get("supports_color", True)),
                supports_sidebar=bool(meta.get("supports_sidebar", False)),
                supports_photo=bool(meta.get("supports_photo", False)),
                preview_variant=str(meta.get("preview_variant") or "single"),
                palette=list(meta.get("palette") or []),
                is_premium=template_id not in FREE_TEMPLATES,
            )
        )
    return items
