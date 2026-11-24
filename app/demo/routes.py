"""Judges' demo: a web chat on the same pipeline as WhatsApp, plus the impact page.

Security:
- Off unless DEMO_ENABLED=true. A shared access code (DEMO_ACCESS_CODE, given
  to judges) starts a session; wrong codes are rate-limited.
- The session id lives in an HttpOnly, Secure, SameSite=Strict cookie signed
  with HMAC, so it can't be forged or read by page scripts.
- Every message goes through the normal pipeline: rate limits, injection
  scan, orchestrator, agent allow-lists, output guard. The demo adds no
  shortcuts and no admin powers.
- Demo users are channel "web" and are removed by the normal retention job.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.channels.base import Incoming
from app.config import get_settings

COOKIE = "rafiq_demo"
router = APIRouter()


class _Store:
    """Thin wrapper so tests can swap Redis for a fake."""

    def __init__(self) -> None:
        self._r: Any = None

    @property
    def r(self) -> Any:
        if self._r is None:
            from app.channels.web import _redis

            self._r = _redis()
        return self._r


_store = _Store()


def _sign(sid: str) -> str:
    key = get_settings().id_hash_pepper.encode()
    return hmac.new(key, f"demo:{sid}".encode(), hashlib.sha256).hexdigest()[:32]


def _session(request: Request) -> str:
    raw = request.cookies.get(COOKIE) or ""
    sid, _, sig = raw.partition(".")
    if not sid or not sig or not hmac.compare_digest(sig, _sign(sid)):
        raise HTTPException(401, "Please enter the demo code")
    return sid


def _enabled() -> None:
    if not get_settings().demo_enabled:
        raise HTTPException(404)


class Login(BaseModel):
    code: str = Field(max_length=100)


class Send(BaseModel):
    text: str | None = Field(default=None, max_length=4000)
    button_id: str | None = Field(default=None, max_length=64)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    file_b64: str | None = Field(default=None, max_length=4_100_000)


@router.get("/demo", response_class=HTMLResponse)
async def page() -> HTMLResponse:
    _enabled()
    from app.demo.page import PAGE

    return HTMLResponse(PAGE, headers={"Cache-Control": "no-store",
                                       "Content-Security-Policy": "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                                       "script-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"})


@router.post("/demo/api/login")
async def login(body: Login, request: Request) -> JSONResponse:
    _enabled()
    s = get_settings()
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0].strip()
    key = f"demo:login:{hashlib.sha256(ip.encode()).hexdigest()[:16]}"
    tries = await _store.r.incr(key)
    if tries == 1:
        await _store.r.expire(key, 3600)
    if tries > 20:
        raise HTTPException(429, "Too many tries. Try again in an hour.")
    if not s.demo_access_code or not hmac.compare_digest(body.code.strip(), s.demo_access_code):
        raise HTTPException(403, "That code isn't right")
    sid = secrets.token_hex(16)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(COOKIE, f"{sid}.{_sign(sid)}", max_age=60 * 60 * 24, httponly=True, secure=s.is_production,
                    samesite="strict", path="/demo")
    return resp


async def _run(msg: Incoming) -> None:
    s = get_settings()
    if s.use_queue:
        from arq import create_pool

        from app.worker import _redis_settings

        pool = await create_pool(_redis_settings())
        try:
            job = await pool.enqueue_job("process_incoming", msg.model_dump(), _job_id=f"msg:web:{msg.message_id}")
            if job is not None:
                await job.result(timeout=120)
        finally:
            await pool.aclose()
    else:
        from app.worker import handle_inline

        await handle_inline(msg)


async def _agent_for(sid: str) -> str | None:
    from sqlalchemy import select

    from app.db import repo
    from app.db.models import AuditLog, User
    from app.db.session import sessionmaker

    async with sessionmaker()() as s:
        uid = (await s.execute(select(User.id).where(User.identity_hash == repo.hash_identity("web", sid)))).scalar()
        if not uid:
            return None
        return (await s.execute(select(AuditLog.detail).where(AuditLog.user_ref == uid, AuditLog.event == "handled_by")
                                .order_by(AuditLog.id.desc()).limit(1))).scalar()


@router.post("/demo/api/send")
async def send(body: Send, request: Request) -> JSONResponse:
    _enabled()
    sid = _session(request)
    mid = uuid.uuid4().hex
    if body.file_b64:
        try:
            data = base64.b64decode(body.file_b64, validate=True)
        except ValueError:
            raise HTTPException(400, "Bad file")
        from app.channels.web import MAX_UPLOAD, store_media
        from app.media.reader import sniff

        mime = sniff(data)
        if len(data) > MAX_UPLOAD or mime is None:
            raise HTTPException(400, "Send a photo (JPG/PNG) or PDF under 3 MB")
        await store_media(_store.r, mid, data)
        msg = Incoming(channel="web", external_id=sid, message_id=mid, kind="media",
                       media_type="document" if mime == "application/pdf" else "image", media_id=mid)
    elif body.latitude is not None and body.longitude is not None:
        msg = Incoming(channel="web", external_id=sid, message_id=mid, kind="location",
                       latitude=round(body.latitude, 5), longitude=round(body.longitude, 5))
    elif body.button_id:
        msg = Incoming(channel="web", external_id=sid, message_id=mid, kind="button", button_id=body.button_id)
    elif body.text and body.text.strip():
        msg = Incoming(channel="web", external_id=sid, message_id=mid, text=body.text)
    else:
        raise HTTPException(400, "Empty message")
    await _run(msg)
    from app.channels.web import drain

    return JSONResponse({"replies": await drain(_store.r, sid), "agent": await _agent_for(sid)})


@router.get("/demo/api/impact")
async def impact(request: Request) -> JSONResponse:
    _enabled()
    _session(request)
    from app.db.session import sessionmaker
    from app.demo.impact import compute

    async with sessionmaker()() as s:
        all_time = await compute(s)
        last30 = await compute(s, 30)
    report = None
    try:
        from pathlib import Path

        p = Path(__file__).resolve().parents[2] / "evals" / "report.md"
        report = p.read_text().split("\n\n")[1] if p.exists() else None
    except OSError:
        pass
    return JSONResponse({"all_time": all_time, "last_30_days": last30, "eval": report})
