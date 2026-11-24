"""Renewal assistant (Life admin agent): the lead task.

For every expat in the UAE, residency paperwork runs on deadlines: residence
visa, Emirates ID, passport, health insurance, tenancy. Missing one means daily
fines and blocked services. Rafiq keeps one calendar of all of them, checks the
documents against each other (e.g. a passport that won't have 6 months left at
visa renewal), lists exactly what each renewal needs and who files it, ticks
off what is ready, schedules the reminders and makes a printable renewal pack.
It never files anything: the employer, an official centre or the person does.

Rules checked on 2026-11-24:
- Emirates ID: renewal after 30 days from expiry costs AED 20 a day, max AED 1,000;
  no one may withhold another person's Emirates ID (u.ae).
- Overstay after a residence permit expires or is cancelled and any grace period
  ends: AED 50 a day for all visa types (u.ae); grace periods depend on category.
- Residence renewal: passport valid at least 6 months; medical fitness test for
  18+; the Emirates ID renews with the visa; valid health insurance; for
  employment visas the employer renews the work permit and files the renewal
  (GDRFA in Dubai, ICP in other emirates).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.parsing import parse_date
from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import S, fmt_date, t
from app.media.pdf import Section, build_pdf
from app.modules.reminders import store as reminders
from app.modules.renewals import check as chk
from app.security.tool_policy import authorize

NODE = "renewals"
CHECKED = "2026-11-24"
STATUSES = ("Not started", "Collecting documents", "Submitted", "Done", "Action needed")

# Official places to apply and check status. Only these, never a link from a message.
# (All hosts are on the output guard's allowlist.)
_UAE_RULES = ("UAE rules and fees (u.ae)", "https://u.ae/en/information-and-services/visa-and-emirates-id")
OFFICIAL: dict[str, tuple[tuple[str, str], ...]] = {
    "residence": (("GDRFA Dubai (apply, status, Amer centres)", "https://gdrfad.gov.ae"),
                  ("ICP (other emirates, Emirates ID)", "https://icp.gov.ae"), _UAE_RULES),
    "family": (("GDRFA Dubai (apply, status, Amer centres)", "https://gdrfad.gov.ae"),
               ("ICP (other emirates)", "https://icp.gov.ae"), _UAE_RULES),
    "eid": (("ICP smart services (apply, status)", "https://icp.gov.ae"), _UAE_RULES),
    "passport": (("Embassies in the UAE (MOFA list)", "https://mofa.gov.ae"),),
    "ejari": (("Dubai Land Department (Ejari)", "https://dubailand.gov.ae"),),
}


@dataclass(frozen=True)
class Process:
    key: str
    title: str
    who: str
    where: str
    start_days: int                  # start this many days before expiry
    needs: tuple[str, ...]
    steps: tuple[str, ...]
    late: str


PROCESSES: dict[str, Process] = {p.key: p for p in (
    Process("residence", "Residence visa (employment)", "Your employer (or its PRO) files it. You do the medical test and keep your documents ready.",
            "GDRFA in Dubai (through Amer centres); ICP in the other emirates", 60,
            ("Passport valid at least 6 months", "Current residence visa (copy or app)", "Emirates ID", "Recent photo (white background)",
             "Valid health insurance", "Medical fitness test result", "Renewed work permit / labour contract (from employer)"),
            ("Check your passport has 6+ months left at renewal. If not, renew it at your embassy first.",
             "Ask your employer when they will start; they renew your work permit and contract first.",
             "Book the medical fitness test close to the submission date (the result has limited validity).",
             "Your employer submits the renewal; the Emirates ID renews with it.",
             "Check status in the ICP or GDRFA app; collect or receive your new Emirates ID."),
            "After expiry and any grace period, overstay fines are AED 50 a day."),
    Process("family", "Family visa (you are the sponsor)", "You file it, yourself or through an official typing centre.",
            "GDRFA in Dubai (Amer); ICP in the other emirates", 60,
            ("Your passport and residence visa", "Family members' passports (6+ months valid)", "Their Emirates IDs",
             "Health insurance for each family member", "Medical test for family members 18+", "Tenancy contract (Ejari in Dubai)",
             "Salary certificate or labour contract", "Marriage / birth certificates (attested)"),
            ("Check every passport has 6+ months left.", "Renew health insurance for each family member.",
             "Book medical tests for adults.", "Apply through Amer or the ICP app; pay the fees.", "Track status and collect Emirates IDs."),
            "After expiry and any grace period, overstay fines are AED 50 a day per person."),
    Process("eid", "Emirates ID", "You (it usually renews together with your residence visa).",
            "ICP app or website, or an official typing centre", 30,
            ("Passport", "Residence visa", "Recent photo", "Fee payment"),
            ("If your visa is being renewed, the Emirates ID renews with it.",
             "Otherwise apply in the ICP app or at an official typing centre.",
             "Go for biometrics if you are asked.", "Use the digital Emirates ID in the ICP app while you wait."),
            "Renewing more than 30 days after expiry costs AED 20 a day, up to AED 1,000. No one may keep your Emirates ID."),
    Process("passport", "Passport (home country)", "You, through your embassy or consulate.",
            "Your embassy or consulate in the UAE (type *embassy*)", 240,
            ("Current passport", "Emirates ID and residence visa copy", "Passport photos to embassy rules", "Fee",
             "Birth certificate or national ID (some countries)"),
            ("Book the embassy appointment or online application early: it can take weeks.",
             "Bring the originals and copies they ask for.",
             "When the new passport arrives, the residence visa may need to be moved to it: ask your employer or GDRFA/ICP."),
            "An expiring passport can block your visa renewal (it needs 6 months' validity)."),
    Process("ejari", "Tenancy (Ejari) renewal, Dubai", "You and your landlord.", "Dubai Land Department (Ejari) and the DLD app", 100,
            ("Signed renewed tenancy contract", "Emirates ID", "Passport and visa copy", "DEWA account details"),
            ("90+ days before the end: watch for a written notice of any change; no notice, no rent increase.",
             "Agree the renewal and sign the new contract.", "Register the renewal in Ejari.", "Keep receipts for rent and deposit."),
            "Without Ejari you may be unable to renew a family visa or bring a case to the Rental Disputes Centre."),
)}

STRINGS: dict[str, dict[str, str]] = {
    "rnw_head": {"en": "🗓️ *My renewals*\nEvery deadline in one place, with what you need and who files it. I remind you before each one."},
    "rnw_line": {"en": "{icon} *{title}*: {when}{status}"},
    "rnw_no_date": {"en": "date not set"},
    "rnw_in": {"en": "expires {date} ({days} days)"},
    "rnw_late": {"en": "*expired {days} days ago*"},
    "rnw_warn_head": {"en": "⚠️ *Check this*"},
    "rnw_warn_passport": {"en": "Your passport expires {pdate}, less than 6 months after your visa expires ({vdate}). Renew the passport first or the visa renewal can be refused."},
    "rnw_warn_eid": {"en": "Your Emirates ID ({edate}) and residence visa ({vdate}) don't match. They are normally renewed together; check with your employer."},
    "rnw_pick": {"en": "Choose a renewal to see the steps, check your documents and set reminders."},
    "rnw_view": {"en": (
        "🗓️ *{title}*\n{when}\n\n*Who files it:* {who}\n*Where:* {where}\n\n*Steps*\n{steps}\n\n"
        "*If late:* {late}\n*Status:* {status}{ref}\n\n*Official sites*\n{links}\n"
        "_Apply and pay only there or in their apps, never through a link in a message._\n\n"
        "_Rules checked {checked}. Fees change: confirm on the official site._"
    )},
    "rnw_ready_head": {"en": "📋 *Documents for {title}*: {n} of {total} ready. Tap to tick what you have."},
    "rnw_ask_date": {"en": "When does it expire? (e.g. *15/03/2027*)"},
    "rnw_bad_date": {"en": "Please type a date like *15/03/2027*."},
    "rnw_saved_date": {"en": "✅ Saved. I'll remind you {plan}."},
    "rnw_plan": {"en": "on {dates}"},
    "rnw_status_saved": {"en": "✅ Status: *{status}*."},
    "rnw_done_ask": {"en": "🎉 Done! What's the *new* expiry date? I'll set your next reminders. (or tap Skip)"},
    "rnw_done_saved": {"en": "✅ New expiry {date} saved. Your reminders are set for the next round."},
    "rnw_pack_caption": {"en": "📄 Your renewal pack (checklist and dates)"},
    "rnw_fine": {"en": "💸 Estimated late fee so far: *AED {amount}*. Act today; you may ask ICP for an exemption if a valid reason applies."},
    "rnw_sms_ask": {"en": (
        "📩 Paste the SMS or email you got from ICP, GDRFA, Amer or Ejari about this application. "
        "I'll read the status and update your tracker.\n_I keep only the status, the application number "
        "and any new expiry date, not the message._")},
    "rnw_sms_status": {"en": "📩 Official update read: *{title}* → *{status}*{ref}."},
    "rnw_sms_submitted": {"en": "It's being processed. I'll keep your reminders running; check again in the official app if nothing changes in a week."},
    "rnw_sms_action": {"en": "⚠️ Something needs fixing (a document, a payment or a correction). Open the official app to see exactly what, then tick the documents here."},
    "rnw_sms_done_date": {"en": "🎉 Approved. New expiry {date} saved; your next reminders are set ({plan})."},
    "rnw_sms_unknown": {"en": "I couldn't find a status in that message. Set it yourself:"},
    "rnw_sms_which": {"en": "📩 That looks like an official update ({status}). Which renewal is it about?"},
    "rnw_sms_scam": {"en": (
        "🚩 *Careful:* this message has a link that isn't an official UAE site, or asks for card details or a code. "
        "ICP and GDRFA don't ask for these by message. Don't tap it; pay only in the official app or at an Amer centre.")},
    "rnw_sms_untouched": {"en": "I haven't changed your tracker. Check the real status in the ICP or GDRFA app."},
    "btn_rnw_sms": {"en": "Paste official SMS"},
    "btn_rnw_docs": {"en": "Check documents"},
    "btn_rnw_date": {"en": "Set expiry date"},
    "btn_rnw_status": {"en": "Update status"},
    "btn_rnw_pack": {"en": "Renewal pack (PDF)"},
    "btn_renewals": {"en": "My renewals"},
    "menu_renewals_d": {"en": "Visa, ID, passport deadlines and a status check"},
}
S.update(STRINGS)


def _data(user) -> dict:  # type: ignore[no-untyped-def]
    d = repo.toolkit(user).get("renewals")
    return d if isinstance(d, dict) else {}


def _save(user, d: dict) -> None:  # type: ignore[no-untyped-def]
    repo.update_toolkit(user, renewals=d or None)


async def expiries(user, session: Any) -> dict[str, date | None]:  # type: ignore[no-untyped-def]
    """Known expiry per process: typed here, from the profile's visa date, or from saved documents."""
    out: dict[str, date | None] = {k: None for k in PROCESSES}
    out["residence"] = repo.get_visa_expiry(user)
    if session is not None:
        from app.modules.tasks import vault as vt

        for _id, kind, exp in await vt.list_docs(session, user.id):
            if exp and kind in ("passport", "eid"):
                out[kind] = max(out[kind], exp) if out[kind] else exp
            if exp and kind == "visa" and not out["residence"]:
                out["residence"] = exp
    for k, v in _data(user).items():
        if isinstance(v, dict) and v.get("expiry") and k in out:
            out[k] = date.fromisoformat(v["expiry"])
    return out


