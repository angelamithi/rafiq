"""Least-privilege rules for agent tools (counters tool misuse and privilege
escalation).

Principles:
- Each graph node may only call the tools on its allow-list.
- Tools never accept a user id from the model. The acting user always comes
  from the verified webhook (server-side context), so the model cannot act on
  another person's data.
- Destructive or outward-facing tools need an explicit user confirmation that
  carries a one-time server-generated nonce. The model cannot create one.
- There are no admin tools reachable from chat. Admin work happens in a
  separate authenticated app.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass


class ToolNotAllowed(PermissionError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    destructive: bool = False      # needs a confirmed nonce
    outward: bool = False          # sends something outside the chat (email, complaint, etc.)


TOOLS: dict[str, ToolSpec] = {
    "get_own_profile": ToolSpec("get_own_profile"),
    "update_own_profile": ToolSpec("update_own_profile"),
    "export_own_data": ToolSpec("export_own_data"),
    "delete_own_data": ToolSpec("delete_own_data", destructive=True),
    "check_job_offer": ToolSpec("check_job_offer"),   # read-only: analyses text, stores nothing
    "check_medicine": ToolSpec("check_medicine"),     # read-only: matches a name, stores nothing
    "get_own_plan": ToolSpec("get_own_plan"),         # Modules 4-5: own checklists + dates
    "update_own_plan": ToolSpec("update_own_plan"),   # tick items / set travel date (own record only)
    "get_own_pay": ToolSpec("get_own_pay"),           # Module 6: own salary record
    "update_own_pay": ToolSpec("update_own_pay"),     # record paid/part/unpaid, check-ins on/off
    "draft_complaint": ToolSpec("draft_complaint"),   # builds text for the USER to send; Rafiq sends nothing
    "update_own_wellbeing_pref": ToolSpec("update_own_wellbeing_pref"),  # Module 7: weekly check-ins on/off
    # "Do it for me"
    "update_own_toolkit": ToolSpec("update_own_toolkit"),   # employer, salary, rate alert... (own record only)
    "build_document": ToolSpec("build_document"),           # makes a PDF for the USER; Rafiq sends it nowhere else
    "get_own_vault": ToolSpec("get_own_vault"),             # own saved documents only (filtered by user id)
    "update_own_vault": ToolSpec("update_own_vault"),       # save / delete own documents
    "send_sos": ToolSpec("send_sos", outward=True),         # ONLY to the opted-in trusted contact, after confirmation
    "save_to_vault": ToolSpec("save_to_vault"),             # add own offer/contract copies; cannot read the vault
    "get_own_cases": ToolSpec("get_own_cases"),             # own dispute cases and incident records
    "update_own_cases": ToolSpec("update_own_cases"),       # open a case, add a note, record a reference or outcome
    "assess_risk": ToolSpec("assess_risk"),
    "update_own_reminders": ToolSpec("update_own_reminders"),
    "get_own_reminders": ToolSpec("get_own_reminders"),   # rent day, appointments, interviews, savings check-ins
    "check_document": ToolSpec("check_document"),               # read-only: reads a rental ad or agreement the user sent                 # read-only: scores exploitation signs in the user's own words
}

# Which node may call which tool. Later modules add their own entries.
NODE_ALLOWLIST: dict[str, set[str]] = {
    "onboarding": {"get_own_profile", "update_own_profile"},
    "menu": {"get_own_profile", "update_own_profile"},
    "privacy": {"get_own_profile", "get_own_plan", "get_own_pay", "export_own_data", "delete_own_data"},
    "job_safety": {"get_own_profile", "check_job_offer"},
    "stay_legal": {"get_own_profile", "check_medicine"},
    "departure": {"get_own_profile", "get_own_plan", "update_own_plan"},
    "arrival": {"get_own_profile", "get_own_plan", "update_own_plan"},
    "pay": {"get_own_profile", "get_own_pay", "update_own_pay", "draft_complaint", "update_own_cases", "build_document"},
    "social": {"get_own_profile", "update_own_wellbeing_pref"},
    "money": {"get_own_profile"},   # read-only: home country for the currency name; stores nothing
    "help": {"get_own_profile"},    # read-only: home country, to show the right embassy
    "tasks": {"get_own_profile"},
    # "Do it for me" actions run inside the tasks node but are authorised as the agent that owns them.
    "tasks.employment": {"get_own_profile", "update_own_toolkit", "build_document", "save_to_vault", "get_own_pay",
                         "update_own_pay"},
    "tasks.life_admin": {"get_own_profile", "update_own_toolkit", "get_own_vault", "update_own_vault"},
    "tasks.protection": {"get_own_profile", "update_own_toolkit", "send_sos"},
    "tasks.financial": {"get_own_profile", "update_own_toolkit"},
    "cases": {"get_own_profile", "get_own_pay", "get_own_cases", "update_own_cases", "build_document"},
    "protection": {"get_own_profile", "assess_risk", "get_own_cases", "update_own_cases", "build_document"},
    "life": {"get_own_profile", "get_own_plan", "get_own_pay", "get_own_vault", "get_own_cases", "get_own_reminders"},
    "growth": {"get_own_profile", "update_own_toolkit", "update_own_reminders"},
    "housing": {"get_own_profile", "update_own_toolkit", "update_own_reminders", "check_document", "update_own_cases"},
    "health": {"get_own_profile", "update_own_toolkit", "update_own_reminders"},
    "career": {"get_own_profile", "update_own_toolkit", "build_document", "update_own_reminders"},
    "services": {"get_own_profile"},
    "renewals": {"get_own_profile", "get_own_vault", "update_own_toolkit", "update_own_reminders", "build_document"},
    "fallback": set(),
}

# Second wall: whatever a node's list says, a tool is refused if the AGENT that owns
# the node doesn't hold it (app/agent/agents.py). This is where data scopes live:
# e.g. no Financial or Wellbeing node can ever be given the vault.
AGENT_ALLOWLIST: dict[str, set[str]] = {
    "orchestrator": {"get_own_profile", "update_own_profile", "get_own_plan", "get_own_pay", "export_own_data",
                     "delete_own_data"},
    "employment": {"get_own_profile", "check_job_offer", "get_own_pay", "update_own_pay", "draft_complaint",
                   "update_own_toolkit", "build_document", "save_to_vault", "get_own_cases", "update_own_cases"},
    "protection": {"get_own_profile", "assess_risk", "update_own_toolkit", "send_sos", "get_own_cases",
                   "update_own_cases", "build_document"},
    "life_admin": {"get_own_profile", "check_medicine", "get_own_plan", "update_own_plan", "get_own_vault",
                   "update_own_vault", "update_own_toolkit", "get_own_pay", "get_own_cases", "update_own_reminders",
                   "check_document", "update_own_cases", "get_own_reminders", "build_document"},
    "financial": {"get_own_profile", "update_own_toolkit", "update_own_reminders"},
    "wellbeing": {"get_own_profile", "update_own_wellbeing_pref", "update_own_toolkit", "update_own_reminders"},
    "career": {"get_own_profile", "update_own_toolkit", "build_document", "update_own_reminders"},
}


def agent_of(node: str) -> str:
    if node.startswith("tasks."):
        return node.split(".", 1)[1]
    from app.agent.agents import ROUTE_AGENT

    return ROUTE_AGENT.get(node, "orchestrator")


def new_nonce() -> str:
    return secrets.token_hex(4)


def authorize(node: str, tool: str, *, confirmed_nonce: str | None = None, expected_nonce: str | None = None) -> ToolSpec:
    spec = TOOLS.get(tool)
    if spec is None:
        raise ToolNotAllowed(f"Unknown tool {tool!r}")
    if tool not in NODE_ALLOWLIST.get(node, set()):
        raise ToolNotAllowed(f"Node {node!r} may not call {tool!r}")
    agent = agent_of(node)
    if tool not in AGENT_ALLOWLIST.get(agent, set()):
        raise ToolNotAllowed(f"Agent {agent!r} may not call {tool!r}")
    if spec.destructive or spec.outward:
        if not expected_nonce or not confirmed_nonce or not secrets.compare_digest(confirmed_nonce, expected_nonce):
            raise ToolNotAllowed(f"{tool!r} needs explicit user confirmation")
    return spec
