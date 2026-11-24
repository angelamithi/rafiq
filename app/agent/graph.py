"""The LangGraph agent.

    START -> route -> onboarding | menu | privacy | fallback | job_safety | stay_legal | departure | arrival | pay | social | money | help | tasks | cases | protection | life | growth | housing | health | career | services | renewals -> END

Input and output guards run in app/service.py, *outside* the graph, so no
node (and no future AI node) can skip them. Later modules add their own nodes
and routes here.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.modules.arrival.content import TOPICS as ARRIVAL_TOPICS
from app.modules.arrival.node import arrival
from app.modules.departure.node import departure
from app.modules.help.node import help_node, unsafe_intent
from app.modules.job_safety.node import job_safety
from app.modules.money.node import money, money_intent
from app.modules.pay.node import pay
from app.modules.social.node import crisis_intent, social
from app.modules.job_safety.rules import looks_like_offer, vague_offer
from app.modules.stay_legal.node import legal_intent, stay_legal
from app.modules.career.node import career
from app.modules.cases.node import cases
from app.modules.growth.node import growth
from app.modules.health.node import health
from app.modules.housing.node import housing
from app.modules.pay.wagecheck import looks_like_shortfall
from app.modules.renewals.node import looks_official, renewals
from app.modules.services.node import services
from app.modules.life.node import life
from app.modules.protection.node import needs_protection, protection
from app.modules.tasks.node import JOIN_RE, tasks
from app.agent.parsing import simplify
from app.agent.state import AgentState, ctx

COMMANDS: dict[str, set[str]] = {
    "menu": {"menu", "main menu", "home", "options", "0"},
    "help": {"help", "emergency", "help me"},
    "profile": {"profile", "my profile", "my details"},
    "privacy": {"privacy"},
    "export": {"my data", "see my data", "export", "show my data"},
    "delete": {"delete", "delete my data", "delete account", "erase my data", "delete me"},
    "job": {"check offer", "check an offer", "check job", "check a job", "job offer", "check job offer", "check a job offer",
            "is this job real", "is this offer real", "scam", "is this a scam", "check scam", "job check"},
    "agency": {"check agency", "check an agency", "check recruitment agency", "is this agency real", "agency"},
    "legal": {"stay legal", "legal", "laws", "law", "is it legal"},
    "visa": {"my visa", "visa", "visa status", "visa expiry", "when does my visa expire", "check my visa"},
    "medicine_prompt": {"medicine", "medicines", "medicine check", "check medicine", "check my medicine", "medication"},
    "work": {"can i work", "work rules", "work permit", "part time", "part-time", "second job"},
    "post": {"can i post this", "can i post", "posting rules", "social media rules"},
    "rules": {"rules", "everyday rules", "uae rules", "uae laws"},
    "plan": {"checklist", "my checklist", "before you fly", "before i fly", "before i travel", "departure",
             "departure checklist", "departure planner", "travel checklist", "pre departure", "pre departure checklist",
             "packing", "packing list", "what to pack", "what should i pack", "plan", "my plan", "travel plan"},
    "plan_date": {"travel date", "my travel date", "flight date", "my flight date", "set travel date", "change travel date"},
    "arrive": {"arrival", "arrival guide", "first weeks", "my first weeks", "your first weeks", "just arrived",
               "i just arrived", "i have arrived", "i arrived", "i ve arrived", "new arrival", "settling in", "after arrival"},
    "arrive_date": {"arrival date", "my arrival date", "set arrival date", "change arrival date"},
    "pay": {"pay", "pay and rights", "pay rights", "my pay", "my salary", "salary", "rights", "my rights",
            "workers rights", "work rights", "labour rights", "labor rights"},
    "salary_watch": {"salary watch", "salary record", "my salary record", "salary check", "salary check in"},
    "salary_late": {"salary late", "late salary", "my salary is late", "salary is late", "salary delayed",
                    "delayed salary", "late pay"},
    "pay_paid": {"paid", "salary paid", "i got paid", "got paid", "got my salary", "salary received",
                 "received my salary", "yes paid", "paid in full"},
    "pay_part": {"part", "part paid", "partly paid", "partial", "partial salary", "only part", "half salary",
                 "half paid", "paid part"},
    "pay_unpaid": {"not paid", "not paid yet", "no salary", "salary not paid", "i was not paid", "unpaid",
                   "unpaid salary", "salary not received", "not received"},
    "complaint": {"complaint", "make a complaint", "write a complaint", "file a complaint", "complain",
                  "report my employer", "report employer", "labour complaint", "labor complaint"},
    "gratuity": {"gratuity", "end of service", "end of service pay", "final settlement", "gratuity calculator",
                 "end of service gratuity"},
    "overtime_calc": {"overtime calculator", "calculate overtime", "calculate my overtime", "overtime pay",
                      "how much overtime", "overtime calculation", "my overtime pay", "overtime owed"},
    "work_hours": {"working hours", "overtime", "annual leave", "leave", "sick leave", "day off", "days off",
                   "rest day", "holidays", "hours"},
    "social": {"friends and wellbeing", "wellbeing", "social", "social circle"},
    "lonely": {"lonely", "i feel lonely", "i am lonely", "im lonely", "i m lonely", "feeling lonely", "so lonely",
               "homesick", "i am homesick", "i m homesick", "i miss home", "i miss my family", "sad", "i feel sad",
               "i am sad", "i m sad", "feeling sad", "depressed", "i feel depressed", "i am depressed", "alone",
               "i feel alone", "i am alone"},
    "free_things": {"free things to do", "things to do", "what to do", "weekend", "free events", "events",
                    "whats on", "what s on", "this weekend"},
    "meet": {"meet people", "make friends", "meet people safely", "friends", "find friends", "community",
             "new friends"},
    "talk": {"talk to someone", "counsellor", "counselor", "mental health", "helpline", "need to talk",
             "i need to talk", "therapist", "someone to talk to"},
    "wellbeing_checkin": {"weekly check in", "wellbeing check in", "check in"},
    "mood_good": {"good", "good week", "great", "great week", "fine", "it was good", "very good"},
    "mood_ok": {"ok", "okay", "ok week", "okay week", "so so", "not bad", "average"},
    "mood_hard": {"hard", "hard week", "bad", "bad week", "not good", "terrible", "awful", "difficult week",
                  "tough week", "very hard", "it was hard"},
    "money": {"money", "money home", "send money home", "remittance", "remittances", "sending money"},
    "send_money": {"send money", "transfer money", "how to send money", "hawala", "exchange house", "send money safely"},
    "compare_costs": {"compare", "compare rates", "exchange rate", "exchange rates", "best rate", "compare transfer",
                      "transfer cost", "transfer costs", "cheapest way to send money"},
    "budget": {"budget", "money plan", "monthly plan", "my budget", "save money", "saving", "savings"},
    "loans": {"loan", "loans", "debt", "debts", "credit card", "borrow money", "i need a loan", "need a loan", "loan app"},
    "money_scams": {"money scam", "money scams", "bank scam", "otp", "fake bank", "bank called me"},
    "rent_account": {"money mule", "rent my account", "rent my bank account", "lend my account"},
    "embassy": {"embassy", "my embassy", "consulate", "my consulate", "embassy contact", "embassy number"},
    "lost_passport": {"lost passport", "i lost my passport", "passport lost", "lost my passport", "stolen passport",
                      "passport stolen", "lost emirates id", "lost my emirates id", "lost id", "lost my id"},
    "report_crime": {"report crime", "report a crime", "al ameen", "report to police"},
    "police_trouble": {"arrested", "i was arrested", "police case", "court case", "jail", "in jail", "detained",
                       "travel ban", "police stopped me"},
    "numbers": {"numbers", "useful numbers", "emergency numbers", "important numbers", "phone numbers"},
    "unsafe": {"not safe", "i am not safe", "i m not safe", "unsafe", "abuse", "i am abused", "human trafficking",
               "trafficking", "help me please", "domestic violence"},
    # "Do it for me"
    "tasks": {"do it for me", "tasks", "do this for me", "toolkit"},
    "pack": {"evidence pack", "unpaid wages pack", "wages pack", "wage pack", "unpaid wages", "evidence",
             "wage theft", "wage record", "unpaid salary record", "proof of unpaid salary"},
    "vault": {"my documents", "documents", "document vault", "vault", "save document", "save a document",
              "save my passport", "my papers", "document safe", "save my documents", "passport copy", "copy of my passport"},
    "sos_menu": {"trusted contact", "sos contact", "emergency contact", "my trusted contact", "set up sos"},
    "sos": {"sos", "send sos", "alert my contact", "send an sos"},
    "sos_leave": {"stop sos"},
    "rate": {"rate alert", "exchange rate alert", "rate alerts", "alert me about the rate", "tell me when the rate goes up"},
    "forms": {"letters", "letter", "forms", "write a letter", "letters and forms", "passport letter",
              "leave letter", "resignation letter", "salary certificate", "resign", "resignation"},
    "contract": {"contract check", "contract switch", "compare contract", "check my contract", "contract substitution",
                 "contract switch check", "compare my contract"},
    "task_status": {"what are you doing for me", "my reminders", "my alerts", "what i m doing for you",
                    "what are you doing for you", "status"},
    "salary_gaps": {"what am i owed", "what i m owed", "money owed", "owed", "salary gap", "promised vs received",
                    "how much am i owed", "how much does my employer owe me"},
    "payslip": {"payslip", "read my payslip", "check my payslip", "pay slip", "my payslip"},
    "cases": {"my cases", "cases", "case", "my case", "my complaint", "complaint status", "track my complaint",
              "dispute", "my complaints", "case manager"},
    "brief": {"brief", "my brief", "life manager", "what needs my attention", "what should i do today", "today",
              "what do i need to do", "my week", "weekly brief", "what s next", "what is next"},
    "brief_on": {"brief on", "turn on weekly brief", "send me a weekly brief"},
    "brief_off": {"brief off", "stop brief", "stop weekly brief", "no more brief"},
    # Lead task: renewals
    "renewals": {"my renewals", "renewals", "renew", "renewal", "renewal reminders", "deadlines", "my deadlines",
                 "what expires", "expiry dates", "my documents expiry"},
    "renew_visa": {"visa renewal", "renew my visa", "renew visa", "residence renewal", "renew residence visa", "renew my residence"},
    "renew_eid": {"emirates id renewal", "renew emirates id", "renew my emirates id", "renew eid", "eid renewal"},
    "renew_passport": {"passport renewal", "renew passport", "renew my passport"},
    "legal_aid": {"free lawyer", "legal aid", "legal help", "need a lawyer", "i need a lawyer", "free legal advice",
                  "find a lawyer", "lawyer", "free legal help"},
    "status_check": {"am i ok", "am i ok?", "status check", "check my status", "am i legal", "am i legal?", "check me",
                     "is everything ok", "is my status ok", "my status"},
    # Growth areas
    "grow": {"grow my money", "savings", "savings goal", "save money", "saving", "how to save", "grow money"},
    "goals": {"my goals", "savings goals", "my savings"},
    "family_budget": {"family budget", "budget check", "check my budget", "i never save", "i cant save"},
    "loan_cost": {"loan cost", "loan calculator", "cost of a loan"},
    "housing": {"housing", "accommodation", "find a room", "room for rent", "landlord", "tenant", "my room",
                "flat", "apartment"},
    "rent_increase": {"rent increase", "landlord increased rent", "rent went up", "rent hike"},
    "check_room": {"check a room", "check room", "check rental", "rental agreement", "tenancy contract"},
    "health": {"health", "doctor", "clinic", "hospital", "sick", "medical", "i am sick", "i feel sick", "pharmacy"},
    "health_insurance": {"medical insurance", "insurance card", "no insurance card", "my insurance"},
    "health_emergency": {"ambulance", "medical emergency"},
    "appointment": {"appointment", "doctor appointment", "remind me of my appointment"},
    "career": {"career", "promotion", "better job", "next job", "skills", "training", "courses", "grow my career"},
    "cv": {"cv", "my cv", "make my cv", "write my cv", "my resume"},
    "job_change": {"change job", "switch job", "change my job", "move to another company", "job transfer"},
    "interview_prep": {"interview", "interview practice", "job interview"},
    "applications": {"my applications", "job applications"},
    "services": {"find help", "services", "directory", "who can help", "trusted services", "where can i get help"},
    "stop": {"stop", "unsubscribe", "pause"},
    "start": {"start", "resume"},
    "greeting": {"hi", "hello", "hey", "hiya", "salaam", "salam", "hi rafiq", "hello rafiq",
                 "good morning", "good evening", "good afternoon"},
}
_LOOKUP = {phrase: cmd for cmd, phrases in COMMANDS.items() for phrase in phrases}
# Arrival topics ("emirates id", "ejari"...) open one step; never override a command above.
for _key, _phrases in ARRIVAL_TOPICS.items():
    for _p in _phrases:
        _LOOKUP.setdefault(_p, f"arrive_topic:{_key}")
PRIVACY_COMMANDS = {"privacy", "export", "delete"}
ALWAYS_AVAILABLE = {"help"} | PRIVACY_COMMANDS  # work even in the middle of setup
LEGAL_COMMANDS = {"legal", "visa", "medicine_prompt", "work", "post", "rules"}
PLAN_COMMANDS = {"plan", "plan_date"}
ARRIVE_COMMANDS = {"arrive", "arrive_date"}
SOCIAL_COMMANDS = {"social", "lonely", "free_things", "meet", "talk", "wellbeing_checkin", "mood_good", "mood_ok",
                   "mood_hard"}
CASE_COMMANDS = {"cases", "legal_aid"}
LIFE_COMMANDS = {"brief", "brief_on", "brief_off"}
GROW_ROUTES = {"grow": "growth", "goals": "growth", "family_budget": "growth", "loan_cost": "growth",
               "housing": "housing", "rent_increase": "housing", "check_room": "housing",
               "health": "health", "health_insurance": "health", "health_emergency": "health", "appointment": "health",
               "career": "career", "cv": "career", "job_change": "career", "interview_prep": "career",
               "applications": "career", "services": "services",
               "renewals": "renewals", "renew_visa": "renewals", "renew_eid": "renewals", "renew_passport": "renewals", "status_check": "renewals"}
PREFIX_ROUTES = {"rnw": "renewals", "grow": "growth", "home": "housing", "health": "health", "career": "career", "svc": "services"}
TASK_COMMANDS = {"tasks", "pack", "vault", "sos_menu", "sos", "rate", "forms", "contract", "task_status"}
HELP_COMMANDS = {"help", "embassy", "lost_passport", "report_crime", "police_trouble", "numbers", "unsafe"}
MONEY_COMMANDS = {"money", "send_money", "compare_costs", "budget", "loans", "money_scams", "rent_account"}
PAY_COMMANDS = {"pay", "salary_watch", "salary_late", "pay_paid", "pay_part", "pay_unpaid", "complaint", "gratuity",
                "work_hours", "salary_gaps", "payslip", "overtime_calc"}


def _is_arrival(command: str | None) -> bool:
    return bool(command) and (command in ARRIVE_COMMANDS or command.startswith("arrive_topic:"))


# Natural speech ("can you please check my job offer") rarely matches a command
# exactly, especially from voice notes. Fillers are removed from both sides.
_FILLERS = re.compile(
    r"\b(please|pls|plz|kindly|thanks?|thank you|rafiq|hi|hello|hey|ok|okay|so|um+|uh+|"
    r"can you|could you|would you|will you|i want to|i would like to|i d like to|i need to|i wanna|"
    r"help me|tell me|show me|let me|how do i|i want|i need|my|a|an|the|me|for|about)\b")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", _FILLERS.sub(" ", simplify(text))).strip()


_LOOKUP_NORM: dict[str, str] = {}
for _phrase, _cmd in _LOOKUP.items():
    if (_n := _norm(_phrase)) and len(_n) >= 3:
        _LOOKUP_NORM.setdefault(_n, _cmd)


def detect_command(text: str) -> str | None:
    s = simplify(text)
    if s in _LOOKUP:
        return _LOOKUP[s]
    if len(s) > 80:          # long messages are content, not commands
        return None
    n = _norm(text)
    return _LOOKUP_NORM.get(n) if len(n) >= 3 else None


def _rule_route(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    user = state["user"]
    msg = state["incoming"]
    settings = ctx(config).get("settings")
    command = detect_command(state.get("text", "")) if msg.kind == "text" else None
    bid = msg.button_id or ""
    prefix = bid.split(":", 1)[0] if bid else ""

    # Safety net, before anything else (even mid-setup): mentions of suicide or
    # self-harm always get support lines first. Nothing is stored about it.
    if msg.kind == "text" and crisis_intent(state.get("text", "")):
        return {"command": "crisis", "route": "social"}
    # Same for abuse, confinement, forced work or trafficking.
    # Protection early warning: several exploitation signs together (or one severe
    # sign with another) go to the Protection agent, even mid-setup.
    if msg.kind == "text" and needs_protection(state.get("text", "")):
        return {"command": "warning", "route": "protection"}
    if prefix == "pro":
        return {"command": command, "route": "protection"}
    if msg.kind == "text" and unsafe_intent(state.get("text", "")):
        return {"command": "unsafe_detected", "route": "help"}

    # Someone accepting a trusted-contact invite (often new to Rafiq), or removing themselves.
    if msg.kind == "text" and JOIN_RE.match(state.get("text", "")):
        return {"command": "sos_join", "route": "tasks"}
    if command == "sos_leave":
        return {"command": "sos_leave", "route": "tasks"}
    if user.step == "new":
        return {"command": None, "route": "onboarding"}

    # Privacy notice changed since the user agreed: ask again before anything else.
    current = getattr(settings, "privacy_policy_version", None)
    if user.consent_status == "granted" and current and user.consent_version != current and user.step == "ready":
        user.step, user.return_to = "consent", "ready"
        return {"command": None, "route": "onboarding", "reconsent": True}

    if user.step.startswith("task:") and bid and prefix != "task":
        user.step = "ready"     # tapped something else: leave the task
    if prefix in ("privacy", "delete"):
        return {"command": command, "route": "privacy"}
    if bid == "menu:job" or prefix == "job":
        return {"command": command, "route": "job_safety"}
    if bid == "menu:legal" or prefix in ("legal", "work", "post"):
        return {"command": command, "route": "stay_legal"}
    if bid == "menu:plan" or prefix == "plan":
        return {"command": command, "route": "departure"}
    if bid == "menu:arrive" or prefix == "arrive":
        return {"command": command, "route": "arrival"}
    if bid == "menu:pay" or prefix == "pay":
        return {"command": command, "route": "pay"}
    if bid == "menu:social" or prefix == "social":
        return {"command": command, "route": "social"}
    if bid == "menu:money" or prefix == "money":
        return {"command": command, "route": "money"}
    if user.consent_status == "granted" and (prefix in PREFIX_ROUTES or bid == "menu:grow"):
        return {"command": "hub" if bid == "menu:grow" else command, "route": PREFIX_ROUTES.get(prefix, "services")}
    if user.step == "pay:await_wc" and msg.kind == "text" and user.consent_status == "granted" and not command in ("menu", "stop", "start"):
        return {"command": "gratuity_input", "route": "pay"}     # the two amounts for a wage check
    step_prefix = user.step.split(":", 1)[0]
    if step_prefix in PREFIX_ROUTES and ":" in user.step and user.consent_status == "granted":
        if msg.kind == "text" and command and not user.step.startswith(("rnw:sms:", "pay:await_wc")):
            user.step = "ready"
        else:
            return {"command": "step_input", "route": PREFIX_ROUTES[step_prefix]}
    if (msg.kind == "text" and user.step == "ready" and user.consent_status == "granted"
            and looks_official(state.get("text", ""))):
        return {"command": "rnw_sms", "route": "renewals"}      # a forwarded ICP/GDRFA/Amer status message
    if (msg.kind == "text" and user.step == "ready" and user.consent_status == "granted"
            and looks_like_shortfall(state.get("text", "")) and not looks_like_offer(state.get("text", ""))):
        return {"command": "wage_check", "route": "pay"}        # "I was supposed to get 1800 but only got 1000"
    if prefix == "life" and user.consent_status == "granted":
        return {"command": command, "route": "life"}
    if prefix == "case" and user.consent_status == "granted":
        return {"command": command, "route": "cases"}
    if user.step.startswith("case:") and user.consent_status == "granted":
        if msg.kind == "text" and command:
            user.step = "ready"
        else:
            return {"command": "case_input", "route": "cases"}
    if (bid == "menu:tasks" or prefix == "task") and user.consent_status == "granted":
        return {"command": command, "route": "tasks"}
    # A shared location is only ever used for an SOS.
    if msg.kind == "location" and user.consent_status == "granted":
        return {"command": "location", "route": "tasks"}
    # Waiting for an answer to a task question: a known command leaves the task;
    # anything else (text, photo, PDF) is the answer.
    if user.step.startswith("task:"):
        if msg.kind == "text" and command:
            user.step = "ready"
        else:
            return {"command": "task_input", "route": "tasks"}
    if (bid == "menu:help" or prefix == "help") and user.step not in nodes.ONBOARDING_STEPS:
        return {"command": command, "route": "help"}
    if prefix in ("menu", "profile"):
        return {"command": command, "route": "menu"}

    # Modules 2-5: waiting for a job offer / a medicine / a date. Global
    # commands still work; anything else is the thing we're waiting for.
    if user.step.startswith(("job:", "legal:", "plan:", "arrive:", "pay:", "money:")):
        if command in PRIVACY_COMMANDS:
            return {"command": command, "route": "privacy"}
        if command in PLAN_COMMANDS:
            return {"command": command, "route": "departure"}
        if _is_arrival(command):
            return {"command": command, "route": "arrival"}
        if command in PAY_COMMANDS:
            return {"command": command, "route": "pay"}
        if command in SOCIAL_COMMANDS:
            return {"command": command, "route": "social"}
        if command in MONEY_COMMANDS:
            return {"command": command, "route": "money"}
        if command in HELP_COMMANDS:
            return {"command": command, "route": "help"}
        if command in TASK_COMMANDS:
            user.step = "ready"
            return {"command": command, "route": "tasks"}
        if command in CASE_COMMANDS:
            user.step = "ready"
            return {"command": command, "route": "cases"}
        if command in LIFE_COMMANDS:
            user.step = "ready"
            return {"command": command, "route": "life"}
        if command in GROW_ROUTES:
            user.step = "ready"
            return {"command": command, "route": GROW_ROUTES[command]}
        if command in LEGAL_COMMANDS:
            user.step = "ready"
            return {"command": command, "route": "stay_legal"}
        if command in ("menu", "help", "profile", "stop", "start", "greeting", "agency", "job"):
            user.step = "ready"
            return {"command": command, "route": "job_safety" if command in ("agency", "job") else "menu"}
        if user.step.startswith("legal:"):
            return {"command": "medicine", "route": "stay_legal"}
        if user.step.startswith("plan:"):
            return {"command": "travel_date", "route": "departure"}
        if user.step.startswith("arrive:"):
            return {"command": "arrival_date", "route": "arrival"}
        if user.step.startswith("pay:"):
            return {"command": "gratuity_input", "route": "pay"}
        if user.step.startswith("money:"):
            return {"command": "money_input", "route": "money"}
        return {"command": "offer", "route": "job_safety"}

    if user.step != "ready":
        if command in ALWAYS_AVAILABLE:
            return {"command": command, "route": "privacy" if command in PRIVACY_COMMANDS else "menu"}
        if command in ("menu", "greeting", "profile", "stop", "start") and user.consent_status == "granted":
            return {"command": command, "route": "menu"}
        return {"command": command, "route": "onboarding"}

    if command in PRIVACY_COMMANDS:
        return {"command": command, "route": "privacy"}
    if command in ("job", "agency"):
        return {"command": command, "route": "job_safety"}
    if command in LEGAL_COMMANDS:
        return {"command": command, "route": "stay_legal"}
    if command in PLAN_COMMANDS:
        return {"command": command, "route": "departure"}
    if _is_arrival(command):
        return {"command": command, "route": "arrival"}
    if command in PAY_COMMANDS:
        return {"command": command, "route": "pay"}
    if command in SOCIAL_COMMANDS:
        return {"command": command, "route": "social"}
    if command in MONEY_COMMANDS:
        return {"command": command, "route": "money"}
    if command in HELP_COMMANDS:
        return {"command": command, "route": "help"}
    if command in TASK_COMMANDS:
        return {"command": command, "route": "tasks"}
    if command in CASE_COMMANDS:
        return {"command": command, "route": "cases"}
    if command in LIFE_COMMANDS and user.consent_status == "granted":
        return {"command": command, "route": "life"}
    if command in GROW_ROUTES and user.consent_status == "granted":
        return {"command": command, "route": GROW_ROUTES[command]}
    if command:
        return {"command": command, "route": "menu"}
    if msg.kind == "text" and looks_like_offer(state.get("text", "")):
        return {"command": "offer", "route": "job_safety", "auto_offer": True}
    if msg.kind == "text" and vague_offer(state.get("text", "")):
        return {"command": "offer_vague", "route": "job_safety"}
    if msg.kind == "text" and (intent := legal_intent(state.get("text", ""))):
        return {"command": intent, "route": "stay_legal"}
    if msg.kind == "text" and (intent := money_intent(state.get("text", ""))):
        return {"command": intent, "route": "money"}
    if msg.kind == "media" and msg.media_type in ("image", "document"):
        return {"command": "offer", "route": "job_safety"}  # a photo/PDF is most likely an offer to check
    return {"command": None, "route": "fallback"}


async def route(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """The orchestrator: decides the specialist, then records which agent handled it."""
    decided = await _decide(state, config)
    from app.agent.agents import agent_for

    agent = agent_for(decided.get("route", "fallback"), decided.get("command"), state["incoming"].button_id,
                      state["user"].step)
    events = decided.get("events", state.get("events", []))
    return {**decided, "agent": agent, "events": [*events, ("handled_by", agent)]}


async def _decide(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Rules first (fast, predictable, safety nets). Only if they don't recognise
    a typed message does the AI pick a topic, from a fixed list (app/agent/intent.py)."""
    decided = _rule_route(state, config)
    user, msg = state["user"], state["incoming"]
    if decided.get("route") != "fallback" or msg.kind != "text" or user.step != "ready":
        return decided
    from app.agent.intent import understand
    from app.config import get_settings

    cfg = ctx(config)
    found = await understand(state.get("text", ""), user=user, cfg=cfg, settings=cfg.get("settings") or get_settings())
    if found is None:
        return decided
    return {"command": found.command, "route": found.route, "inferred_topic": found.topic,
            "events": [*state.get("events", []), ("intent_ai", found.command)]}