def warnings(ex: dict[str, date | None], lang: str | None) -> list[str]:
    w = []
    v, p, e = ex.get("residence"), ex.get("passport"), ex.get("eid")
    if v and p and p < v + timedelta(days=183):
        w.append(t("rnw_warn_passport", lang, pdate=fmt_date(p, lang), vdate=fmt_date(v, lang)))
    if v and e and abs((v - e).days) > 31:
        w.append(t("rnw_warn_eid", lang, edate=fmt_date(e, lang), vdate=fmt_date(v, lang)))
    return w


def late_fee(key: str, days_late: int) -> int | None:
    if days_late <= 0:
        return None
    if key == "eid":
        return min(20 * max(0, days_late - 30), 1000) or None
    return None


def reminder_dates(key: str, expiry: date, today: date) -> list[date]:
    start = PROCESSES[key].start_days
    picks = sorted({expiry - timedelta(days=d) for d in (start, 30, 7)})
    return [d for d in picks if d >= today]


def _when(exp: date | None, today: date, lang: str | None) -> str:
    if not exp:
        return t("rnw_no_date", lang)
    days = (exp - today).days
    return t("rnw_late", lang, days=-days) if days < 0 else t("rnw_in", lang, date=fmt_date(exp, lang), days=days)


async def overview(user, session: Any, today: date, lang: str | None) -> list[Outgoing]:  # type: ignore[no-untyped-def]
    ex = await expiries(user, session)
    d = _data(user)
    order = sorted(PROCESSES, key=lambda k: (ex[k] is None, ex[k] or date.max))
    lines = []
    for k in order:
        exp = ex[k]
        icon = "⚪" if not exp else ("🔴" if (exp - today).days <= 30 else "🟠" if (exp - today).days <= PROCESSES[k].start_days else "🟢")
        st = (d.get(k) or {}).get("status")
        lines.append(t("rnw_line", lang, icon=icon, title=PROCESSES[k].title, when=_when(exp, today, lang),
                       status=f" · {st}" if st and st != "Not started" else ""))
    text = t("rnw_head", lang) + "\n\n" + "\n".join(lines)
    if w := warnings(ex, lang):
        text += "\n\n" + t("rnw_warn_head", lang) + "\n" + "\n".join(f"• {x}" for x in w)
    rows = [ListRow(id="rnw:check", title=t("btn_chk", lang), description="Visa, passport, pay, insurance, housing")]
    rows += [ListRow(id=f"rnw:view:{k}", title=PROCESSES[k].title[:24], description=_when(ex[k], today, lang).replace("*", "")[:72])
             for k in order]
    return [Outgoing(text=text), Outgoing(text=t("rnw_pick", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))]


