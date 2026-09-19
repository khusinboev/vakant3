import logging
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from webapp.core.config import DB_PATH, get_settings
from webapp.core.database import init_db
from webapp.core.limiter import limiter
from webapp.core.retention import purge_expired
from webapp.routers import admin_panel, auth, content, filters, jobs, notifications, profile, referral, resume, saves, wallet

_log = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            conn.row_factory = aiosqlite.Row
            deleted = await purge_expired(conn)
        if any(deleted.values()):
            _log.info("retention pass deleted %s", deleted)
    except Exception as exc:
        _log.error("retention pass failed: %s", exc)
    yield


app = FastAPI(title="Bandlik.uz WebApp API", version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEBAPP_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(filters.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(saves.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(referral.router, prefix="/api")
app.include_router(admin_panel.router, prefix="/api")
app.include_router(wallet.router, prefix="/api")
app.include_router(resume.router, prefix="/api")
app.include_router(content.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
if frontend_dist.exists():
    # The assets folder is missing while the frontend is being rebuilt — mounting it
    # unconditionally would crash the API at import time.
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # Keep this catch-all registered last: it serves the SPA for every non-API path.
    @app.get("/{path:path}")
    async def frontend(path: str):
        if path.startswith("api/") or path == "api":
            return JSONResponse(status_code=404, content={"detail": {"code": "NOT_FOUND", "resource": "endpoint"}})
        index_file = frontend_dist / "index.html"
        if not index_file.exists():
            return {"ok": True}
        return FileResponse(index_file)
