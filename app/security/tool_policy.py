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
    "pay": {"get_own_profile", "get_own_pay", "update_own_pay", "draft_complaint"},
    "social": {"get_own_profile", "update_own_wellbeing_pref"},
    "money": {"get_own_profile"},   # read-only: home country for the currency name; stores nothing
    "help": {"get_own_profile"},    # read-only: home country, to show the right embassy
    "fallback": set(),
}


def new_nonce() -> str:
    return secrets.token_hex(4)


def authorize(node: str, tool: str, *, confirmed_nonce: str | None = None, expected_nonce: str | None = None) -> ToolSpec:
    spec = TOOLS.get(tool)
    if spec is None:
        raise ToolNotAllowed(f"Unknown tool {tool!r}")
    if tool not in NODE_ALLOWLIST.get(node, set()):
        raise ToolNotAllowed(f"Node {node!r} may not call {tool!r}")
    if spec.destructive or spec.outward:
        if not expected_nonce or not confirmed_nonce or not secrets.compare_digest(confirmed_nonce, expected_nonce):
            raise ToolNotAllowed(f"{tool!r} needs explicit user confirmation")
    return spec