def view(key: str, user, exp: date | None, today: date, lang: str | None) -> list[Outgoing]:  # type: ignore[no-untyped-def]
    p = PROCESSES[key]
    entry = _data(user).get(key) or {}
    st = entry.get("status") or STATUSES[0]
    ref = f" (application {entry['ref']})" if entry.get("ref") else ""
    links = "\n".join(f"• {name}: {url}" for name, url in OFFICIAL[key])
    msgs = [Outgoing(text=t("rnw_view", lang, title=p.title, when=_when(exp, today, lang), who=p.who, where=p.where,
                             steps="\n".join(f"{i + 1}. {s}" for i, s in enumerate(p.steps)), late=p.late, status=st,
                             ref=ref, links=links, checked=CHECKED),
                     menu=ListMenu(button=t("btn_choose", lang), rows=[
                         ListRow(id=f"rnw:docs:{key}", title=t("btn_rnw_docs", lang)),
                         ListRow(id=f"rnw:date:{key}", title=t("btn_rnw_date", lang)),
                         ListRow(id=f"rnw:status:{key}", title=t("btn_rnw_status", lang)),
                         ListRow(id=f"rnw:sms:{key}", title=t("btn_rnw_sms", lang)),
                         ListRow(id=f"rnw:pack:{key}", title=t("btn_rnw_pack", lang)),
                         ListRow(id="rnw:check", title=t("btn_chk", lang)),
                         ListRow(id="rnw:menu", title=t("btn_renewals", lang))]))]
    if exp and (fee := late_fee(key, (today - exp).days)):
        msgs.insert(0, Outgoing(text=t("rnw_fine", lang, amount=f"{fee:,}")))
    return msgs


