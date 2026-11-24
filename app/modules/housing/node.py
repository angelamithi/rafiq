"""Housing guardian (Life admin agent): check a room or flat before paying,
work out the real monthly cost, check a rent increase, keep a rent reminder
and track a problem with a landlord.

Rules checked on 2026-11-24 (sources in README):
- Dubai: Ejari registration of tenancy contracts is required (needed for
  utilities, residency papers and Rental Disputes Centre cases).
- Dubai: a rent increase needs written notice at least 90 days before the
  contract ends and must be allowed by the DLD Smart Rental Index; without the
  notice no increase applies (Dubai Land Department, 2025).
- Dubai Law No. 4 of 2026 on shared housing (in force August 2026): only owners
  and licensed operators may let shared housing; partitions made without a
  Dubai Municipality permit are illegal; fines AED 500 to 500,000, up to
  AED 1 million for repeat violations.
The agreement text is read once (AI transcribes photos); rules pick the terms.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.parsing import parse_date
from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import S, fmt_date, t
from app.modules.reminders import store as reminders
from app.security.tool_policy import authorize

NODE = "housing"
CHECKED = "2026-11-24"

STRINGS: dict[str, dict[str, str]] = {
    "home_menu": {"en": "🏠 *Housing*\nCheck a place *before* you pay, know the real cost, and know your rights as a tenant."},
    "home_m_check": {"en": "Check a rental offer"},
    "home_m_check_d": {"en": "Send the ad or agreement: I flag risks"},
    "home_m_cost": {"en": "Real monthly cost"},
    "home_m_cost_d": {"en": "Rent + bills + transport, all in"},
    "home_m_viewing": {"en": "Viewing checklist"},
    "home_m_viewing_d": {"en": "What to check before you agree"},
    "home_m_increase": {"en": "Rent increase check"},
    "home_m_increase_d": {"en": "Is the increase allowed?"},
    "home_m_remind": {"en": "Rent reminder"},
    "home_m_remind_d": {"en": "A message before rent is due"},
    "home_m_problem": {"en": "Problem with landlord"},
    "home_m_problem_d": {"en": "Repairs, deposit, eviction: track it"},
    "home_m_rights": {"en": "Tenant rights"},
    "home_m_rights_d": {"en": "Ejari, deposits, shared housing rules"},
    "btn_housing": {"en": "Housing"},
    "home_ask_offer": {"en": "📄 Send the room ad or rental agreement: paste the text, or send a photo or PDF."},
    "home_unreadable": {"en": "I couldn't read that. Paste the text, or send a clearer photo."},
    "home_report": {"en": "🏠 *What I found*\n{found}\n\n{flags}\n\n{missing}\n\n{verdict}"},
    "home_found_line": {"en": "• {label}: {value}"},
    "home_flags_head": {"en": "*Warning signs*"},
    "home_no_flags": {"en": "No warning signs found in the text. ✅"},
    "home_missing_head": {"en": "*Not stated (ask before paying)*"},
    "home_verdict_high": {"en": "⛔ *Don't pay yet.* Ask for a written contract registered in Ejari, and see the place in person first."},
    "home_verdict_mid": {"en": "⚠️ *Ask questions first.* Get the missing points in writing before you pay."},
    "home_verdict_ok": {"en": "👍 Looks normal so far. Still see it in person and get a receipt for every payment."},
    "home_f_pay_first": {"en": "Asks for money before you've seen the place"},
    "home_f_no_ejari": {"en": "Says no Ejari / no contract"},
    "home_f_cash": {"en": "Cash only, or no receipt"},
    "home_f_partition": {"en": "Partition or bed space: shared housing must be licensed under Dubai Law No. 4 of 2026"},
    "home_f_crowded": {"en": "{n} people in one room is likely overcrowded"},
    "home_f_big_deposit": {"en": "Deposit is more than 2 months' rent"},
    "home_f_fees": {"en": "Extra fees (commission, key money, 'admin'): ask what each is for and get a receipt"},
    "home_l_rent": {"en": "Rent"},
    "home_l_deposit": {"en": "Deposit"},
    "home_l_people": {"en": "People per room"},
    "home_l_bills": {"en": "Bills (DEWA/internet)"},
    "home_l_length": {"en": "Contract length"},
    "home_l_notice": {"en": "Notice period"},
    "home_bills_in": {"en": "included"},
    "home_bills_out": {"en": "not included"},
    "home_m_rentm": {"en": "rent amount"},
    "home_m_deposit": {"en": "deposit and how it's returned"},
    "home_m_bills": {"en": "whether DEWA and internet are included"},
    "home_m_length": {"en": "how long the contract runs"},
    "home_m_notice": {"en": "notice needed to leave"},
    "home_m_ejari": {"en": "whether it will be registered in Ejari"},
    "home_ask_cost": {"en": "Type your monthly costs in AED: *rent, bills, transport*, e.g. *1200 150 200*. (Add a 4th number for anything else.)"},
    "home_bad_cost": {"en": "Please type 3 or 4 numbers, e.g. *1200 150 200*."},
    "home_cost": {"en": "🏠 Real monthly cost: *AED {total}*\n• Rent AED {rent}\n• Bills AED {bills}\n• Transport AED {transport}{other}{share}"},
    "home_cost_share": {"en": "\n\nThat's *{pct}%* of your income{warn}"},
    "home_cost_warn": {"en": ". Over a third of income on housing leaves little for family and savings; a legal place nearer work may cost less overall."},
    "home_viewing": {"en": (
        "🔎 *Viewing checklist*\n"
        "• See the actual room, in daylight. Never pay for a place you haven't seen.\n"
        "• Count beds and people. No wooden or gypsum partitions dividing rooms.\n"
        "• Fire exit, smoke detector, working windows, no exposed wires.\n"
        "• Water pressure, AC, toilet, kitchen, signs of damp or insects.\n"
        "• Ask who the owner or licensed operator is, and see the Ejari or shared housing permit.\n"
        "• Ask what's included: DEWA, internet, cleaning, cooking gas.\n"
        "• Time the trip to work at rush hour.\n"
        "• Get every payment receipted, and never hand over your passport."
    )},
    "home_ask_renewal": {"en": "When does your contract end (renewal date)? e.g. *31/03/2027*"},
    "home_ask_notice": {"en": "When did you get the written notice of the increase? e.g. *15/01/2027* (or type *none*)"},
    "home_bad_date": {"en": "Please type a date like *31/03/2027*."},
    "home_increase_late": {"en": (
        "📅 Notice came *{days} days* before your contract ends. In Dubai a landlord must give written notice at least "
        "*90 days* before expiry, otherwise *no increase applies* and you can renew at the same rent "
        "(Dubai Land Department, checked {checked}). If they insist, you can go to the Rental Disputes Centre."
    )},
    "home_increase_none": {"en": (
        "📅 No written notice means no increase can apply at this renewal in Dubai "
        "(Dubai Land Department, checked {checked}). Keep paying the current rent and keep your receipts."
    )},
    "home_increase_ok": {"en": (
        "📅 Notice came *{days} days* before expiry, so the 90-day rule is met. The increase is only allowed if the "
        "DLD *Smart Rental Index* says your unit is eligible: check it on the Dubai Land Department website or app "
        "(dubailand.gov.ae). If the index says no increase, the landlord can't raise it."
    )},
    "home_ask_day": {"en": "Which day of the month is rent due? (1-28)"},
    "home_bad_day": {"en": "Please type a day from 1 to 28."},
    "home_remind_set": {"en": "✅ I'll remind you 3 days before rent is due each month (next: {date})."},
    "home_rights": {"en": (
        "📜 *Tenant basics in Dubai* (checked {checked})\n"
        "• Get a written tenancy contract and make sure it's registered in *Ejari*. You need it for DEWA, residency "
        "papers and to complain to the Rental Disputes Centre.\n"
        "• Rent can only go up at renewal, with *90 days' written notice*, and only if the DLD Smart Rental Index allows it.\n"
        "• Shared housing (bed spaces, shared flats) may only be let by the owner or a *licensed operator*. Partitions "
        "without a Dubai Municipality permit are illegal, and the law allows fines on violators.\n"
        "• Keep receipts for rent and deposit. Deposits are usually returned at the end, minus documented damage.\n"
        "• Other emirates have their own rules; ask me and I'll point you to the right office."
    )},
}
S.update(STRINGS)

_AED = r"(?:aed|dhs?|dirhams?)"
_AMT = r"(\d{1,3}(?:,\d{3})+|\d{3,7})"


def _first(rx: str, text: str) -> int | None:
    m = re.search(rx, text, re.I)
    if not m:
        return None
    for g in m.groups():
        if g and re.fullmatch(r"[\d,]+", g):
            return int(g.replace(",", ""))
    return None


def analyse(text: str) -> dict[str, Any]:
    low = (text or "").lower()
    rent = _first(rf"(?:rent|price)[^\n\d]{{0,25}}{_AED}?\s*{_AMT}", text) or _first(rf"{_AED}\s*{_AMT}\s*(?:/|per|a)\s*(?:month|mo)", text)
    yearly = bool(re.search(r"(per|a|/)\s*(year|annum|yr)|yearly|annual", low))
    deposit = _first(rf"deposit[^\n\d]{{0,25}}{_AED}?\s*{_AMT}", text)
    people = _first(r"(\d{1,2})\s*(?:people|persons|pax|beds?|sharing)\s*(?:per|in\s+(?:one|a|the))?\s*room", text) \
        or _first(r"(\d{1,2})\s*(?:per)\s*room", text)
    bills = False if re.search(r"(dewa|bills?|utilities)[^\n]{0,20}(not\s+included|extra|excluded|separate)", low) \
        else (True if re.search(r"(dewa|bills?|utilities|internet|wifi)[^\n]{0,20}(included|inclusive|free)|all\s+inclusive", low)
              else None)
    months = _first(r"(\d{1,2})\s*(?:months?)\s*(?:contract|lease|minimum)", text)
    years = _first(r"(\d)\s*(?:years?)\s*(?:contract|lease)", text)
    notice = _first(r"(\d{1,3})\s*(?:days?|months?)\s*notice|notice\s*(?:period)?\s*[:\-]?\s*(\d{1,3})", text)
    flags = []
    if re.search(r"(pay|send|transfer|deposit)[^\n]{0,40}(before|without)\s+(viewing|seeing|visit)|book\s+now\s+pay|advance\s+to\s+reserve"
                 r"|no\s+viewing|can'?t\s+(view|visit)", low):
        flags.append(("pay_first", True))
    if re.search(r"no\s+(ejari|contract|agreement)|without\s+(ejari|contract)|ejari\s+not", low):
        flags.append(("no_ejari", True))
    if re.search(r"cash\s+only|no\s+receipt", low):
        flags.append(("cash", True))
    if re.search(r"partition|bed\s*space|bedspace|executive\s+room|sharing\s+room", low):
        flags.append(("partition", True))
    if people and people >= 5:
        flags.append(("crowded", True))
    if rent and deposit and not yearly and deposit > 2 * rent:
        flags.append(("big_deposit", False))
    if re.search(r"commission|key\s*money|admin\s*fee|agent\s*fee", low):
        flags.append(("fees", False))
    return {"rent": rent, "yearly": yearly, "deposit": deposit, "people": people, "bills": bills,
            "length": f"{years} year(s)" if years else (f"{months} months" if months else None),
            "notice": notice, "ejari": "ejari" in low, "flags": flags}


def report(a: dict[str, Any], lang: str | None) -> str:
    found = []
    if a["rent"]:
        found.append(t("home_found_line", lang, label=t("home_l_rent", lang), value=f"AED {a['rent']:,}" + (" a year" if a["yearly"] else "")))
    if a["deposit"]:
        found.append(t("home_found_line", lang, label=t("home_l_deposit", lang), value=f"AED {a['deposit']:,}"))
    if a["people"]:
        found.append(t("home_found_line", lang, label=t("home_l_people", lang), value=str(a["people"])))
    if a["bills"] is not None:
        found.append(t("home_found_line", lang, label=t("home_l_bills", lang), value=t("home_bills_in" if a["bills"] else "home_bills_out", lang)))
    if a["length"]:
        found.append(t("home_found_line", lang, label=t("home_l_length", lang), value=a["length"]))
    flags = [t(f"home_f_{k}", lang, n=a.get("people") or "") for k, _ in a["flags"]]
    missing = [t(f"home_m_{k}", lang) for k, ok in (("rentm", a["rent"]), ("deposit", a["deposit"]), ("bills", a["bills"] is not None),
                                                    ("length", a["length"]), ("notice", a["notice"]), ("ejari", a["ejari"])) if not ok]
    severe = any(hi for _, hi in a["flags"])
    verdict = "home_verdict_high" if severe else ("home_verdict_mid" if a["flags"] or len(missing) >= 3 else "home_verdict_ok")
    return t("home_report", lang,
             found="\n".join(found) or "-",
             flags=(t("home_flags_head", lang) + "\n" + "\n".join(f"• {f}" for f in flags)) if flags else t("home_no_flags", lang),
             missing=(t("home_missing_head", lang) + "\n" + "\n".join(f"• {m}" for m in missing)) if missing else "",
             verdict=t(verdict, lang)).replace("\n\n\n\n", "\n\n")


def home_menu(lang: str | None) -> Outgoing:
    keys = ("check", "cost", "viewing", "increase", "remind", "problem", "rights")
    rows = [ListRow(id=f"home:{k}", title=t(f"home_m_{k}", lang), description=t(f"home_m_{k}_d", lang)) for k in keys]
    return Outgoing(text=t("home_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _ev(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _back(lang: str | None) -> list[Button]:
    return [Button(id="home:menu", title=t("btn_housing", lang)), Button(id="menu:main", title=t("btn_menu", lang))]


async def housing(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    from app.modules.growth.node import _nums

    user, msg = state["user"], state["incoming"]
    lang = user.language
    bid = msg.button_id or ""
    text = (state.get("text") or "").strip()
    today: date = ctx(config).get("today") or date.today()
    authorize(NODE, "get_own_profile")
    action = bid.removeprefix("home:") if bid.startswith("home:") else ""
    kit = repo.toolkit(user)
    draft = kit.get("home_draft") if isinstance(kit.get("home_draft"), dict) else {}

    def set_step(step: str | None, d: dict | None = None) -> None:
        repo.update_toolkit(user, home_draft=d or None)
        user.step = step or "ready"

    if not bid and user.step.startswith("home:"):
        step = user.step
        if step == "home:offer":
            doc = text
            if msg.kind == "media" and msg.media_type in ("image", "document"):
                authorize(NODE, "check_document")
                from app.media.flow import read_media_from_message

                res, _ = await read_media_from_message(state, config)
                doc = res.text or ""
            if len(doc) < 25:
                return _out(state, Outgoing(text=t("home_unreadable", lang), buttons=_back(lang)))
            set_step(None)
            a = analyse(doc)
            level = "high" if any(hi for _, hi in a["flags"]) else ("medium" if a["flags"] else "low")
            return _out(state, Outgoing(text=report(a, lang), buttons=[Button(id="home:viewing", title=t("home_m_viewing", lang)),
                                                                       *_back(lang)]),
                        events=_ev(state, ("housing_checked", level)))
        if step == "home:cost":
            nums = _nums(text)
            if not (3 <= len(nums) <= 4) or any(n > 100_000 for n in nums):
                return _out(state, Outgoing(text=t("home_bad_cost", lang)))
            rent, bills, transport = (int(n) for n in nums[:3])
            other = int(nums[3]) if len(nums) == 4 else 0
            total = rent + bills + transport + other
            income = (kit.get("budget") or {}).get("income") or kit.get("salary")
            share = ""
            if income:
                pct = round(100 * total / income)
                share = t("home_cost_share", lang, pct=pct, warn=t("home_cost_warn", lang) if pct > 33 else ".")
            set_step(None)
            return _out(state, Outgoing(text=t("home_cost", lang, total=f"{total:,}", rent=f"{rent:,}", bills=f"{bills:,}",
                                               transport=f"{transport:,}", other=f"\n• Other AED {other:,}" if other else "", share=share),
                                        buttons=_back(lang)), events=_ev(state, ("housing_cost", "")))
        if step == "home:renewal":
            d = parse_date(text)
            if not d:
                return _out(state, Outgoing(text=t("home_bad_date", lang)))
            set_step("home:notice", {"renewal": d.isoformat()})
            return _out(state, Outgoing(text=t("home_ask_notice", lang)))
        if step == "home:notice":
            renewal = date.fromisoformat(draft.get("renewal", today.isoformat()))
            set_step(None)
            if text.lower() in ("none", "no", "no notice", "never"):
                return _out(state, Outgoing(text=t("home_increase_none", lang, checked=CHECKED), buttons=_back(lang)),
                            events=_ev(state, ("rent_increase_checked", "no_notice")))
            d = parse_date(text)
            if not d:
                user.step = "home:notice"
                repo.update_toolkit(user, home_draft=draft)
                return _out(state, Outgoing(text=t("home_bad_date", lang)))
            days = (renewal - d).days
            key = "home_increase_late" if days < 90 else "home_increase_ok"
            return _out(state, Outgoing(text=t(key, lang, days=days, checked=CHECKED), buttons=_back(lang)),
                        events=_ev(state, ("rent_increase_checked", "late" if days < 90 else "on_time")))
        if step == "home:day":
            nums = _nums(text)
            if len(nums) != 1 or not (1 <= nums[0] <= 28):
                return _out(state, Outgoing(text=t("home_bad_day", lang)))
            day = int(nums[0])
            due = today.replace(day=day)
            if due <= today:
                due = reminders.add_month(due)
            remind = due.replace(day=max(1, day - 3))
            session = ctx(config).get("db")
            authorize(NODE, "update_own_reminders")
            await reminders.replace_kind(session, user.id, "rent")
            await reminders.add(session, user.id, "rent", remind, f"Rent is due on the {day}th. Pay with a receipt or bank transfer.",
                                monthly=True)
            set_step(None)
            return _out(state, Outgoing(text=t("home_remind_set", lang, date=fmt_date(remind, lang)), buttons=_back(lang)),
                        events=_ev(state, ("rent_reminder_on", "")))
    user.step = "ready"

    if action == "check":
        set_step("home:offer")
        return _out(state, Outgoing(text=t("home_ask_offer", lang)))
    if action == "cost":
        set_step("home:cost")
        return _out(state, Outgoing(text=t("home_ask_cost", lang)))
    if action == "viewing":
        return _out(state, Outgoing(text=t("home_viewing", lang), buttons=_back(lang)))
    if action == "increase":
        set_step("home:renewal")
        return _out(state, Outgoing(text=t("home_ask_renewal", lang)))
    if action == "remind":
        set_step("home:day")
        return _out(state, Outgoing(text=t("home_ask_day", lang)))
    if action == "problem":
        from app.modules.cases.node import open_case

        case, msgs = await open_case(state, config, "housing", "Housing problem recorded", actor=NODE)
        return _out(state, *msgs, events=_ev(state, ("case_opened", "housing")) if case else state.get("events", []))
    if action == "rights":
        return _out(state, Outgoing(text=t("home_rights", lang, checked=CHECKED), buttons=_back(lang)))
    cmd = state.get("command") or ""
    if cmd == "rent_increase":
        set_step("home:renewal")
        return _out(state, Outgoing(text=t("home_ask_renewal", lang)))
    if cmd == "check_room":
        set_step("home:offer")
        return _out(state, Outgoing(text=t("home_ask_offer", lang)))
    return _out(state, home_menu(lang))
