"""Web entry point: receives webhooks, verifies them, and queues messages.

Nothing is processed until the request is proven to come from Meta
(HMAC signature with the app secret) or Telegram (secret header).
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.channels import telegram, whatsapp
from app.channels.base import Incoming
from app.config import get_settings
from app.db.session import init_db
from app.logging_setup import setup_logging
from app.security.crypto import constant_time_equals
from app.worker import enqueue, handle_inline

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    setup_logging(get_settings().log_level)
    await init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    docs = None if s.is_production else "/docs"
    app = FastAPI(title="Rafiq", lifespan=lifespan, docs_url=docs, redoc_url=None, openapi_url=None if s.is_production else "/openapi.json")

    async def read_body(request: Request) -> bytes:
        declared = int(request.headers.get("content-length") or 0)
        if declared > s.max_webhook_body_bytes:
            raise HTTPException(413, "Payload too large")
        body = await request.body()
        if len(body) > s.max_webhook_body_bytes:
            raise HTTPException(413, "Payload too large")
        return body

    async def dispatch(messages: list[Incoming], background: BackgroundTasks) -> None:
        for m in messages:
            if s.use_queue:
                await enqueue(m)
            else:
                background.add_task(handle_inline, m)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ----------------------------------------------------------- WhatsApp
    @app.get("/webhook/whatsapp")
    async def wa_verify(request: Request) -> PlainTextResponse:
        q = request.query_params
        token = q.get("hub.verify_token") or ""
        if (
            s.whatsapp_enabled
            and q.get("hub.mode") == "subscribe"
            and s.whatsapp_verify_token
            and constant_time_equals(token, s.whatsapp_verify_token)
        ):
            return PlainTextResponse(q.get("hub.challenge", ""))
        raise HTTPException(403, "Verification failed")

    @app.post("/webhook/whatsapp")
    async def wa_receive(request: Request, background: BackgroundTasks) -> JSONResponse:
        if not s.whatsapp_enabled:
            raise HTTPException(404)
        body = await read_body(request)
        if not whatsapp.verify_signature(body, request.headers.get("x-hub-signature-256")):
            log.warning("Rejected WhatsApp webhook with a bad signature")
            raise HTTPException(401, "Bad signature")
        try:
            payload: dict[str, Any] = json.loads(body)
        except ValueError:
            raise HTTPException(400, "Bad JSON")
        await dispatch(whatsapp.parse_webhook(payload), background)
        return JSONResponse({"ok": True})  # answer fast; Meta retries slow webhooks

    # ----------------------------------------------------------- Telegram (development)
    @app.post("/webhook/telegram")
    async def tg_receive(request: Request, background: BackgroundTasks) -> JSONResponse:
        if not s.telegram_enabled:
            raise HTTPException(404)
        if not telegram.verify_secret(request.headers.get("x-telegram-bot-api-secret-token")):
            log.warning("Rejected Telegram webhook with a bad secret")
            raise HTTPException(401, "Bad secret")
        body = await read_body(request)
        try:
            payload = json.loads(body)
        except ValueError:
            raise HTTPException(400, "Bad JSON")
        await dispatch(telegram.parse_update(payload), background)
        return JSONResponse({"ok": True})

    return app


app = create_app()