def docs_menu(key: str, user, lang: str | None) -> Outgoing:  # type: ignore[no-untyped-def]
    p = PROCESSES[key]
    have = set((_data(user).get(key) or {}).get("have") or [])
    rows = [ListRow(id=f"rnw:tick:{key}:{i}", title=("✅ " if i in have else "⬜ ") + n[:21], description=n[:72])
            for i, n in enumerate(p.needs)]
    rows.append(ListRow(id=f"rnw:view:{key}", title="⬅ Back"))
    return Outgoing(text=t("rnw_ready_head", lang, title=p.title, n=len(have), total=len(p.needs)),
                    menu=ListMenu(button=t("btn_choose", lang), rows=rows[:10]))


def renewal_pdf(key: str, user, exp: date | None, today: date, lang: str | None) -> bytes:  # type: ignore[no-untyped-def]
    p = PROCESSES[key]
    have = set((_data(user).get(key) or {}).get("have") or [])
    checklist = [["Document", "Ready?"]] + [[n, "Yes" if i in have else "To get"] for i, n in enumerate(p.needs)]
    dates = [["When", "What"]]
    if exp:
        for d in reminder_dates(key, exp, today):
            dates.append([fmt_date(d, lang), "Reminder: check progress"])
        dates.append([fmt_date(exp, lang), "Expiry date"])
    return build_pdf(f"Renewal pack: {p.title}", f"{repo.get_display_name(user) or ''} · prepared {fmt_date(today, lang)}", [
        Section("Who files it and where", [p.who, p.where]),
        Section("Steps", ["\n".join(f"{i + 1}. {s}" for i, s in enumerate(p.steps))]),
        Section("Documents checklist", table=checklist),
        Section("Key dates", table=dates if len(dates) > 1 else [["When", "What"], ["-", "Add the expiry date in Rafiq"]]),
        Section("If late", [p.late]),
        Section("Official sites (apply and pay only here)", [f"{n}: {u}" for n, u in OFFICIAL[key]]),
    ], f"Made with Rafiq. Rules checked {CHECKED}; confirm fees and documents on the official site.")


