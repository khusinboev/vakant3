"""Server-side error log (``error_log`` table, see m012_error_log) plus the
FastAPI catch-all exception handler.

``log_error`` is a plain insert-and-commit helper any process (API request,
bot handler, background scheduler) can call with its own connection — it
never raises, because a logging failure must not crash the caller.

``install_exception_handler`` wires a handler for exceptions that escape every
router/middleware. FastAPI's own ``HTTPException``/``api_error`` handling
already produces clean JSON for expected errors, so this only fires for
genuinely unhandled exceptions: it logs with a request id (never leaking a
traceback to the client) and always answers 500 with a stable envelope.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_log = logging.getLogger(__name__)

_MAX_MESSAGE_CHARS = 4000
_MAX_CONTEXT_CHARS = 8000


async def _table_exists(conn, name: str) -> bool:
    cursor = await conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1", (name,)
    )
    return await cursor.fetchone() is not None


async def log_error(
    conn,
    source: str,
    message: str,
    context: dict[str, Any] | None = None,
    level: str = "error",
) -> None:
    """Insert one ``error_log`` row and commit.

    ``source`` is conventionally one of ``api``/``bot``/``scheduler``. Never
    raises: a table missing from a not-yet-migrated DB, or any other failure
    while writing the row, is logged locally instead.
    """
    try:
        if not await _table_exists(conn, "error_log"):
            _log.warning("error_log table missing, dropping error: %s", message)
            return
        context_json: str | None = None
        if context is not None:
            try:
                context_json = json.dumps(context, ensure_ascii=False, default=str)
            except (TypeError, ValueError):
                context_json = json.dumps({"_unserializable": True})
            if len(context_json) > _MAX_CONTEXT_CHARS:
                context_json = context_json[:_MAX_CONTEXT_CHARS] + '..."[truncated]"'
        await conn.execute(
            "INSERT INTO error_log (created_at, source, level, message, context_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                int(time.time()),
                str(source)[:32],
                str(level)[:16],
                str(message)[:_MAX_MESSAGE_CHARS],
                context_json,
            ),
        )
        await conn.commit()
    except Exception:
        _log.exception("failed to write error_log row (message=%r)", str(message)[:200])


def install_exception_handler(app: FastAPI) -> None:
    """Register the catch-all handler for exceptions that escape every route.

    The coordinator calls this once, after every router is included.
    """

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # HTTPException (ours or Starlette's) is already handled elsewhere;
        # never swallow a deliberate HTTP response if one somehow reaches here.
        if isinstance(exc, (StarletteHTTPException, FastAPIHTTPException)):
            raise exc

        request_id = uuid.uuid4().hex
        _log.exception(
            "unhandled exception [%s] %s %s", request_id, request.method, request.url.path
        )

        try:
            from webapp.core.database import open_connection

            conn = await open_connection()
            try:
                await log_error(
                    conn,
                    source="api",
                    message=f"{type(exc).__name__}: {exc}",
                    context={
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                    },
                )
            finally:
                await conn.close()
        except Exception:
            _log.exception("failed to persist unhandled exception to error_log")

        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "INTERNAL_ERROR", "request_id": request_id}},
        )
