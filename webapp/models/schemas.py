from typing import Any

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: int
    first_name: str
    username: str | None = None
    photo_url: str | None = None
    lang: str = "uz"


class AuthResponse(BaseModel):
    session_token: str
    user: UserProfile


class VacancyItem(BaseModel):
    uid: str
    # Upstream may omit any of these; the Mini App renders its own placeholder.
    title: str | None = None
    company: str | None = None
    salary_text: str | None = None
    location: str | None = None
    district: str | None = None
    posted_at: str | None = None
    is_saved: bool = False
    is_pro_locked: bool = False


class JobsSearchResponse(BaseModel):
    vacancies: list[VacancyItem]
    page: int
    last_page: int
    total_estimate: int


class VacancyDetailResponse(BaseModel):
    uid: str
    data: dict[str, Any]


class SavesResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


class SaveActionResponse(BaseModel):
    saved: bool | None = None
    removed: bool | None = None


class ProfileFiltersPatchRequest(BaseModel):
    region: str | None = Field(default=None)
    district: str | None = Field(default=None)
    specs: str | None = Field(default=None)
    money: int | None = Field(default=None)


class LangPatchRequest(BaseModel):
    lang: str


class LangResponse(BaseModel):
    ok: bool = True
    lang: str


class UpdateResultResponse(BaseModel):
    updated: bool


class ReferralUser(BaseModel):
    first_name: str | None = None
    date: int
    username: str | None = None


class ReferralResponse(BaseModel):
    ref_link: str
    ref_count: int
    referrals: list[ReferralUser]


class RegionItem(BaseModel):
    soato: str
    name_uz: str
    name: str | None = None


class SpecItem(BaseModel):
    id: str
    key: str
    label: str