# ---- official status messages (SMS / email the person forwards)
# Rules only: the text is untrusted, so no AI reads it, nothing in it is followed,
# no link from it is ever repeated, and the message itself is not stored.
_AUTHORITY = re.compile(r"\b(icp|gdrfa|gdrfad|federal authority for identity|general directorate of residency|amer|ejari|"
                        r"dubai land|emirates id|residence (visa|permit)|residency|entry permit|visa application)\b", re.I)
_APPNO = re.compile(r"\b(?:application|app|request|transaction|reference|ref|file)\.?\s*(?:no\.?|number|num|#|id)?\s*[:#]?\s*"
                    r"([A-Z0-9][A-Z0-9/-]{5,23})\b", re.I)
_STATUS_RULES = (
    ("Action needed", re.compile(r"reject|refus|declin|returned|incomplete|missing|additional (document|info)|"
                                 r"(document|documents|information) (is |are )?required|pending (document|payment)|not approved|"
                                 r"correction|cancel", re.I)),
    ("Done", re.compile(r"approv|issued|printed|ready for (collection|delivery)|delivered|dispatched|has been renewed|"
                        r"renewed successfully|completed", re.I)),
    ("Submitted", re.compile(r"received|submitted|under (process|review|processing)|in progress|being processed|"
                             r"registered|payment (received|successful)|successfully paid", re.I)),
)
_KEY_RULES = (
    ("ejari", re.compile(r"ejari|tenancy|dubai land", re.I)),
    ("family", re.compile(r"dependent|family|spouse|child|sponsored", re.I)),
    ("passport", re.compile(r"passport (renewal|application)|embassy|consulate", re.I)),
    ("eid", re.compile(r"emirates id|identity card|id card", re.I)),
    ("residence", re.compile(r"residen|visa|entry permit|work permit", re.I)),
)
_DATE = r"(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2} [A-Za-z]{3,9} \d{4})"
_NEW_EXPIRY = re.compile(r"(?:valid\w*|expir\w*)\s*(?:until|till|to|on|date|is)?\s*(?:date)?\s*[:\-]?\s*" + _DATE, re.I)
_SCAM_WORDS = re.compile(r"\b(otp|cvv|card number|pin|verification code|bit\.ly|tinyurl|click (here|the link)|pay now)\b", re.I)
_LINK = re.compile(r"https?://\S+|\bwww\.\S+|\b[a-z0-9-]+\.(?:com|net|info|xyz|top|online|site|link)\b\S*", re.I)


@dataclass(frozen=True)
class OfficialUpdate:
    status: str | None
    key: str | None
    ref: str | None
    new_expiry: date | None
    suspicious: bool


def looks_official(text: str) -> bool:
    """Is this a forwarded status message (not a question)? Needs an authority
    or application number AND a status word, and some length."""
    if len(text or "") < 40:
        return False
    has_status = any(rx.search(text) for _, rx in _STATUS_RULES)
    return has_status and bool(_AUTHORITY.search(text) or _APPNO.search(text))


