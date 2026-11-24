"""Career, housing, health, financial growth, trusted services and user reminders."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app.db.models import UserReminder
from app.db.session import sessionmaker
from app.modules.growth.node import loan_cost, parse_spend
from app.modules.housing.node import analyse
from app.modules.reminders.store import add_month, send_due
from app.modules.services.node import NEEDS, PARTNERS
from tests.conftest import TODAY, Chat, onboard
from tests.test_guardian import events
from tests.test_tasks import fake_fx, rows

SCAM_ROOM = ("Bed space in Satwa, 6 people per room, AED 450 per month. Partition room also available. "
             "Pay deposit 1500 by transfer before viewing to book. No Ejari, cash only.")
OK_FLAT = ("Studio in Al Nahda, rent AED 3,500 per month, deposit AED 3,500, DEWA not included, 12 months contract, "
           "60 days notice, Ejari registered by landlord.")


# ------------------------------------------------------------------ hub

async def test_hub_menu(chat: Chat):
    await onboard(chat)
    r = await chat.tap("menu:grow")
    assert [row.id for row in rows(r[0])] == ["career:menu", "home:menu", "health:menu", "grow:menu", "menu:social", "svc:menu",
                                         "menu:profile"]
    handled = await events("handled_by")
    assert handled[-1] == "life_admin"


# ------------------------------------------------------------------ financial growth

async def test_savings_goal_in_home_currency(chat: Chat):
    await onboard(chat, country="Kenya")
    chat.fx_fetcher = fake_fx(35.0)
    await chat.tap("grow:goal")
    await chat.say("school fees")
    await chat.say("300000 KES")
    r = await chat.say("11/2027")          # 12 months from November 2026
    assert "AED 714 a month" in r[0].text and "35.000 KES" in r[0].text
    await chat.tap("grow:add:0")
    r = await chat.say("800")
    assert "AED 800 of 8,571" in r[0].text and "on track" in r[1].text
    r = await chat.tap("grow:remind")
    async with sessionmaker()() as s:
        rem = (await s.execute(select(UserReminder))).scalar_one()
    assert rem.kind == "savings" and rem.repeat_monthly == 1 and rem.due == date(2026, 12, 1)


async def test_family_budget_finds_pressure_points(chat: Chat):
    await onboard(chat)
    await chat.say("family budget")
    await chat.say("2000")
    r = await chat.say("rent 600, food 400, transport 150, family 900")
    text = r[0].text
    assert "Left over: AED -50" in text and "more than you earn" in text and "Family support is 45%" in text


def test_budget_and_loan_maths():
    assert parse_spend("rent 600, food: 400; family 800, other 50") == {"rent": 600, "food": 400, "family": 800, "other": 50}
    pay, total = loan_cost(5000, 2.5, 12)
    assert round(pay) == 487 and round(total) == 5849


async def test_loan_warning(chat: Chat):
    await onboard(chat)
    await chat.say("loan calculator")
    r = await chat.say("3000 10 12")
    assert "very expensive" in r[0].text and "Central Bank" in r[0].text


# ------------------------------------------------------------------ housing

def test_room_ad_flags():
    a = analyse(SCAM_ROOM)
    assert {k for k, _ in a["flags"]} >= {"pay_first", "no_ejari", "cash", "partition", "crowded"}
    b = analyse(OK_FLAT)
    assert b["rent"] == 3500 and b["deposit"] == 3500 and b["bills"] is False and not b["flags"]


async def test_check_room_before_paying(chat: Chat):
    await onboard(chat)
    await chat.say("check a room")
    r = await chat.say(SCAM_ROOM)
    assert "Don't pay yet" in r[0].text and "Law No. 4 of 2026" in r[0].text
    assert "high" in await events("housing_checked")


async def test_rent_increase_90_day_rule(chat: Chat):
    await onboard(chat)
    await chat.say("rent increase")
    await chat.say("31/03/2027")
    r = await chat.say("15/02/2027")
    assert "*44 days*" in r[0].text and "no increase applies" in r[0].text
    await chat.say("rent increase")
    await chat.say("31/03/2027")
    r = await chat.say("none")
    assert "No written notice" in r[0].text


async def test_rent_reminder_and_landlord_case(chat: Chat):
    await onboard(chat)
    await chat.tap("home:remind")
    r = await chat.say("5")
    assert "2 December 2026" in r[0].text
    r = await chat.tap("home:problem")
    assert "Landlord or housing" in r[0].text and "Rental Disputes Centre" in r[1].text


# ------------------------------------------------------------------ health

async def test_health_navigation_never_diagnoses(chat: Chat):
    await onboard(chat)
    r = await chat.say("I am sick")
    assert "998" in r[0].text and "don't diagnose" in r[0].text
    r = await chat.tap("health:insurance")
    assert "employer pays" in r[0].text.lower() and "1 January 2025" in r[0].text
    r = await chat.tap("health:noins")
    assert "task:form:insurance" in chat.ids_of(r)
    r = await chat.tap("task:form:insurance")
    await chat.say("Al Noor LLC")
    r = await chat.say("HR Manager")
    assert r[0].file and r[0].file.startswith(b"%PDF")


async def test_appointment_reminder(chat: Chat, kv):
    await onboard(chat)
    await chat.say("appointment")
    await chat.say("25/11/2026 10:30")
    r = await chat.say("eye clinic, Karama")
    assert "25 November 2026 at 10:30" in r[0].text
    sent = []

    async def send(rem):
        sent.append(rem)
        return True

    async with sessionmaker()() as s:
        assert await send_due(s, send, date(2026, 11, 24)) == 1
        assert (await s.execute(select(UserReminder))).first() is None      # one-off: removed after sending
    assert "eye clinic" in sent[0].text


# ------------------------------------------------------------------ career

async def test_career_plan_cv_and_applications(chat: Chat):
    await onboard(chat, name="Wanjiru")
    await chat.tap("career:path")
    await chat.tap("career:now:housekeeping")
    await chat.say("3")
    r = await chat.say("1 3")
    text = r[0].text
    assert "Housekeeping supervisor" in text and "room inspection standards" in text.split("To build")[0]
    assert "team scheduling" in text.split("To build")[1]
    await chat.tap("career:cv")
    r = await chat.say("English, Swahili")
    assert r[0].file.startswith(b"%PDF")


async def test_career_applications_and_interview(chat: Chat):
    await onboard(chat, name="Wanjiru")
    await chat.tap("career:add")
    r = await chat.say("Hilton, housekeeping supervisor")
    assert "career:app:0" in chat.ids_of(r)
    await chat.tap("career:app:0")
    await chat.tap("career:st:1:0")
    r = await chat.say((TODAY + timedelta(days=10)).strftime("%d/%m/%Y"))
    assert "Interview saved" in r[0].text
    r = await chat.tap("career:interview")
    assert "never asks you to pay" in r[0].text
    assert "career" in await events("handled_by")


async def test_job_change_rules(chat: Chat):
    await onboard(chat)
    r = await chat.say("change job")
    assert "one year" in r[0].text and "probation" in r[0].text


# ------------------------------------------------------------------ services

def test_directory_never_lists_unchecked_businesses():
    assert PARTNERS == ()
    for _, (_, items) in NEEDS.items():
        for s in items:
            assert s.tier in ("official", "licensed", "community")
            if s.tier == "licensed":
                assert "check" in s.how.lower()        # always says how to verify


async def test_services_lookup(chat: Chat):
    await onboard(chat)
    r = await chat.say("find help")
    assert "svc:housing" in chat.ids_of(r)
    r = await chat.tap("svc:housing")
    assert "Official" in r[0].text and "Licensed" in r[0].text and "licence number" in r[1].text


def test_add_month_clamps():
    assert add_month(date(2027, 1, 31)) == date(2027, 2, 28) and add_month(date(2026, 12, 5)) == date(2027, 1, 5)


async def test_life_manager_shows_upcoming_reminders(chat: Chat):
    await onboard(chat)
    await chat.say("appointment")
    await chat.say("21/11/2026")
    await chat.say("dentist")
    r = await chat.say("brief")
    assert "Appointment: dentist" in r[0].text
