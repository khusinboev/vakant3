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
    #: Vacancy store source (``osonish`` / ``hh``), its display name and the original posting.
    source: str = "osonish"
    source_label: str | None = None
    url: str | None = None


class JobsSearchResponse(BaseModel):
    vacancies: list[VacancyItem]
    page: int
    last_page: int
    total_estimate: int
    #: Store results page by cursor (send it back as ``?cursor=`` with ``page+1``);
    #: ``None`` on the last page and on the live osonish fallback (page numbers).
    next_cursor: str | None = None


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
