"""Status check: one look at everything a resident's status depends on.

Almost everything in a resident's life hangs on the residence visa: the job,
the Emirates ID, health insurance, housing, the right to stay. A renewal
depends on all of them. So the check looks at each requirement, marks it
red / amber / green with one plain reason, and hands each problem to the agent
that can fix it (Protection, Employment, Wellbeing, Housing, Career, Financial).

What Rafiq doesn't already know is asked with up to five tap-only questions
(no free text, so nothing to inject). Answers are kept in the encrypted
toolkit and can be changed with "Check again".

Rules checked 2026-11-24: employers may not keep a worker's passport or other
official documents (MOHRE; Federal Decree-Law 33 of 2021); health insurance for
private-sector and domestic workers is employer-paid in every emirate since
1 Jan 2025 and may not be deducted from pay in Dubai (MOHRE, DHA); Dubai Law
No. 4 of 2026 limits shared housing to owners and licensed operators.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.i18n import S, fmt_date, t

RED, AMBER, GREEN = "🔴", "🟠", "🟢"


@dataclass(frozen=True)
class Question:
    key: str
    text: str
    options: tuple[str, ...]


QUESTIONS: tuple[Question, ...] = (
    Question("passport", "Who has your passport right now?", ("I have it", "My employer", "Agent / someone else")),
    Question("insurance", "Your health insurance:", ("Employer pays", "Taken from my pay", "I have no card")),
    Question("renewing", "Is your employer renewing your visa?", ("Yes", "I'm changing jobs", "Not sure")),
    Question("pay", "Last month's salary:", ("Paid in full", "Part paid", "Not paid")),
    Question("home", "Where do you live?", ("Flat or room I rent", "Employer housing", "Bed space / shared")),
)


@dataclass(frozen=True)
class Item:
    level: str
    title: str
    why: str
    action: str | None = None      # button id of the agent that can fix it
    agent: str | None = None
    label: str | None = None


STRINGS: dict[str, dict[str, str]] = {
    "chk_intro": {"en": "✅ *Status check*: a quick check of everything your residency depends on. {n} quick question{s} first (tap an answer)."},
    "chk_q": {"en": "{i}/{n} · {text}"},
    "chk_head": {"en": "🧭 *Status check*  {red} red · {amber} to watch · {green} fine\n"},
    "chk_line": {"en": "{icon} *{title}*: {why}{agent}"},
    "chk_all_green": {"en": "\nEverything I can see looks fine. I'll keep watching your dates."},
    "chk_next": {"en": "Tap a problem to fix it. Each one goes to the right specialist."},
    "btn_chk": {"en": "Status check"},
    "btn_chk_again": {"en": "Check again"},
}
S.update(STRINGS)


def pending(answers: dict[str, int]) -> list[Question]:
    return [q for q in QUESTIONS if q.key not in answers]


def question_message(q: Question, answers: dict[str, int], lang: str | None) -> Outgoing:
    i = [x.key for x in QUESTIONS].index(q.key) + 1
    return Outgoing(text=t("chk_q", lang, i=i, n=len(QUESTIONS), text=q.text),
                    buttons=[Button(id=f"rnw:q:{q.key}:{j}", title=o[:20]) for j, o in enumerate(q.options)])


def _date_item(title: str, exp: date | None, today: date, warn_days: int, key: str, lang: str | None) -> Item:
    if not exp:
        return Item(AMBER, title, "date not set", f"rnw:date:{key}", "Life admin", "Add the date")
    days = (exp - today).days
    if days < 0:
        return Item(RED, title, f"expired {-days} days ago", f"rnw:view:{key}", "Life admin", "What to do now")
    if days <= 30:
        return Item(RED, title, f"expires in {days} days ({fmt_date(exp, lang)})", f"rnw:view:{key}", "Life admin", "Start renewal")
    if days <= warn_days:
        return Item(AMBER, title, f"renewal window open: {days} days left", f"rnw:view:{key}", "Life admin", "Start renewal")
    return Item(GREEN, title, f"valid until {fmt_date(exp, lang)}")


def items(ex: dict[str, date | None], answers: dict[str, int], today: date, lang: str | None, *,
          owed: int = 0, streak: int = 0, open_cases: int = 0, warnings: list[str] | None = None) -> list[Item]:
    from app.modules.renewals.node import PROCESSES

    out: list[Item] = []
    out.append(_date_item("Residence visa", ex.get("residence"), today, PROCESSES["residence"].start_days, "residence", lang))

    # Passport: who holds it beats any date.
    held = answers.get("passport", 0)
    v, p = ex.get("residence"), ex.get("passport")
    if held:
        out.append(Item(RED, "Passport", "kept by someone else. Employers and agents may not keep your passport",
                        "pro:help", "Protection", "Get help"))
    elif v and p and (p - v).days < 183:
        out.append(Item(AMBER, "Passport", "less than 6 months left at visa renewal: renew it first",
                        "rnw:view:passport", "Life admin", "Renew passport"))
    else:
        out.append(_date_item("Passport", p, today, PROCESSES["passport"].start_days, "passport", lang))

    e = ex.get("eid")
    if e and v and abs((v - e).days) > 31:
        out.append(Item(AMBER, "Emirates ID", "date doesn't match your visa", "rnw:view:eid", "Life admin", "Check Emirates ID"))
    elif e:
        out.append(_date_item("Emirates ID", e, today, PROCESSES["eid"].start_days, "eid", lang))

    ins = answers.get("insurance")
    if ins == 1:
        out.append(Item(RED, "Health insurance", "taken from your pay. Your employer must pay it (not deductible in Dubai)",
                        "health:insurance", "Wellbeing", "My insurance rights"))
    elif ins == 2:
        out.append(Item(RED, "Health insurance", "no card. It's required for your visa and your employer must arrange it",
                        "health:noins", "Wellbeing", "No insurance card"))
    elif ins == 0:
        out.append(Item(GREEN, "Health insurance", "paid by your employer"))

    ren = answers.get("renewing")
    if ren == 1:
        out.append(Item(AMBER, "Job change", "notice, probation and permit rules decide if you can move without a ban",
                        "career:change", "Career", "Change jobs safely"))
    elif ren == 2:
        out.append(Item(AMBER, "Who renews", "ask your employer when they'll start; they file it",
                        "rnw:view:residence", "Life admin", "What to ask"))
    elif ren == 0:
        out.append(Item(GREEN, "Renewal", "your employer is renewing it"))

    pay = answers.get("pay")
    if owed > 0 or streak >= 2:
        why = f"AED {owed:,} unpaid" + (f", short {streak} months in a row" if streak >= 2 else "")
        out.append(Item(RED, "Salary", why, "case:new:wages" if streak >= 2 else "pay:gaps", "Employment",
                        "Open a wages case" if streak >= 2 else "What I'm owed"))
    elif pay in (1, 2):
        out.append(Item(RED, "Salary", "not paid in full. Wages are due on the 1st; MOHRE can act from day 2",
                        "pay:watch", "Employment", "Track my pay"))
    elif pay == 0:
        out.append(Item(GREEN, "Salary", "paid in full last month"))

    if answers.get("home") == 2:
        out.append(Item(AMBER, "Housing", "shared housing is legal only from owners or licensed operators (Dubai, 2026)",
                        "home:rights", "Housing", "My housing rights"))
    elif "home" in answers:
        out.append(Item(GREEN, "Housing", "no issue found"))

    f = ex.get("family")
    if f and 0 <= (f - today).days <= 90:
        out.append(Item(AMBER, "Family visa fees", f"due {fmt_date(f, lang)}: plan the costs now", "grow:goal", "Financial", "Plan the fees"))
    if open_cases:
        out.append(Item(AMBER, "Open cases", f"{open_cases} open; keep notes up to date", "case:list", "Employment", "My cases"))

    order = {RED: 0, AMBER: 1, GREEN: 2}
    return sorted(out, key=lambda x: order[x.level])


def result_messages(found: list[Item], lang: str | None) -> list[Outgoing]:
    red = sum(i.level == RED for i in found)
    amber = sum(i.level == AMBER for i in found)
    green = sum(i.level == GREEN for i in found)
    lines = [t("chk_line", lang, icon=i.level, title=i.title, why=i.why,
               agent=f"  → _{i.agent}_" if i.agent and i.level != GREEN else "") for i in found]
    text = t("chk_head", lang, red=red, amber=amber, green=green) + "\n".join(lines)
    fixes = [i for i in found if i.action and i.level != GREEN]
    if not fixes:
        return [Outgoing(text=text + t("chk_all_green", lang), buttons=[Button(id="rnw:menu", title="My renewals"),
                                                                       Button(id="rnw:check:again", title=t("btn_chk_again", lang))])]
    rows = [ListRow(id=i.action, title=f"{i.level} {i.label or i.title}"[:24], description=f"{i.title} · {i.agent}"[:72])
            for i in fixes[:8]]
    rows += [ListRow(id="rnw:menu", title="My renewals"), ListRow(id="rnw:check:again", title=t("btn_chk_again", lang))]
    return [Outgoing(text=text), Outgoing(text=t("chk_next", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows[:10]))]


async def context_numbers(user, session: Any) -> dict[str, int]:  # type: ignore[no-untyped-def]
    from app.modules.pay import amounts as am

    _, owed = am.gaps(user)
    n = 0
    if session is not None:
        from app.modules.cases import store as case_store

        n = await case_store.open_count(session, user.id)
    return {"owed": owed or 0, "streak": am.shortfall_streak(user), "open_cases": n}
