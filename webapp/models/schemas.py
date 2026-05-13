from typing import Any

from pydantic import BaseModel, Field


class TelegramAuthRequest(BaseModel):
    id: int
    first_name: str
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class UserProfile(BaseModel):
    user_id: int
    first_name: str
    username: str | None = None
    photo_url: str | None = None
    lang: str = "uz"


class AuthResponse(BaseModel):
    session_token: str
    user: UserProfile


class LogoutResponse(BaseModel):
    ok: bool = True


class VacancyItem(BaseModel):
    uid: str
    title: str
    company: str
    salary_text: str
    location: str
    district: str
    posted_at: str
    is_saved: bool = False


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


class ProfileStats(BaseModel):
    saves_count: int
    referrals_count: int
    member_since: str
    days_active: int


class CurrentFilters(BaseModel):
    region: str | None = None
    district: str | None = None
    specs: str | None = None
    money: int | None = None


class ProfileResponse(BaseModel):
    user: UserProfile
    stats: ProfileStats
    current_filters: CurrentFilters


class ProfileFiltersPatchRequest(BaseModel):
    region: str | None = Field(default=None)
    district: str | None = Field(default=None)
    specs: str | None = Field(default=None)
    money: int | None = Field(default=None)


class UpdateResultResponse(BaseModel):
    updated: bool


class ReferralUser(BaseModel):
    first_name: str
    date: int
    username: str | None = None


class ReferralResponse(BaseModel):
    ref_link: str
    ref_count: int
    referrals: list[ReferralUser]


class RegionItem(BaseModel):
    soato: str
    name_uz: str


class SpecItem(BaseModel):
    id: str
    label: str