def _pick(state: AgentState) -> str:
    return state["route"]


@lru_cache
def build_graph():  # type: ignore[no-untyped-def]
    g = StateGraph(AgentState)
    g.add_node("route", route)
    g.add_node("onboarding", nodes.onboarding)
    g.add_node("menu", nodes.menu)
    g.add_node("privacy", nodes.privacy)
    g.add_node("fallback", nodes.fallback)
    g.add_node("job_safety", job_safety)
    g.add_node("stay_legal", stay_legal)
    g.add_node("departure", departure)
    g.add_node("arrival", arrival)
    g.add_node("pay", pay)
    g.add_node("social", social)
    g.add_node("money", money)
    g.add_node("help", help_node)
    g.add_node("tasks", tasks)
    g.add_node("cases", cases)
    g.add_node("protection", protection)
    g.add_node("life", life)
    for name, fn in (("renewals", renewals), ("growth", growth), ("housing", housing), ("health", health), ("career", career), ("services", services)):
        g.add_node(name, fn)
    g.add_edge(START, "route")
    routes = ["onboarding", "menu", "privacy", "fallback", "job_safety", "stay_legal", "departure", "arrival", "pay", "social", "money", "help", "tasks", "cases", "protection", "life", "growth", "housing", "health", "career", "services", "renewals"]
    g.add_conditional_edges("route", _pick, routes)
    for n in routes:
        g.add_edge(n, END)
    return g.compile()
