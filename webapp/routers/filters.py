from fastapi import APIRouter, Depends

from src.functions.cache import cache_get, cache_set, make_cache_key
from webapp.core.database import get_db
from webapp.models.schemas import RegionItem, SpecItem

router = APIRouter(prefix="/filters", tags=["filters"])

SPECS: list[SpecItem] = [
    SpecItem(id="spec:47", label="Sog'liqni saqlash"),
    SpecItem(id="spec:41", label="Qurilish"),
    SpecItem(id="spec:64", label="Savdo va marketing"),
    SpecItem(id="spec:7", label="Qishloq xo'jaligi"),
    SpecItem(id="spec:12", label="Axborot texnologiyalari"),
    SpecItem(id="spec:42", label="Ta'lim, madaniyat, sport"),
    SpecItem(id="spec:36", label="Transport"),
    SpecItem(id="spec:1", label="Moliya, iqtisod, boshqaruv"),
    SpecItem(id="spec:21", label="Sanoat va ishlab chiqarish"),
    SpecItem(id="spec:48", label="Xizmatlar"),
]


@router.get("/regions", response_model=list[RegionItem])
async def regions(db=Depends(get_db)) -> list[RegionItem]:
    key = make_cache_key("webapp_filters_regions")
    cached = await cache_get(key)
    if isinstance(cached, list):
        return [RegionItem(**item) for item in cached]

    cursor = await db.execute("SELECT soato, name_uz FROM regions ORDER BY CAST(soato AS INTEGER)")
    rows = await cursor.fetchall()
    data = [RegionItem(soato=str(row["soato"]), name_uz=str(row["name_uz"])) for row in rows]
    await cache_set(key, [item.model_dump() for item in data], ttl=24 * 60 * 60)
    return data


@router.get("/districts", response_model=list[RegionItem])
async def districts(region_soato: str, db=Depends(get_db)) -> list[RegionItem]:
    key = make_cache_key("webapp_filters_districts", region_soato=region_soato)
    cached = await cache_get(key)
    if isinstance(cached, list):
        return [RegionItem(**item) for item in cached]

    cursor = await db.execute(
        "SELECT soato, name_uz FROM districts WHERE region_soato = ? ORDER BY name_uz",
        (region_soato,),
    )
    rows = await cursor.fetchall()
    data = [RegionItem(soato=str(row["soato"]), name_uz=str(row["name_uz"])) for row in rows]
    await cache_set(key, [item.model_dump() for item in data], ttl=24 * 60 * 60)
    return data


@router.get("/specs", response_model=list[SpecItem])
async def specs() -> list[SpecItem]:
    return SPECS
