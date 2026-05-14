from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from webapp.core.config import get_settings
from webapp.core.database import init_db
from webapp.core.limiter import limiter
from webapp.routers import admin_panel, auth, filters, jobs, profile, referral, saves

settings = get_settings()
app = FastAPI(title="Bandlik.uz WebApp API", version="1.0.0")

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


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


frontend_dist = Path(__file__).resolve().parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

    @app.get("/{path:path}")
    async def frontend(path: str):
        index_file = frontend_dist / "index.html"
        if not index_file.exists():
            return {"ok": True}
        return FileResponse(index_file)