def read_update(text: str) -> OfficialUpdate:
    status = next((name for name, rx in _STATUS_RULES if rx.search(text)), None)
    key = next((k for k, rx in _KEY_RULES if rx.search(text)), None)
    ref = None
    for m in _APPNO.finditer(text):
        if any(ch.isdigit() for ch in m.group(1)):
            ref = m.group(1).upper()
            break
    new = None
    if status == "Done" and (m := _NEW_EXPIRY.search(text)):
        new = parse_date(m.group(1))
    from app.security.output_guard import _domain_allowed

    links = [x for x in _LINK.findall(text) if not _domain_allowed(x.rstrip(".,)"))]
    return OfficialUpdate(status, key, ref, new, bool(links or _SCAM_WORDS.search(text)))


async def _apply_update(session: Any, user, key: str, up: OfficialUpdate, today: date, lang: str | None,  # type: ignore[no-untyped-def]
                        ev: list) -> tuple[list[Outgoing], list]:
    authorize(NODE, "update_own_toolkit")
    d = _data(user)
    entry = d.setdefault(key, {})
    msgs: list[Outgoing] = []
    if up.suspicious:           # a possible scam never changes the tracker
        return [Outgoing(text=t("rnw_sms_scam", lang) + "\n\n" + t("rnw_sms_untouched", lang)),
                *view(key, user, (await expiries(user, session))[key], today, lang)], [*ev, ("renewal_sms", f"{key}:suspicious")]
    if up.ref:
        entry["ref"] = up.ref
    if not up.status:
        _save(user, d)
        rows = [ListRow(id=f"rnw:st:{key}:{i}", title=s) for i, s in enumerate(STATUSES)]
        msgs.append(Outgoing(text=t("rnw_sms_unknown", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows)))
        return msgs, [*ev, ("renewal_sms", f"{key}:unread")]
    entry["status"], entry["updated"] = up.status, today.isoformat()
    ref = f" (application {up.ref})" if up.ref else ""
    msgs.append(Outgoing(text=t("rnw_sms_status", lang, title=PROCESSES[key].title, status=up.status, ref=ref)))
    events = [*ev, ("renewal_sms", f"{key}:{up.status}")]
    if up.status == "Done":
        if up.new_expiry and up.new_expiry > today:
            authorize(NODE, "update_own_reminders")
            entry["expiry"] = up.new_expiry.isoformat()
            if key == "residence":
                repo.set_field(user, "visa_expiry", up.new_expiry)
            _save(user, d)
            dates = await _schedule(session, user, key, up.new_expiry, today)
            plan = ", ".join(fmt_date(x, lang) for x in dates) or "as it gets close"
            msgs.append(Outgoing(text=t("rnw_sms_done_date", lang, date=fmt_date(up.new_expiry, lang), plan=plan)))
            return msgs + view(key, user, up.new_expiry, today, lang), [*events, ("renewal_date_set", key)]
        _save(user, d)
        user.step = f"rnw:done:{key}"
        msgs.append(Outgoing(text=t("rnw_done_ask", lang), buttons=[Button(id="rnw:menu", title="Skip")]))
        return msgs, [*events, ("renewal_done", key)]
    _save(user, d)
    if up.status == "Action needed":
        msgs.append(Outgoing(text=t("rnw_sms_action", lang)))
        msgs.append(docs_menu(key, user, lang))
        return msgs, events
    msgs.append(Outgoing(text=t("rnw_sms_submitted", lang)))
    return msgs, events


async def _schedule(session: Any, user, key: str, exp: date, today: date) -> list[date]:  # type: ignore[no-untyped-def]
    await reminders.replace_kind(session, user.id, f"rn_{key}"[:16])
    dates = reminder_dates(key, exp, today)
    for d in dates:
        days = (exp - d).days
        await reminders.add(session, user.id, f"rn_{key}"[:16], d,
                            f"{PROCESSES[key].title} expires in {days} days ({exp.isoformat()}). Type *my renewals* for the steps.")
    return dates


async def status_check(user, session: Any, today: date, lang: str | None, d: dict, ev: list,  # type: ignore[no-untyped-def]
                       *, again: bool = False) -> tuple[list[Outgoing], list]:
    """Ask what Rafiq doesn't know yet (taps only), then the red/amber/green result with handoffs."""
    answers = d.get("_check") if isinstance(d.get("_check"), dict) else {}
    if again:
        answers = {}
        d["_check"] = answers
        _save(user, d)
    todo = chk.pending(answers)
    if todo:
        intro = [Outgoing(text=t("chk_intro", lang, n=len(todo), s="" if len(todo) == 1 else "s"))] if len(todo) == len(chk.QUESTIONS) else []
        return [*intro, chk.question_message(todo[0], answers, lang)], ev
    found = chk.items(await expiries(user, session), answers, today, lang, **await chk.context_numbers(user, session))
    red = sum(i.level == chk.RED for i in found)
    amber = sum(i.level == chk.AMBER for i in found)
    return chk.result_messages(found, lang), [*ev, ("status_check", f"r{red}a{amber}"),
                                              *[("status_handoff", f"{i.title}>{i.agent}") for i in found if i.action and i.level != chk.GREEN]]


