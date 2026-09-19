from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.data.law_articles import get_article, get_articles, get_categories
from webapp.core import errors
from webapp.core.i18n import get_lang

router = APIRouter(prefix="/content", tags=["content"])


# ── Response schemas ────────────────────────────────────────


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


def _category_names(lang: str) -> list[str]:
    names: list[str] = []
    for item in get_categories(lang):
        if isinstance(item, dict):
            names.append(str(item.get("name") or item.get("id") or ""))
        else:
            names.append(str(item))
    return [name for name in names if name]


# ── Endpoints ───────────────────────────────────────────────


@router.get("/laws", response_model=LawsListResponse)
async def get_laws(lang: str = Depends(get_lang)) -> LawsListResponse:
    """All law articles (categories plus short descriptions), localized."""
    return LawsListResponse(
        categories=_category_names(lang),
        articles=[
            ArticleSummary(
                id=str(a["id"]),
                category=str(a.get("category") or ""),
                title=str(a.get("title") or ""),
                summary=str(a.get("summary") or ""),
                source_label=str(a.get("source_label") or ""),
            )
            for a in get_articles(lang)
        ],
    )


@router.get("/laws/{article_id}", response_model=ArticleDetail)
async def get_law_detail(article_id: str, lang: str = Depends(get_lang)) -> ArticleDetail:
    """Full text of a single article, localized."""
    article = get_article(article_id, lang)
    if not article:
        raise errors.not_found("article")
    return ArticleDetail(
        id=str(article["id"]),
        category=str(article.get("category") or ""),
        title=str(article.get("title") or ""),
        summary=str(article.get("summary") or ""),
        full_text=str(article.get("full_text") or ""),
        source_url=str(article.get("source_url") or ""),
        source_label=str(article.get("source_label") or ""),
    )
