import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from webapp.core.config import get_settings
from webapp.core.database import close_pool, init_db, open_connection
from webapp.core.limiter import limiter
from webapp.core.retention import checkpoint_wal, purge_expired
from webapp.core.error_log import install_exception_handler
from webapp.routers import (
    admin_analytics,
    admin_autopost,
    admin_broadcasts,
    admin_channels,
    admin_content,
    admin_finance,
    admin_panel,
    admin_system,
    admin_users,
    auth,
    content,
    filters,
    jobs,
    notifications,
    profile,
    referral,
    resume,
    saves,
    wallet,
)

_log = logging.getLogger(__name__)
settings = get_settings()


# The maintenance pass is cheap (indexed DELETEs + a checkpoint), so hourly is
# frequent enough to keep the WAL and resume_events from growing unbounded.
MAINTENANCE_INTERVAL_SECONDS = 60 * 60


async def _maintenance_pass() -> None:
    """One retention sweep plus a WAL checkpoint, on its own connection.

    Deliberately not a pooled connection: maintenance must never take a slot
    away from a request.
    """
    conn = await open_connection()
    try:
        deleted = await purge_expired(conn)
        if any(deleted.values()):
            _log.info("retention pass deleted %s", deleted)
        await checkpoint_wal(conn)
    finally:
        await conn.close()


async def _maintenance_loop() -> None:
    while True:
        try:
            await asyncio.sleep(MAINTENANCE_INTERVAL_SECONDS)
            await _maintenance_pass()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _log.error("maintenance pass failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await _maintenance_pass()
    except Exception as exc:
        _log.error("retention pass failed: %s", exc)

    task = asyncio.create_task(_maintenance_loop(), name="maintenance_loop")
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await close_pool()


app = FastAPI(title="Bandlik.uz WebApp API", version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEBAPP_ORIGIN],
    # The Mini App authenticates with headers (Bearer / init-data), never with
    # cookies — so the browser must not be allowed to attach credentials.
    allow_credentials=False,
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
# Admin panel v2 routers (all protected by require_role inside each router).
for _admin_router in (
    admin_channels,
    admin_users,
    admin_broadcasts,
    admin_content,
    admin_autopost,
    admin_finance,
    admin_analytics,
    admin_system,
):
    app.include_router(_admin_router.router, prefix="/api")

install_exception_handler(app)


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
