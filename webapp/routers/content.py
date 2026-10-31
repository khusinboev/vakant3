from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from webapp.core import content_repo, errors
from webapp.core.database import get_db
from webapp.core.i18n import get_lang
from webapp.core.limiter import limiter

router = APIRouter(prefix="/content", tags=["content"])

#: These two endpoints are public (no ``current_user``), so their bucket is
#: the caller's IP. The content is small and cached client-side for ten
#: minutes; 120/minute is far above any real Mini App session and still
#: stops an anonymous caller from hammering the article tables.
PUBLIC_RATE_LIMIT = "120/minute"


# ── Response schemas (unchanged shape — see webapp/frontend/src/pages/Laws.tsx) ──


class ArticleSummary(BaseModel):
    id: str
    category: str
    title: str
    summary: str
    source_label: str


class ArticleDetail(BaseModel):
    id: str
    category: str
    title: str
    summary: str
    full_text: str
    source_url: str
    source_label: str


class LawsListResponse(BaseModel):
    categories: list[str]
    articles: list[ArticleSummary]


# ── Endpoints ───────────────────────────────────────────────


@router.get("/laws", response_model=LawsListResponse)
@limiter.limit(PUBLIC_RATE_LIMIT)
async def get_laws(
    request: Request, lang: str = Depends(get_lang), db=Depends(get_db)
) -> LawsListResponse:
    """All law articles (categories plus short descriptions), localized."""
    categories = await content_repo.list_categories_public(db, lang)
    articles = await content_repo.list_articles_public(db, lang)
    return LawsListResponse(
        categories=[c["name"] for c in categories if c.get("name")],
        articles=[ArticleSummary(**a) for a in articles],
    )


@router.get("/laws/{article_id}", response_model=ArticleDetail)
@limiter.limit(PUBLIC_RATE_LIMIT)
async def get_law_detail(
    request: Request, article_id: str, lang: str = Depends(get_lang), db=Depends(get_db)
) -> ArticleDetail:
    """Full text of a single article, localized."""
    article = await content_repo.get_article_public(db, article_id, lang)
    if not article:
        raise errors.not_found("article")
    return ArticleDetail(**article)
