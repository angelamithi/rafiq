"""Lead task: the renewals calendar (visa, Emirates ID, passport, family visa, Ejari)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.db import repo
from app.db.models import UserReminder
from app.db.session import sessionmaker
from app.modules.renewals.node import late_fee, reminder_dates, warnings
from tests.conftest import Chat, onboard
from tests.test_guardian import events
from tests.test_tasks import db_user


async def test_renewals_is_first_in_the_menu(chat: Chat):
    await onboard(chat)
    r = await chat.say("menu")
    assert "rnw:menu" in chat.ids_of(await chat.tap("menu:more"))


async def test_overview_uses_known_dates_and_flags_a_short_passport(chat: Chat):
    await onboard(chat)                                    # visa expires 15 March 2027
    r = await chat.say("my renewals")
    assert "Residence visa (employment)" in r[0].text and "15 March 2027" in r[0].text
    await chat.tap("rnw:date:passport")
    await chat.say("01/06/2027")
    r = await chat.tap("rnw:menu")
    assert "less than 6 months after your visa expires" in r[0].text
    assert "life_admin" in await events("handled_by")


async def test_visa_steps_documents_and_reminders(chat: Chat):
    await onboard(chat)
    r = await chat.say("renew my visa")
    assert "employer" in r[0].text.lower() and "medical fitness" in r[0].text and "AED 50 a day" in r[0].text
    r = await chat.tap("rnw:docs:residence")
    assert "0 of 7 ready" in r[0].text
    r = await chat.tap("rnw:tick:residence:0")
    assert "1 of 7 ready" in r[0].text and r[0].menu.rows[0].title.startswith("✅")
    await chat.tap("rnw:date:residence")
    r = await chat.say("15/03/2027")
    assert "14 January 2027" in r[0].text                 # 60 days before
    async with sessionmaker()() as s:
        due = sorted(x.due for x in (await s.execute(select(UserReminder).where(UserReminder.kind == "rn_residence"))).scalars())
    assert due == [date(2027, 1, 14), date(2027, 2, 13), date(2027, 3, 8)]
    r = await chat.tap("rnw:pack:residence")
    assert r[0].file.startswith(b"%PDF")


async def test_done_sets_the_next_cycle(chat: Chat):
    await onboard(chat)
    await chat.tap("rnw:st:residence:3")
    r = await chat.say("15/03/2029")
    assert "New expiry" in r[0].text
    assert repo.get_visa_expiry(await db_user(chat)) == date(2029, 3, 15)
    assert "residence:Done" not in await events("renewal_status") and "residence" in await events("renewal_done")


async def test_emirates_id_late_fee(chat: Chat):
    await onboard(chat)
    await chat.tap("rnw:date:eid")
    r = await chat.say("01/09/2026")                       # 79 days before 19 Nov 2026
    assert "AED 980" in r[1].text


def test_rules():
    assert late_fee("eid", 20) is None and late_fee("eid", 31) == 20 and late_fee("eid", 400) == 1000
    assert late_fee("residence", 10) is None
    today = date(2026, 11, 19)
    assert reminder_dates("eid", date(2026, 12, 1), today) == [date(2026, 11, 24)]
    w = warnings({"residence": date(2027, 3, 15), "passport": date(2027, 6, 1), "eid": date(2026, 1, 1)}, "en")
    assert len(w) == 2


# ---- official sites and forwarded status messages ----------------------------
from app.modules.renewals.node import looks_official, read_update  # noqa: E402

SUBMITTED = "Dear customer, your residence visa renewal application No. 2045871236 has been received by GDRFA Dubai and is under process."
APPROVED = "ICP: Your Emirates ID application no. 784199001122 has been approved and printed. Card valid until 20/04/2029."
RETURNED = "GDRFA: Application 30112233445 for residence renewal was returned. Additional documents required."
SCAM = "ICP: your Emirates ID renewal is approved. Pay AED 370 delivery fee now at http://icp-uae-pay.xyz/card or your card will be cancelled"


def test_reader_rules():
    assert looks_official(SUBMITTED) and looks_official(APPROVED)
    assert not looks_official("how do I renew my visa?")
    up = read_update(SUBMITTED)
    assert (up.status, up.key, up.ref, up.suspicious) == ("Submitted", "residence", "2045871236", False)
    up = read_update(APPROVED)
    assert (up.status, up.key, up.new_expiry) == ("Done", "eid", date(2029, 4, 20))
    assert read_update(RETURNED).status == "Action needed"
    assert read_update(SCAM).suspicious


async def test_view_shows_only_official_links(chat: Chat):
    await onboard(chat)
    r = await chat.say("renew my visa")
    assert "https://gdrfad.gov.ae" in r[0].text and "never through a link in a message" in r[0].text
    assert "rnw:sms:residence" in chat.ids_of(r)


async def test_pasted_sms_updates_status_without_storing_the_message(chat: Chat):
    await onboard(chat)
    r = await chat.say(SUBMITTED)
    assert "Submitted" in r[0].text and "2045871236" in r[0].text
    r = await chat.say("renew my visa")
    assert "*Status:* Submitted (application 2045871236)" in r[0].text
    assert "under process" not in str(repo.toolkit(await db_user(chat)))
    r = await chat.say(RETURNED)
    assert "Action needed" in r[0].text and any("Documents for" in (m.text or "") for m in r)


async def test_approved_sms_sets_next_cycle_and_scam_is_flagged(chat: Chat):
    await onboard(chat)
    await chat.tap("rnw:sms:eid")
    r = await chat.say(APPROVED)
    assert "New expiry 20 April 2029" in " ".join(m.text or "" for m in r)
    r = await chat.say(SCAM)
    assert "Careful" in r[0].text and "haven't changed" in r[0].text
    assert "icp-uae-pay" not in " ".join(m.text or "" for m in r)
    assert "New expiry" not in " ".join(m.text or "" for m in r)


async def test_unclear_sms_asks_which_renewal(chat: Chat):
    await onboard(chat)
    r = await chat.say("Amer: application no. 99887766 has been received and is under process. Thank you.")
    assert "Which renewal" in r[-1].text
    r = await chat.tap("rnw:apply:family")
    assert "Family visa" in r[0].text and "Submitted" in r[0].text


# ---- Status check: one look across visa, passport, pay, insurance, housing ---------------
from app.modules.renewals import check as chk  # noqa: E402


async def answer_all(chat: Chat, picks: dict[str, int]):
    r = None
    for q in chk.QUESTIONS:
        r = await chat.tap(f"rnw:q:{q.key}:{picks.get(q.key, 0)}")
    return r


async def test_check_asks_tap_questions_then_all_green(chat: Chat):
    await onboard(chat)
    r = await chat.say("am I ok?")
    assert "Status check" in r[0].text and "rnw:q:passport:0" in chat.ids_of(r)
    r = await answer_all(chat, {})
    assert "0 red" in r[0].text and "🟢 *Health insurance*" in r[0].text
    assert "life_admin" in await events("handled_by")


async def test_check_hands_each_problem_to_the_right_agent(chat: Chat):
    await onboard(chat)
    await chat.tap("rnw:check")
    r = await answer_all(chat, {"passport": 1, "insurance": 1, "renewing": 1, "pay": 2, "home": 2})
    text = r[0].text
    assert "4 red" not in text and "🔴 *Passport*" in text and "Protection" in text
    assert "taken from your pay" in text and "Wellbeing" in text
    ids = chat.ids_of(r)
    for target in ("pro:help", "health:insurance", "career:change", "pay:watch", "home:rights"):
        assert target in ids, target
    assert any(e.startswith("Passport>Protection") for e in await events("status_handoff"))
    # follow one handoff: it lands in the Protection agent
    await chat.tap("pro:help")
    assert "protection" in await events("handled_by")


async def test_check_uses_known_pay_gaps_and_can_be_redone(chat: Chat):
    await onboard(chat)
    await chat.tap("rnw:check")
    await answer_all(chat, {})
    r = await chat.tap("rnw:check:again")
    assert "1/5" in r[-1].text


def test_short_passport_is_amber_with_dates():
    today = date(2026, 11, 24)
    found = chk.items({"residence": date(2027, 3, 15), "passport": date(2027, 6, 1)}, {"passport": 0}, today, None)
    p = next(i for i in found if i.title == "Passport")
    assert p.level == chk.AMBER and p.action == "rnw:view:passport"
    v = next(i for i in found if i.title == "Residence visa")
    assert v.level == chk.GREEN
