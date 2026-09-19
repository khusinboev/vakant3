from fastapi import APIRouter, Depends

from src.functions.cache import cache_get, cache_set, make_cache_key
from webapp.core.database import get_db
from webapp.core.i18n import SPECS, district_name, get_lang, region_name
from webapp.models.schemas import RegionItem, SpecItem

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("/regions", response_model=list[RegionItem])
async def regions(db=Depends(get_db), lang: str = Depends(get_lang)) -> list[RegionItem]:
    key = make_cache_key("webapp_filters_regions")
    cached = await cache_get(key)
    if isinstance(cached, list):
        rows = cached
    else:
        cursor = await db.execute("SELECT soato, name_uz FROM regions ORDER BY CAST(soato AS INTEGER)")
        rows = [
            {"soato": str(row["soato"]), "name_uz": str(row["name_uz"])}
            for row in await cursor.fetchall()
        ]
        await cache_set(key, rows, ttl=24 * 60 * 60)

    return [
        RegionItem(
            soato=str(item["soato"]),
            name_uz=str(item["name_uz"]),
            name=region_name(str(item["soato"]), str(item["name_uz"]), lang),
        )
        for item in rows
    ]


@router.get("/districts", response_model=list[RegionItem])
async def districts(
    region_soato: str, db=Depends(get_db), lang: str = Depends(get_lang)
) -> list[RegionItem]:
    key = make_cache_key("webapp_filters_districts", region_soato=region_soato)
    cached = await cache_get(key)
    if isinstance(cached, list):
        rows = cached
    else:
        cursor = await db.execute(
            "SELECT soato, name_uz FROM districts WHERE region_soato = ? ORDER BY name_uz",
            (region_soato,),
        )
        rows = [
            {"soato": str(row["soato"]), "name_uz": str(row["name_uz"])}
            for row in await cursor.fetchall()
        ]
        await cache_set(key, rows, ttl=24 * 60 * 60)

    return [
        RegionItem(
            soato=str(item["soato"]),
            name_uz=str(item["name_uz"]),
            name=district_name(str(item["soato"]), str(item["name_uz"]), lang),
        )
        for item in rows
    ]


@router.get("/specs", response_model=list[SpecItem])
async def specs(lang: str = Depends(get_lang)) -> list[SpecItem]:
    return [
        SpecItem(
            id=str(item["id"]),
            key=str(item["key"]),
            label=str(item["labels"].get(lang) or item["labels"]["uz"]),
        )
        for item in SPECS
    ]
