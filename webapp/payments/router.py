"""HTTP routes for Click top-ups.

``callback_router``: ``POST /api/payments/click`` — the Shop API callback,
called by SlaydX's forwarder (see :mod:`webapp.payments.shop`). No auth and no
entry gate; the md5 signature is the authentication. Always HTTP 200 JSON.

``router``: the signed-in user's endpoints, behind ``require_entry`` like the
wallet. Money is never credited here; the client polls the order.
"""

import json
import logging
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from webapp.core import errors
from webapp.core.admin_settings import get_admin_settings
from webapp.core.auth import current_user
from webapp.core.database import get_db
from webapp.core.entry_gate import require_entry
from webapp.core.limiter import limiter
from webapp.payments import paynet, service, shop
from webapp.payments.config import (
    MAX_TOPUP_SOUM,
    MIN_TOPUP_SOUM,
    paynet_app_url,
    paynet_enabled,
    paynet_payer_id,
    payments_enabled,
)

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["payments"], dependencies=[Depends(require_entry)])
callback_router = APIRouter(prefix="/payments", tags=["payments-callback"])

#: Webhook bodies are < 2 KB; anything far larger is not Click.
MAX_CALLBACK_BYTES = 16_000


async def _read_params(request: Request):
    """Form-urlencoded / multipart (Click) or JSON, like SlaydX's ``readParams``."""
    content_type = (request.headers.get("content-type") or "").lower()
    try:
        body = await request.body()
        if len(body) > MAX_CALLBACK_BYTES:
            return None
        if "application/json" in content_type:
            return json.loads(body.decode("utf-8") or "null")
        form = await request.form()
        return {key: str(value) for key, value in form.items()}
    except Exception:
        return None


@callback_router.post("/click", include_in_schema=False)
async def click_callback(request: Request, db=Depends(get_db)) -> JSONResponse:
    params = await _read_params(request)
    body = await shop.handle_click(db, params)
    return JSONResponse(status_code=200, content=body)


@callback_router.api_route(
    "/paynet", methods=["POST", "GET", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"], include_in_schema=False
)
async def paynet_callback(request: Request, db=Depends(get_db)) -> JSONResponse:
    """Paynet's JSON-RPC provider endpoint (relayed by SlaydX); Basic auth, see :mod:`webapp.payments.paynet`."""
    return await paynet.handle_request(request, db)


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------


class PaymentsConfigResponse(BaseModel):
    enabled: bool
    min_amount: int
    max_amount: int
    bonus_percent: int


class CreateOrderBody(BaseModel):
    amount: float
    method: Literal["page", "card", "phone", "app"] = "app"


class CardStartBody(BaseModel):
    order_id: str = Field(max_length=64)
    card_number: str = Field(max_length=40)
    expire_date: str = Field(max_length=12)


class CardVerifyBody(BaseModel):
    order_id: str = Field(max_length=64)
    sms_code: str = Field(max_length=16)


class InvoiceBody(BaseModel):
    order_id: str = Field(max_length=64)
    phone: str = Field(max_length=24)


async def _config(db) -> PaymentsConfigResponse:
    settings = await get_admin_settings(db)
    return PaymentsConfigResponse(
        enabled=payments_enabled(),
        min_amount=MIN_TOPUP_SOUM,
        max_amount=MAX_TOPUP_SOUM,
        bonus_percent=int(settings.get("payment_bonus_percent") or 0),
    )


@router.get("/config", response_model=PaymentsConfigResponse)
@limiter.limit("60/minute")
async def get_payments_config(request: Request, db=Depends(get_db)) -> PaymentsConfigResponse:
    return await _config(db)


@router.get("/paynet/info")
@limiter.limit("60/minute")
async def paynet_info(request: Request, user=Depends(current_user)) -> dict:
    """The wallet card: the user's Paynet payer id (``vk-<id>``), only when Paynet is configured."""
    if not paynet_enabled():
        return {"enabled": False, "payer_id": None, "app_url": None}
    return {
        "enabled": True,
        "payer_id": paynet_payer_id(int(user["user_id"])),
        "app_url": paynet_app_url(),
    }


@router.get("/orders")
@limiter.limit("60/minute")
async def list_orders(request: Request, user=Depends(current_user), db=Depends(get_db)) -> dict:
    orders = await service.list_orders(db, int(user["user_id"]))
    return {"orders": [o.public() for o in orders], "enabled": payments_enabled()}


@router.get("/orders/{order_id}")
@limiter.limit("120/minute")
async def get_order(order_id: str, request: Request, user=Depends(current_user), db=Depends(get_db)) -> dict:
    order = await service.find_user_order(db, int(user["user_id"]), order_id)
    if order is None:
        raise errors.not_found("order")
    return {"order": order.public()}


@router.post("/orders", status_code=201)
@limiter.limit("30/minute")
async def create_order(
    request: Request, payload: CreateOrderBody, user=Depends(current_user), db=Depends(get_db)
) -> dict:
    """A new order + the Click checkout link (also the Click app deeplink).

    Nothing is credited here — only the Shop API Complete credits.
    """
    service.assert_payments_enabled()
    user_id = int(user["user_id"])
    await service.hit_limit(db, f"pay:{user_id}", 10, 300)
    order = await service.create_order(db, user_id=user_id, amount=payload.amount, method=payload.method)
    return {"order": order.public(), "checkout_url": service.checkout_url(order)}


@router.post("/click/card")
@limiter.limit("20/minute")
async def click_card_start(
    request: Request, payload: CardStartBody, user=Depends(current_user), db=Depends(get_db)
) -> dict:
    """"Karta" step 1. The card number is never logged or stored (only the one-time token)."""
    return await service.start_card_payment(
        db,
        user_id=int(user["user_id"]),
        order_id=payload.order_id,
        card_number=payload.card_number,
        expire_date=payload.expire_date,
    )


@router.post("/click/card/verify")
@limiter.limit("20/minute")
async def click_card_verify(
    request: Request, payload: CardVerifyBody, user=Depends(current_user), db=Depends(get_db)
) -> dict:
    """"Karta" step 2 -> {status: paid | pending | cancelled}."""
    return await service.confirm_card_payment(
        db, user_id=int(user["user_id"]), order_id=payload.order_id, sms_code=payload.sms_code
    )


@router.post("/click/invoice")
@limiter.limit("20/minute")
async def click_invoice(
    request: Request, payload: InvoiceBody, user=Depends(current_user), db=Depends(get_db)
) -> dict:
    """"Telefon raqam": an invoice to the Click app of that phone -> {status: sent}."""
    return await service.send_click_invoice(
        db, user_id=int(user["user_id"]), order_id=payload.order_id, phone=payload.phone
    )
