"""Career agent: from the job you have to the job you want.

Skills profile, gap to a target role, a 90-day plan, a CV (PDF), a tracker
for applications and interviews, interview practice, and the rules for
changing jobs safely. It never applies for a job or contacts an employer.

Job-change rules checked 2026-11-24 (MOHRE guidance, May 2026): a worker can
move to a new employer when the contract ends or both sides agree to end it;
leaving during probation without the required notice, or a proven
work-abandonment complaint, can mean no new work permit for one year.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.parsing import parse_date
from app.agent.state import AgentState, ctx
from app.channels.base import Button, ListMenu, ListRow, Outgoing
from app.db import repo
from app.i18n import S, fmt_date, t
from app.media.pdf import Section, build_pdf
from app.modules.reminders import store as reminders
from app.security.tool_policy import authorize

NODE = "career"
MAX_APPS = 15


@dataclass(frozen=True)
class Path:
    key: str
    now: str
    next: str
    skills: tuple[str, ...]
    plan: tuple[str, str, str]           # weeks 1-4, 5-8, 9-12
    questions: tuple[str, ...]


_HOSP_Q = ("Tell me about yourself and your work so far.", "How do you handle an unhappy guest?",
           "How would you organise a team when two people are absent?", "Tell me about a time you found a problem before a guest did.",
           "Why do you want more responsibility?")
PATHS: dict[str, Path] = {p.key: p for p in (
    Path("housekeeping", "Housekeeper / room attendant", "Housekeeping supervisor",
         ("room inspection standards", "team scheduling", "guest communication in English", "basic reporting",
          "chemical and safety rules", "training new staff"),
         ("Ask your supervisor to let you check rooms with them; learn the inspection checklist.",
          "Offer to train one new colleague; practise short daily reports in English.",
          "Ask HR about internal supervisor openings or training; update your CV with these examples."), _HOSP_Q),
    Path("waiter", "Waiter / waitress", "Captain or F&B supervisor",
         ("menu and allergen knowledge", "upselling", "handling complaints", "POS and billing", "team coordination",
          "food safety basics"),
         ("Learn the full menu and allergens; ask to shadow the captain.", "Take a food safety course if your employer offers one.",
          "Lead a section for a shift; collect guest compliments as examples for your CV."), _HOSP_Q),
    Path("cook", "Commis / cook", "Chef de partie",
         ("one full station", "food safety and HACCP", "stock and ordering", "costing basics", "leading a small team"),
         ("Master one station end to end; keep notes of recipes and timings.", "Ask about food safety training at work.",
          "Help with ordering and stock counts; ask the head chef for feedback on a step up."),
         ("Walk me through your station during a busy service.", "How do you keep food safe?", "How do you reduce waste?",
          "Tell me about a mistake in the kitchen and what you did.", "Why chef de partie now?")),
    Path("cleaning", "Cleaner", "Cleaning team leader",
         ("quality checklists", "safe chemical use", "rota planning", "client communication", "reporting issues"),
         ("Learn the site's quality checklist; note what clients complain about.", "Volunteer to plan the weekly rota with your supervisor.",
          "Collect examples of problems you solved; ask about team leader roles."),
         ("How do you check work is done well?", "How do you keep chemicals safe?", "A client is unhappy: what do you do?",
          "How would you share work fairly in a team?", "Why do you want to lead?")),
    Path("security", "Security guard", "Security supervisor",
         ("incident reporting", "CCTV and access control", "emergency procedures", "team briefing", "English report writing"),
         ("Ask how security licensing and training work for supervisors in your emirate (in Dubai, SIRA regulates security staff).",
          "Practise writing clear incident reports in English.", "Ask to lead a shift briefing; ask HR about supervisor roles."),
         ("Describe how you handled an incident.", "What do you do in a fire alarm?", "How do you write a good incident report?",
          "How would you brief a team at the start of a shift?", "Why supervisor?")),
    Path("driver", "Driver / delivery rider", "Light or heavy vehicle driver, then logistics coordinator",
         ("UAE driving licence for the vehicle class", "route planning apps", "vehicle checks", "customer service", "basic logistics records"),
         ("Find out the cost and steps for the licence class you need at the RTA (Dubai) or your emirate's police.",
          "Keep a clean record: no fines, on-time deliveries; ask for a reference.", "Learn the delivery or logistics software your company uses."),
         ("How do you plan a day of deliveries?", "What checks do you do before driving?", "A customer isn't home: what do you do?",
          "How do you stay safe in heat and traffic?", "Why do you want this job?")),
    Path("care", "Domestic worker / nanny", "Childcare assistant or caregiver",
         ("child development basics", "first aid", "safe food preparation", "routines and reporting to parents", "English communication"),
         ("Look for a recognised first aid course; ask your employer if they'll support it.",
          "Keep a simple record of routines you manage (meals, school runs, activities).",
          "Ask your employer for a written reference; prepare your CV with these examples."),
         ("How do you keep children safe at home?", "What would you do if a child is choking?", "How do you plan a child's day?",
          "How do you tell parents about a problem?", "Why childcare?")),
    Path("construction", "Construction worker", "Foreman / site supervisor",
         ("site safety rules", "reading simple drawings", "leading a crew", "materials and tools tracking", "daily reporting"),
         ("Learn your site's safety rules well; ask about safety training.", "Ask the foreman to show you the drawings and daily plan.",
          "Lead a small task with a crew; ask about steps to foreman."),
         ("How do you keep a crew safe?", "How do you read this drawing?", "Materials are late: what do you do?",
          "Tell me about a problem you solved on site.", "Why foreman?")),
    Path("retail", "Sales / retail assistant", "Store supervisor",
         ("sales targets", "stock and visual merchandising", "cash and POS", "handling returns and complaints", "shift planning"),
         ("Learn your store's numbers: daily target, best sellers, stock levels.", "Offer to help with stock counts and displays.",
          "Ask to cover the supervisor on a quiet shift; ask about promotion."),
         ("How do you meet a sales target?", "A customer wants a refund without a receipt: what do you do?",
          "How do you keep the shop looking good?", "Tell me about your best sale.", "Why supervisor?")),
)}

STRINGS: dict[str, dict[str, str]] = {
    "career_menu": {"en": "🚀 *Career*\nFrom the job you have to the job you want: skills, a 90-day plan, your CV and your applications. You apply yourself; I never contact employers."},
    "career_m_path": {"en": "Plan my next step"},
    "career_m_path_d": {"en": "Skills you need and a 90-day plan"},
    "career_m_cv": {"en": "Make my CV"},
    "career_m_cv_d": {"en": "A one-page PDF from your details"},
    "career_m_apps": {"en": "My applications"},
    "career_m_apps_d": {"en": "Track applications and interview dates"},
    "career_m_interview": {"en": "Interview practice"},
    "career_m_interview_d": {"en": "Questions for your target job"},
    "career_m_find": {"en": "Find jobs safely"},
    "career_m_find_d": {"en": "Where to look and what to avoid"},
    "career_m_change": {"en": "Changing jobs"},
    "career_m_change_d": {"en": "Notice, permits, avoiding a ban"},
    "btn_career": {"en": "Career"},
    "career_pick_now": {"en": "Which is closest to your job now?"},
    "career_ask_years": {"en": "How many years have you done this work? (just a number)"},
    "career_ask_skills": {"en": "Which of these can you already do? Type the numbers, e.g. *1 3 4* (or *none*):\n{list}"},
    "career_gap": {"en": (
        "🎯 *{now} → {next}*\n\n*You already have:* {have}\n*To build:* {need}\n\n*Your 90-day plan*\n"
        "• Weeks 1-4: {p1}\n• Weeks 5-8: {p2}\n• Weeks 9-12: {p3}\n\n"
        "I'll keep this. Come back any time with *career*."
    )},
    "career_none": {"en": "none yet"},
    "career_all": {"en": "all of them 👏"},
    "career_need_profile": {"en": "First, let's plan your next step so your CV has something to show."},
    "career_ask_langs": {"en": "Which languages do you speak? (e.g. *English, Swahili*)"},
    "career_cv_ready": {"en": "📄 Your CV is ready. Add your phone and email by hand before you send it; I don't keep them."},
    "career_apps_none": {"en": "No applications yet."},
    "career_apps_head": {"en": "📋 *My applications*"},
    "career_app_line": {"en": "• {company} · {role}: {status}{when}"},
    "career_ask_app": {"en": "Type the company and job, e.g. *Hilton, room attendant supervisor*."},
    "career_bad_app": {"en": "Please type the company and the job, separated by a comma."},
    "career_app_added": {"en": "✅ Added. Tap it later to update the status or add an interview date."},
    "career_pick_status": {"en": "What's the news for *{company}*?"},
    "career_ask_interview": {"en": "When is the interview? e.g. *02/12/2026*"},
    "career_bad_date": {"en": "Please type a future date, e.g. *02/12/2026*."},
    "career_interview_set": {"en": "✅ Interview saved for {date}. I'll remind you the day before. Practise with *interview practice*."},
    "career_status_saved": {"en": "✅ Updated."},
    "career_interview": {"en": (
        "🎤 *Practise these for {role}*\n{questions}\n\n"
        "*Tip:* answer with a short story: the situation, what you did, and the result.\n"
        "⚠️ A real employer never asks you to pay for an interview, a visa or a job."
    )},
    "career_find": {"en": (
        "🔎 *Finding jobs safely*\n"
        "• Apply on the company's own careers page, or through an agency you've checked is licensed (type *agency*).\n"
        "• Never pay a fee to get a job. Never send your passport before a real offer.\n"
        "• A real offer names the employer, job, salary and visa type, and the employer pays the visa.\n"
        "• Got an offer? Send it to me and I'll check it before you say yes."
    )},
    "career_change": {"en": (
        "🔁 *Changing jobs in the UAE* (MOHRE guidance, checked {checked})\n"
        "• You can move to a new employer when your contract ends, or if you and your employer agree to end it.\n"
        "• Serve the notice in your contract. Leaving during probation without the required notice can mean no new work permit for *one year*.\n"
        "• A proven complaint that you stopped coming to work (work abandonment) can also mean a one-year ban.\n"
        "• After your visa is cancelled you get a grace period to start a new job, change visa or leave.\n"
        "• Get your final settlement in writing. Type *gratuity* to estimate end-of-service pay."
    )},
}
S.update(STRINGS)

STATUSES = ("Applied", "Interview", "Offer", "Not selected", "Withdrew")


def career_menu(lang: str | None) -> Outgoing:
    keys = ("path", "cv", "apps", "interview", "find", "change")
    rows = [ListRow(id=f"career:{k}", title=t(f"career_m_{k}", lang), description=t(f"career_m_{k}_d", lang)) for k in keys]
    return Outgoing(text=t("career_menu", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def _profile(user) -> dict:  # type: ignore[no-untyped-def]
    p = repo.toolkit(user).get("career")
    return p if isinstance(p, dict) else {}


def _save(user, p: dict) -> None:  # type: ignore[no-untyped-def]
    repo.update_toolkit(user, career=p or None)


def gap_message(p: dict, lang: str | None) -> str:
    path = PATHS[p["path"]]
    have = [s for i, s in enumerate(path.skills) if i in set(p.get("have", []))]
    need = [s for i, s in enumerate(path.skills) if i not in set(p.get("have", []))]
    return t("career_gap", lang, now=path.now, next=path.next, have=", ".join(have) or t("career_none", lang),
             need=", ".join(need) or t("career_all", lang), p1=path.plan[0], p2=path.plan[1], p3=path.plan[2])


def build_cv(name: str, p: dict, employer: str | None, today: date, lang: str | None) -> bytes:
    path = PATHS[p["path"]]
    have = [s for i, s in enumerate(path.skills) if i in set(p.get("have", []))]
    years = p.get("years", 0)
    summary = (f"{path.now} with {years:g} year{'s' if years != 1 else ''} of experience in the UAE, working towards "
               f"{path.next.lower()}. Reliable, safety-minded and ready to take on more responsibility.")
    exp = [["Role", "Employer", "Experience"], [path.now, employer or "-", f"{years:g} years"]]
    return build_pdf(name, f"Aiming for: {path.next}", [
        Section("Summary", [summary]),
        Section("Experience", table=exp),
        Section("Skills", [", ".join(have) or "Hard-working, quick to learn"]),
        Section("Languages", [p.get("langs") or "-"]),
        Section("Contact", ["Phone: ____________    Email: ____________    References available on request."]),
    ], f"CV prepared {fmt_date(today, lang)}")


def apps_message(p: dict, lang: str | None) -> Outgoing:
    apps = p.get("apps") or []
    lines = [t("career_app_line", lang, company=a["company"], role=a["role"], status=a["status"],
               when=f" ({a['when']})" if a.get("when") else "") for a in apps]
    rows = [ListRow(id=f"career:app:{i}", title=a["company"][:24], description=f"{a['role']} · {a['status']}"[:72])
            for i, a in enumerate(apps[:8])]
    rows.append(ListRow(id="career:add", title="➕ Add application"))
    return Outgoing(text=t("career_apps_head", lang) + "\n" + ("\n".join(lines) or t("career_apps_none", lang)),
                    menu=ListMenu(button=t("btn_choose", lang), rows=rows))


def _out(state: AgentState, *msgs: Outgoing, **extra: Any) -> dict[str, Any]:
    return {"replies": [*state.get("replies", []), *msgs], **extra}


def _ev(state: AgentState, *new: tuple[str, str]) -> list[tuple[str, str]]:
    return [*state.get("events", []), *new]


def _back(lang: str | None) -> list[Button]:
    return [Button(id="career:menu", title=t("btn_career", lang)), Button(id="menu:main", title=t("btn_menu", lang))]


async def career(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user, msg = state["user"], state["incoming"]
    lang = user.language
    bid = msg.button_id or ""
    text = (state.get("text") or "").strip()
    today: date = ctx(config).get("today") or date.today()
    authorize(NODE, "get_own_profile")
    action = bid.removeprefix("career:") if bid.startswith("career:") else ""
    p = _profile(user)

    if not bid and user.step.startswith("career:"):
        authorize(NODE, "update_own_toolkit")
        step = user.step
        if step == "career:years":
            nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", text)]
            if len(nums) != 1 or not (0 <= nums[0] <= 50):
                return _out(state, Outgoing(text=t("career_ask_years", lang)))
            p["years"] = nums[0]
            _save(user, p)
            user.step = "career:skills"
            path = PATHS[p["path"]]
            listing = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(path.skills))
            return _out(state, Outgoing(text=t("career_ask_skills", lang, list=listing)))
        if step == "career:skills":
            n = len(PATHS[p["path"]].skills)
            p["have"] = sorted({int(x) - 1 for x in re.findall(r"\d+", text) if 1 <= int(x) <= n})
            _save(user, p)
            user.step = "ready"
            return _out(state, Outgoing(text=gap_message(p, lang),
                                        buttons=[Button(id="career:cv", title=t("career_m_cv", lang)),
                                                 Button(id="career:interview", title=t("career_m_interview", lang)[:20]),
                                                 Button(id="career:menu", title=t("btn_career", lang))]),
                        events=_ev(state, ("career_plan", p["path"])))
        if step == "career:langs":
            p["langs"] = text[:80]
            _save(user, p)
            user.step = "ready"
            authorize(NODE, "build_document")
            pdf = build_cv(repo.get_display_name(user) or "Your name", p, repo.toolkit(user).get("employer"), today, lang)
            return _out(state, Outgoing(text=t("career_cv_ready", lang), file=pdf, filename="my-cv.pdf", file_mime="application/pdf",
                                        buttons=_back(lang)), events=_ev(state, ("cv_built", p["path"])))
        if step == "career:add":
            parts = [x.strip() for x in text.split(",", 1)]
            if len(parts) != 2 or not all(2 <= len(x) <= 60 for x in parts):
                return _out(state, Outgoing(text=t("career_bad_app", lang)))
            apps = (p.get("apps") or [])[-(MAX_APPS - 1):]
            apps.append({"company": parts[0], "role": parts[1], "status": "Applied", "added": today.isoformat()})
            p["apps"] = apps
            _save(user, p)
            user.step = "ready"
            return _out(state, Outgoing(text=t("career_app_added", lang)), apps_message(p, lang),
                        events=_ev(state, ("job_application_added", "")))
        if step == "career:when":
            d = parse_date(text)
            i = int(p.get("cur", -1))
            apps = p.get("apps") or []
            if not d or d < today or not (0 <= i < len(apps)):
                return _out(state, Outgoing(text=t("career_bad_date", lang)))
            apps[i].update(status="Interview", when=fmt_date(d, lang))
            _save(user, p)
            user.step = "ready"
            authorize(NODE, "update_own_reminders")
            await reminders.add(ctx(config).get("db"), user.id, "interview", max(today, date.fromordinal(d.toordinal() - 1)),
                                f"Interview with {apps[i]['company']} on {fmt_date(d, lang)}. Type *interview practice* to prepare.")
            return _out(state, Outgoing(text=t("career_interview_set", lang, date=fmt_date(d, lang))), apps_message(p, lang),
                        events=_ev(state, ("interview_reminder", "")))
    user.step = "ready"
    cmd = state.get("command") or ""
    key = action or {"career": "", "cv": "cv", "job_change": "change", "interview_prep": "interview", "applications": "apps"}.get(cmd, "")

    if key == "path":
        rows = [ListRow(id=f"career:now:{k}", title=pth.now[:24], description=f"→ {pth.next}"[:72]) for k, pth in PATHS.items()]
        return _out(state, Outgoing(text=t("career_pick_now", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows)))
    if key.startswith("now:") and key[4:] in PATHS:
        _save(user, {**p, "path": key[4:], "have": []})
        user.step = "career:years"
        return _out(state, Outgoing(text=t("career_ask_years", lang)))
    if key == "cv":
        if not p.get("path"):
            rows = [ListRow(id=f"career:now:{k}", title=pth.now[:24], description=f"→ {pth.next}"[:72]) for k, pth in PATHS.items()]
            return _out(state, Outgoing(text=t("career_need_profile", lang)),
                        Outgoing(text=t("career_pick_now", lang), menu=ListMenu(button=t("btn_choose", lang), rows=rows)))
        user.step = "career:langs"
        return _out(state, Outgoing(text=t("career_ask_langs", lang)))
    if key == "apps":
        return _out(state, apps_message(p, lang))
    if key == "add":
        user.step = "career:add"
        return _out(state, Outgoing(text=t("career_ask_app", lang)))
    m = re.fullmatch(r"app:(\d+)", key)
    if m and int(m.group(1)) < len(p.get("apps") or []):
        i = int(m.group(1))
        rows = [ListRow(id=f"career:st:{j}:{i}", title=s) for j, s in enumerate(STATUSES)]
        return _out(state, Outgoing(text=t("career_pick_status", lang, company=p["apps"][i]["company"]),
                                    menu=ListMenu(button=t("btn_choose", lang), rows=rows)))
    m = re.fullmatch(r"st:(\d):(\d+)", key)
    if m and int(m.group(2)) < len(p.get("apps") or []) and int(m.group(1)) < len(STATUSES):
        j, i = int(m.group(1)), int(m.group(2))
        authorize(NODE, "update_own_toolkit")
        if STATUSES[j] == "Interview":
            _save(user, {**p, "cur": i})
            user.step = "career:when"
            return _out(state, Outgoing(text=t("career_ask_interview", lang)))
        p["apps"][i]["status"] = STATUSES[j]
        _save(user, p)
        return _out(state, Outgoing(text=t("career_status_saved", lang)), apps_message(p, lang),
                    events=_ev(state, ("job_application_status", STATUSES[j])))
    if key == "interview":
        path = PATHS.get(p.get("path", ""), PATHS["housekeeping"])
        qs = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(path.questions))
        return _out(state, Outgoing(text=t("career_interview", lang, role=path.next, questions=qs), buttons=_back(lang)))
    if key == "find":
        return _out(state, Outgoing(text=t("career_find", lang), buttons=[Button(id="job:check", title="Check an offer"), *_back(lang)][:3]))
    if key == "change":
        return _out(state, Outgoing(text=t("career_change", lang, checked="2026-11-24"), buttons=_back(lang)))
    if p.get("path") and key == "plan":
        return _out(state, Outgoing(text=gap_message(p, lang), buttons=_back(lang)))
    return _out(state, career_menu(lang))