async def renewals(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, msg = state["user"], state["incoming"]
    lang = user.language
    session = ctx(config).get("db")
    today: date = ctx(config).get("today") or date.today()
    bid = msg.button_id or ""
    text = (state.get("text") or "").strip()
    authorize(NODE, "get_own_profile")
    authorize(NODE, "get_own_vault")
    action = bid.removeprefix("rnw:") if bid.startswith("rnw:") else ""
    d = _data(user)
    ev = list(state.get("events", []))

    def out(*msgs: Outgoing, events: list | None = None) -> dict[str, Any]:
        return {"replies": [*state.get("replies", []), *msgs], "events": events if events is not None else ev}

    # ---- typed answers (expiry dates)
    if not bid and user.step.startswith("rnw:sms:"):
        key = user.step.split(":")[2]
        user.step = "ready"
        if key in PROCESSES:
            msgs, evs = await _apply_update(session, user, key, read_update(text), today, lang, ev)
            return out(*msgs, events=evs)
    if not bid and user.step.startswith("rnw:"):
        was_done = user.step.startswith("rnw:done")
        key = user.step.split(":")[2] if user.step.count(":") >= 2 else ""
        if key not in PROCESSES:
            user.step = "ready"
            return out(*await overview(user, session, today, lang))
        new = parse_date(text) if text.lower() not in ("skip",) else None
        if text.lower() != "skip" and not new:
            return out(Outgoing(text=t("rnw_bad_date", lang)))
        user.step = "ready"
        authorize(NODE, "update_own_toolkit")
        authorize(NODE, "update_own_reminders")
        if new:
            d.setdefault(key, {})["expiry"] = new.isoformat()
            if key == "residence":
                repo.set_field(user, "visa_expiry", new)       # the visa reminders follow the new date
            _save(user, d)
            dates = await _schedule(session, user, key, new, today)
            plan = t("rnw_plan", lang, dates=", ".join(fmt_date(x, lang) for x in dates)) if dates else "as it gets close"
            msg_key = "rnw_done_saved" if was_done else "rnw_saved_date"
            return out(Outgoing(text=t(msg_key, lang, date=fmt_date(new, lang), plan=plan)),
                       *view(key, user, new, today, lang), events=[*ev, ("renewal_date_set", key)])
        _save(user, d)
        return out(*await overview(user, session, today, lang))

    if action in ("check", "check:again"):
        msgs, evs = await status_check(user, session, today, lang, d, ev, again=action == "check:again")
        return out(*msgs, events=evs)
    m = re.fullmatch(r"q:(\w+):(\d)", action)
    q = next((x for x in chk.QUESTIONS if m and x.key == m.group(1)), None)
    if m and q and int(m.group(2)) < len(q.options):
        authorize(NODE, "update_own_toolkit")
        answers = d.get("_check") if isinstance(d.get("_check"), dict) else {}
        answers[q.key] = int(m.group(2))
        d["_check"] = answers
        _save(user, d)
        msgs, evs = await status_check(user, session, today, lang, d, ev)
        return out(*msgs, events=evs)
    m = re.fullmatch(r"(sms|apply):(\w+)", action)
    if m and m.group(2) in PROCESSES:
        verb, key = m.groups()
        if verb == "sms":
            user.step = f"rnw:sms:{key}"
            return out(Outgoing(text=t("rnw_sms_ask", lang)))
        pending = d.pop("_pending", None)
        if isinstance(pending, dict):
            up = OfficialUpdate(pending.get("status"), key, pending.get("ref"),
                                date.fromisoformat(pending["expiry"]) if pending.get("expiry") else None, False)
            _save(user, d)
            msgs, evs = await _apply_update(session, user, key, up, today, lang, ev)
            return out(*msgs, events=evs)
    m = re.fullmatch(r"(view|docs|date|status|pack):(\w+)", action)
    if m and m.group(2) in PROCESSES:
        verb, key = m.groups()
        exp = (await expiries(user, session))[key]
        if verb == "view":
            return out(*view(key, user, exp, today, lang), events=[*ev, ("renewal_viewed", key)])
        if verb == "docs":
            return out(docs_menu(key, user, lang))
        if verb == "date":
            user.step = f"rnw:date:{key}"
            return out(Outgoing(text=t("rnw_ask_date", lang)))
        if verb == "status":
            rows = [ListRow(id=f"rnw:st:{key}:{i}", title=s) for i, s in enumerate(STATUSES)]
            return out(Outgoing(text=t("btn_rnw_status", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows)))
        if verb == "pack":
            authorize(NODE, "build_document")
            return out(Outgoing(text=t("rnw_pack_caption", lang), file=renewal_pdf(key, user, exp, today, lang),
                                filename=f"renewal-{key}.pdf", file_mime="application/pdf"),
                       events=[*ev, ("renewal_pack_built", key)])
    m = re.fullmatch(r"tick:(\w+):(\d+)", action)
    if m and m.group(1) in PROCESSES and int(m.group(2)) < len(PROCESSES[m.group(1)].needs):
        authorize(NODE, "update_own_toolkit")
        key, i = m.group(1), int(m.group(2))
        entry = d.setdefault(key, {})
        have = set(entry.get("have") or [])
        have ^= {i}
        entry["have"] = sorted(have)
        if have and entry.get("status", STATUSES[0]) == STATUSES[0]:
            entry["status"] = STATUSES[1]
        _save(user, d)
        return out(docs_menu(key, user, lang), events=[*ev, ("renewal_doc_ticked", key)])
    m = re.fullmatch(r"st:(\w+):(\d)", action)
    if m and m.group(1) in PROCESSES and int(m.group(2)) < len(STATUSES):
        authorize(NODE, "update_own_toolkit")
        key, status = m.group(1), STATUSES[int(m.group(2))]
        d.setdefault(key, {})["status"] = status
        _save(user, d)
        if status == "Done":
            user.step = f"rnw:done:{key}"
            return out(Outgoing(text=t("rnw_done_ask", lang), buttons=[Button(id="rnw:menu", title="Skip")]),
                       events=[*ev, ("renewal_done", key)])
        return out(Outgoing(text=t("rnw_status_saved", lang, status=status)), *view(key, user, (await expiries(user, session))[key], today, lang),
                   events=[*ev, ("renewal_status", f"{key}:{status}")])
    user.step = "ready"
    cmd = state.get("command") or ""
    if cmd == "status_check":
        msgs, evs = await status_check(user, session, today, lang, d, ev)
        return out(*msgs, events=evs)
    if cmd == "rnw_sms":
        up = read_update(text)
        if up.key:
            msgs, evs = await _apply_update(session, user, up.key, up, today, lang, ev)
            return out(*msgs, events=evs)
        authorize(NODE, "update_own_toolkit")
        d["_pending"] = {"status": up.status, "ref": up.ref, "expiry": up.new_expiry.isoformat() if up.new_expiry else None}
        _save(user, d)
        if up.suspicious:
            return out(Outgoing(text=t("rnw_sms_scam", lang) + "\n\n" + t("rnw_sms_untouched", lang)),
                       events=[*ev, ("renewal_sms", "suspicious")])
        msgs: list[Outgoing] = []
        rows = [ListRow(id=f"rnw:apply:{k}", title=PROCESSES[k].title[:24]) for k in PROCESSES]
        return out(*msgs, Outgoing(text=t("rnw_sms_which", lang, status=up.status or "status unclear"),
                                   menu=ListMenu(button=t("btn_choose", lang), rows=rows)), events=[*ev, ("renewal_sms", "ask_which")])
    direct = {"renew_eid": "eid", "renew_passport": "passport", "renew_visa": "residence"}.get(cmd)
    if direct:
        exp = (await expiries(user, session))[direct]
        return out(*view(direct, user, exp, today, lang), events=[*ev, ("renewal_viewed", direct)])
    return out(*await overview(user, session, today, lang), events=[*ev, ("renewals_overview", "")])
