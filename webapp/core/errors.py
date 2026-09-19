"""Machine-readable API errors.

Every HTTPException raised by the API carries ``detail = {"code": "<UPPER_SNAKE>", ...params}``
so the Mini App can translate the message itself (see CONTRACT.md).
"""

from typing import Any

from fastapi import HTTPException

# Canonical error codes (documented in CONTRACT.md).
AUTH_REQUIRED = "AUTH_REQUIRED"
INVALID_INIT_DATA = "INVALID_INIT_DATA"
SESSION_EXPIRED = "SESSION_EXPIRED"
ADMIN_REQUIRED = "ADMIN_REQUIRED"
REFERRAL_LOCKED = "REFERRAL_LOCKED"
PRO_REQUIRED = "PRO_REQUIRED"
SAVE_LIMIT_REACHED = "SAVE_LIMIT_REACHED"
PREMIUM_TEMPLATE = "PREMIUM_TEMPLATE"
INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
ALREADY_PRO = "ALREADY_PRO"
NOT_FOUND = "NOT_FOUND"
INVALID_UID = "INVALID_UID"
VALIDATION_ERROR = "VALIDATION_ERROR"
PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"
TELEGRAM_SEND_FAILED = "TELEGRAM_SEND_FAILED"
UPSTREAM_ERROR = "UPSTREAM_ERROR"
RATE_LIMITED = "RATE_LIMITED"
SERVER_MISCONFIGURED = "SERVER_MISCONFIGURED"
PDF_RENDER_FAILED = "PDF_RENDER_FAILED"


def api_error(status: int, code: str, **params: Any) -> HTTPException:
    """Build an HTTPException whose detail is a machine-readable payload."""
    detail: dict[str, Any] = {"code": code}
    for key, value in params.items():
        if value is not None:
            detail[key] = value
    return HTTPException(status_code=status, detail=detail)


def auth_required() -> HTTPException:
    return api_error(401, AUTH_REQUIRED)


def not_found(resource: str) -> HTTPException:
    return api_error(404, NOT_FOUND, resource=resource)


def validation_error(field: str | None = None, status: int = 400) -> HTTPException:
    return api_error(status, VALIDATION_ERROR, field=field)
