"""Webhook authentication and WhatsApp message limits (UX + reliability)."""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

from app.agent import ui
from app.channels import telegram, whatsapp
from app.db.models import User
from app.i18n import S, SUPPORTED_LANGUAGES


def _sig(body: bytes, secret: str = "test-app-secret") -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


WA_PAYLOAD = {
    "entry": [{"changes": [{"value": {
        "metadata": {"phone_number_id": "111"},
        "messages": [{"from": "254700000001", "id": "wamid.1", "type": "text", "text": {"body": "hi"}}],
    }}]}]
}


@pytest.fixture
def client(monkeypatch):
    import app.main as main
    calls = []

    async def fake_inline(m):
        calls.append(m)

    monkeypatch.setattr(main, "handle_inline", fake_inline)
    app = main.create_app()
    with TestClient(app) as c:
        c.calls = calls  # type: ignore[attr-defined]
        yield c


def test_whatsapp_rejects_bad_signature(client):
    body = json.dumps(WA_PAYLOAD).encode()
    assert client.post("/webhook/whatsapp", content=body, headers={"x-hub-signature-256": "sha256=bad"}).status_code == 401
    assert client.post("/webhook/whatsapp", content=body).status_code == 401
    assert client.calls == []


def test_whatsapp_accepts_good_signature(client):
    body = json.dumps(WA_PAYLOAD).encode()
    r = client.post("/webhook/whatsapp", content=body, headers={"x-hub-signature-256": _sig(body)})
    assert r.status_code == 200 and len(client.calls) == 1
    assert client.calls[0].external_id == "254700000001"


def test_whatsapp_rejects_oversized_body(client):
    body = b"{" + b" " * 600_000 + b"}"
    assert client.post("/webhook/whatsapp", content=body, headers={"x-hub-signature-256": _sig(body)}).status_code == 413


def test_whatsapp_verification_handshake(client):
    ok = client.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "test-verify-token", "hub.challenge": "42"})
    assert ok.status_code == 200 and ok.text == "42"
    bad = client.get("/webhook/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"})
    assert bad.status_code == 403


def test_whatsapp_ignores_messages_for_other_numbers():
    p = json.loads(json.dumps(WA_PAYLOAD))
    p["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "999"
    assert whatsapp.parse_webhook(p) == []


def test_telegram_secret_and_private_chats_only(client):
    upd = {"message": {"message_id": 1, "chat": {"id": 5, "type": "private"}, "text": "hi"}}
    assert client.post("/webhook/telegram", json=upd).status_code == 401
    assert client.post("/webhook/telegram", json=upd, headers={"x-telegram-bot-api-secret-token": "test-telegram-secret"}).status_code == 200
    group = {"message": {"message_id": 2, "chat": {"id": -9, "type": "group"}, "text": "hi"}}
    assert telegram.parse_update(group) == []


def test_docs_hidden_in_production(monkeypatch):
    from app.config import get_settings
    import app.main as main
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "x" * 44)
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    get_settings.cache_clear()
    app = main.create_app()
    assert app.docs_url is None and app.openapi_url is None


def test_production_refuses_to_start_without_secrets(monkeypatch):
    from app.config import Settings
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FIELD_ENCRYPTION_KEY", "")
    with pytest.raises(ValueError, match="Missing required settings"):
        Settings()


# ------------------------------------------------------------------ WhatsApp UI limits, every screen, both languages

def _all_screens(lang: str):
    u = User(channel="whatsapp", identity_hash="x", language=lang, consent_status="granted", step="ready",
             journey_stage="offer", home_country="Kenya", visa_type="visit", sector="hospitality", notifications_paused=0)
    yield ui.consent_prompt(lang, welcome=True)
    yield ui.consent_prompt(lang)
    yield ui.consent_prompt(lang, more=True, updated=True)
    yield ui.name_prompt(lang)
    yield ui.stage_prompt(lang, u)
    yield ui.country_prompt(lang)
    yield ui.visa_prompt(lang)
    yield ui.expiry_prompt(lang)
    yield ui.sector_prompt(lang)
    yield ui.summary_prompt(lang, u)
    yield ui.edit_menu(lang)
    yield ui.main_menu(lang)
    yield ui.profile_view(lang, u)
    yield ui.help_message(lang)
    yield ui.privacy_menu(lang)
    yield ui.export_message(lang, u)
    yield ui.delete_confirm(lang, "abcd1234")


@pytest.mark.parametrize("lang", SUPPORTED_LANGUAGES)
def test_every_screen_fits_whatsapp_limits(lang):
    for screen in _all_screens(lang):
        assert len(screen.buttons) <= 3
        for b in screen.buttons:
            assert len(b.title) <= 20, b.title
            assert len(b.id) <= 64
        if screen.menu:
            assert len(screen.menu.rows) <= 10 and len(screen.menu.button) <= 20
            for r in screen.menu.rows:
                assert len(r.title) <= 24, r.title
                assert r.description is None or len(r.description) <= 72, r.description
        if screen.buttons or screen.menu:
            assert len(screen.text) <= 1024, screen.text[:60]
        payload = whatsapp.to_payload("254700000001", screen)
        assert payload["type"] in ("text", "interactive")


def test_every_string_has_english():
    assert all("en" in v for v in S.values())


def test_telegram_renders_bold_safely():
    from app.channels.base import Outgoing
    from app.channels.telegram import to_payload

    body = to_payload("1", Outgoing(text="⛔ *You can't work* on a <visit> visa & see https://u.ae/a_b_c"))
    assert body["parse_mode"] == "HTML"
    assert body["text"] == "⛔ <b>You can't work</b> on a &lt;visit&gt; visa &amp; see https://u.ae/a_b_c"
