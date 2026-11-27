"""Module 3: Stay Legal."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import select, text

from app.channels import whatsapp
from app.db import repo
from app.db.models import AuditLog, User
from app.db.session import sessionmaker
from app.modules.stay_legal import node as legal
from app.modules.stay_legal.medicines import check_medicine, find_medicines
from app.modules.stay_legal.visa import send_due_reminders, visa_status
from app.security.output_guard import check_output
from app.security.ratelimit import MemoryKV
from tests.conftest import TODAY, Chat, onboard
from tests.test_documents import JPEG, FakeVision, loader_for

# ------------------------------------------------------------------ medicines


@pytest.mark.parametrize(
    "text,status,ingredient",
    [
        ("Tramadol 50mg", "controlled", "tramadol"),
        ("XANAX 0.5", "controlled", "alprazolam"),
        ("Lyrica 75 mg capsules", "controlled", "pregabalin"),
        ("Ritalin", "controlled", "methylphenidate"),
        ("Panadol Extra with Codeine", "controlled", "codeine"),     # most serious wins
        ("Dihydrocodeine tablets", "controlled", "dihydrocodeine"),
        ("Stilnox", "controlled", "zolpidem"),
        ("CBD oil drops", "banned", ""),
        ("Panadol", "common", "paracetamol"),
        ("Augmentin 625", "common", "amoxicillin (antibiotic)"),
        ("Zyrtec", "common", "cetirizine (antihistamine)"),
        ("Vitamin C", "unknown", ""),
    ],
)
def test_medicine_lookup(text, status, ingredient):
    m = check_medicine(text)
    assert m.status == status and m.ingredient == ingredient


def test_codeine_not_matched_inside_other_words():
    assert [m.ingredient for m in find_medicines("dihydrocodeine")] == ["dihydrocodeine"]


def test_unknown_is_never_reported_as_allowed():
    r, status = legal.medicine_result("Some new pill", "en")
    assert status == "unknown" and "check the official" in r.text and "not* on the UAE controlled list" not in r.text


# ------------------------------------------------------------------ intents

@pytest.mark.parametrize(
    "text,intent",
    [
        ("I am on a visit visa, can I start working?", "work_visit"),
        ("Can I work with a tourist visa?", "work_visit"),
        ("can I bring tramadol to Dubai", "medicine"),
        ("what time is it", None),
        ("my employer pays my salary late", None),
    ],
)
def test_legal_intent(text, intent):
    assert legal.legal_intent(text) == intent


# ------------------------------------------------------------------ my visa view

def _user(expiry: date | None, visa="employment", paused=0) -> User:
    u = User(channel="whatsapp", identity_hash="h", language="en", visa_type=visa, notifications_paused=paused, consent_status="granted")
    repo.set_field(u, "visa_expiry", expiry)
    return u


@pytest.mark.parametrize(
    "offset,expect",
    [(60, "🟢"), (20, "🟠"), (5, "🔴"), (0, "expires *today*"), (-10, "AED 500")],
)
def test_visa_status_levels(offset, expect):
    out = visa_status(_user(TODAY + timedelta(days=offset)), TODAY, "en")
    assert expect in out.text


def test_visa_status_without_date_offers_to_add_it():
    out = visa_status(_user(None), TODAY, "en")
    assert "don't have your visa expiry" in out.text and out.buttons[0].id == "legal:visa_set"


def test_expired_visa_points_to_official_checks():
    out = visa_status(_user(TODAY - timedelta(days=3)), TODAY, "en")
    assert "AED 150" in out.text and out.buttons[0].id == "legal:visa_check"
    assert "Check your exact fine" in out.text


# ------------------------------------------------------------------ reminders

async def _make_users(kv):
    """One user per offset, plus a paused user and an unconsented one."""
    offsets = [30, 14, 7, 3, 1, 0, -1, 5, 100]
    for i, off in enumerate(offsets):
        c = Chat(kv, phone=f"2547000001{i:02d}")
        await onboard(c, name=f"User{i}")
        async with sessionmaker()() as s:
            u = (await s.execute(select(User).where(User.identity_hash == repo.hash_identity("whatsapp", c.phone)))).scalar_one()
            repo.set_field(u, "visa_expiry", TODAY + timedelta(days=off))
            await s.commit()
    paused = Chat(kv, phone="254700000900")
    await onboard(paused)
    await paused.say("stop")
    pending = Chat(kv, phone="254700000901")
    await pending.say("hi")  # never agreed


async def test_reminders_sent_on_schedule_once(kv):
    await _make_users(kv)
    sent = []

    async def send(r):
        sent.append((r.days, r.to, r.text))
        return True

    reminder_kv = MemoryKV()
    async with sessionmaker()() as s:
        n = await send_due_reminders(s, reminder_kv, send, TODAY)
    assert n == 7 and sorted(d for d, _, _ in sent) == [-1, 0, 1, 3, 7, 14, 30]
    assert all(to.startswith("2547000001") for _, to, _ in sent)     # decrypted only to send
    assert any("expired yesterday" in t for d, _, t in sent if d == -1)
    async with sessionmaker()() as s:
        assert await send_due_reminders(s, reminder_kv, send, TODAY) == 0   # no duplicates
        events = list((await s.execute(select(AuditLog.event, AuditLog.detail))).all())
    assert sum(1 for e, _ in events if e == "visa_reminder_sent") == 7


async def test_failed_reminder_is_retried_next_run(kv):
    c = Chat(kv)
    await onboard(c)  # visa expires 15 March 2027
    expiry = date(2027, 3, 15)
    day = expiry - timedelta(days=7)
    reminder_kv = MemoryKV()

    async def fail(r):
        return False

    async def ok(r):
        return True

    async with sessionmaker()() as s:
        assert await send_due_reminders(s, reminder_kv, fail, day) == 0
        assert await send_due_reminders(s, reminder_kv, ok, day) == 1


async def test_whatsapp_reminders_need_a_template(monkeypatch):
    import app.worker as worker
    from app.config import get_settings
    from app.modules.stay_legal.visa import Reminder

    r = Reminder("u1", "whatsapp", "254700000001", 7, "text", ["Amina", "15 March 2027", "7"])
    get_settings.cache_clear()
    assert await worker.send_reminder(r) is False                    # no template configured
    calls = []

    async def fake_send_template(client, to, name, lang, params):
        calls.append((to, name, lang, params))

    monkeypatch.setenv("WHATSAPP_VISA_TEMPLATE", "visa_expiry_reminder")
    get_settings.cache_clear()
    monkeypatch.setattr(worker, "send_template", fake_send_template)
    monkeypatch.setattr(worker, "_client", lambda ch: object())
    assert await worker.send_reminder(r) is True
    assert calls == [("254700000001", "visa_expiry_reminder", "en", ["Amina", "15 March 2027", "7"])]


def test_template_payload_shape():
    p = whatsapp.template_payload("254700000001", "visa_expiry_reminder", "en", ["Amina", "15 March 2027", "7"])
    assert p["type"] == "template" and p["template"]["name"] == "visa_expiry_reminder"
    assert [x["text"] for x in p["template"]["components"][0]["parameters"]] == ["Amina", "15 March 2027", "7"]


# ------------------------------------------------------------------ conversations

async def test_menu_has_stay_legal_second(chat: Chat):
    await onboard(chat)
    r = await chat.say("menu")
    assert chat.ids_of(r)[1] == "menu:job" and "menu:legal" in chat.ids_of(await chat.tap("menu:more"))
    r = await chat.tap("menu:legal")
    assert chat.ids_of(r) == ["legal:visa", "legal:work", "legal:med", "legal:post", "legal:rules"]


async def test_add_visa_date_from_my_visa(chat: Chat):
    await chat.say("hi"); await chat.tap("consent:yes"); await chat.say("Ali")
    await chat.tap("stage:arrived"); await chat.tap("country:India"); await chat.tap("visa:none")
    await chat.tap("sector:retail"); await chat.tap("summary:ok")
    r = await chat.say("my visa")
    assert "don't have your visa expiry" in r[0].text
    r = await chat.tap("legal:visa_set")
    assert "When does your visa expire" in r[0].text
    r = await chat.say("29/11/2026")
    assert r[0].text == "Saved ✅" and "10 days left" in r[1].text and "29 November 2026" in r[1].text


async def test_visa_check_links(chat: Chat):
    await onboard(chat)
    await chat.say("my visa")
    r = await chat.tap("legal:visa_check")
    assert "https://www.gdrfad.gov.ae" in r[0].text and "https://smartservices.icp.gov.ae" in r[0].text


@pytest.mark.parametrize("key,expect", [
    ("visit", "can't work on a visit"), ("later", "80084"), ("second", "part-time work permit"),
    ("family", "no-objection letter"), ("heat", "600590000"),
])
async def test_work_answers(chat: Chat, key, expect):
    await onboard(chat)
    await chat.tap("legal:work")
    r = await chat.tap(f"work:{key}")
    assert expect in r[0].text and "not legal advice" in r[0].text


@pytest.mark.parametrize("key,expect", [
    ("people", "without their permission"), ("accident", "999"), ("news", "official sources"),
    ("complaint", "Online insults"), ("fundraise", "AED 500,000"),
])
async def test_post_answers(chat: Chat, key, expect):
    await onboard(chat)
    await chat.tap("legal:post")
    r = await chat.tap(f"post:{key}")
    assert expect in r[0].text


async def test_everyday_rules(chat: Chat):
    await onboard(chat)
    r = await chat.say("rules")
    assert "Jaywalking" in r[0].text and "https://www.ede.gov.ae" in r[0].text


async def test_medicine_check_typed_and_photo(chat: Chat):
    await onboard(chat)
    r = await chat.tap("legal:med")
    assert "Type the medicine name" in r[0].text
    r = await chat.say("Xanax")
    assert "controlled medicine" in r[0].text and "alprazolam" in r[0].text
    chat.media_loader, chat.doc_model = loader_for(JPEG), FakeVision("RIVOTRIL 2 mg\nclonazepam\n30 tablets")
    await chat.tap("legal:med")
    r = await chat.media("image")
    assert "Rivotril" in r[0].text or "Clonazepam" in r[0].text
    chat.doc_model = FakeVision("Best before 2027. Store below 25C.")
    await chat.tap("legal:med")
    r = await chat.media("image")
    assert "couldn't find a medicine name" in r[0].text


async def test_free_text_questions_answered_directly(chat: Chat):
    await onboard(chat)
    r = await chat.say("Can I bring codeine cough syrup?")
    assert "controlled medicine" in r[0].text
    r = await chat.say("I'm here on a visit visa, can I start a job?")
    assert "can't work on a visit" in r[0].text


async def test_job_offer_mentioning_visit_visa_still_goes_to_job_check(chat: Chat):
    await onboard(chat)
    offer = ("We are hiring waiters for a Dubai hotel. Salary AED 2000 per month. Come on a visit visa and the "
             "visa will be changed after you arrive. Contact our agency to apply.")
    r = await chat.say(offer)
    assert "This looks like a job offer" in r[0].text


async def test_commands_work_while_waiting_for_medicine(chat: Chat):
    await onboard(chat)
    await chat.tap("legal:med")
    r = await chat.say("menu")
    assert "What would you like to do" in r[0].text
    await chat.tap("legal:med")
    r = await chat.say("my visa")
    assert "My visa" in r[0].text


async def test_medicine_names_are_never_stored(chat: Chat):
    await onboard(chat)
    await chat.tap("legal:med")
    await chat.say("Tramadol")
    async with sessionmaker()() as s:
        rows = [" ".join(map(str, r)) for t in ("users", "audit_log") for r in (await s.execute(text(f"select * from {t}"))).all()]
    assert not any("ramadol" in r.lower() for r in rows)
    assert any("medicine_checked" in r and "status=controlled" in r for r in rows)


def test_official_numbers_survive_output_guard():
    out = check_output(legal.work_answer("heat", "en").text)
    assert "600590000" in out.text


def test_stay_legal_screens_fit_whatsapp_limits():
    u = _user(TODAY + timedelta(days=5))
    screens = [legal.legal_menu("en"), legal.work_menu("en"), legal.post_menu("en"), legal.rules_message("en"),
               legal.medicine_prompt("en"), visa_status(u, TODAY, "en"), visa_status(_user(None), TODAY, "en"),
               visa_status(_user(TODAY - timedelta(days=400)), TODAY, "en")]
    screens += [legal.work_answer(k, "en") for k in legal.WORK] + [legal.post_answer(k, "en") for k in legal.POST]
    screens += [legal.medicine_result(x, "en")[0] for x in ("Xanax", "CBD", "Panadol", "unknown thing")]
    for s in screens:
        assert len(s.text) <= 4096
        if s.buttons:
            assert len(s.buttons) <= 3 and all(len(b.title) <= 20 for b in s.buttons) and len(s.text) <= 1024, s.text[:50]
        if s.menu:
            assert len(s.menu.rows) <= 10 and all(len(r.title) <= 24 and len(r.description or "") <= 72 for r in s.menu.rows)
            assert len(s.text) <= 1024
        whatsapp.to_payload("254700000001", s)
