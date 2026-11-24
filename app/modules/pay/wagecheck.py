"""Wage check: the flagship workflow of the Employment protection agent.

One message in ("I was supposed to get AED 1,800 but only got AED 1,000"),
a reviewed complaint and an evidence pack out. Each step is a tool the agent
is allowed to use, and every step that matters waits for the worker:

  1. Understand  - pick the agreed and received amounts out of her words (rules,
                   not the AI, so a message can't "decide" the numbers);
                   ask if anything is missing.
  2. Cross-check - against the contract salary she saved, and the pay rule for
                   her worker category (private sector vs domestic worker).
  3. Calculate   - the potential shortfall for the month, and any pattern.
  4. Ask         - was a deduction agreed in writing? (her answer, not a guess)
  5. Prepare     - on her approval: a case file in Rafiq (not an official case)
                   and the Arabic + English evidence pack.
  6. Draft       - on her approval: the complaint text, for her to review and
                   file herself at MOHRE. Rafiq never sends anything.
  7. Follow up   - when she says she filed: her reference number and reminders
                   (the case manager's follow-ups).

A shortfall is always called *potential*: it comes from her own records, and
only MOHRE or a court decides what is legally owed.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.channels.base import Button, Outgoing
from app.db import repo
from app.i18n import S, t
from app.modules.pay import amounts as am

_AMT = re.compile(r"(?:aed|dhs?|dirhams?)?\s*(\d{1,3}(?:,\d{3})+|\d{3,6})(?:\.\d{1,2})?\s*(?:aed|dhs?|dirhams?)?", re.I)
_PAY_WORD = re.compile(r"\b(salary|salaries|pay|paid|wage|wages)\b", re.I)
_SHORT_WORD = re.compile(r"\b(only|less|short|instead|half|cut|deducted|not paid|didn'?t pay|did not pay|"
                         r"no salary|haven'?t been paid|have not been paid|wasn'?t paid|was not paid)\b", re.I)
_AGREED_WORD = re.compile(r"\b(supposed|agreed|contract|promised|should|meant to|salary is|offer)\b", re.I)
_ZERO = re.compile(r"\b(not paid|didn'?t pay|did not pay|no salary|haven'?t been paid|have not been paid|wasn'?t paid|"
                   r"was not paid|nothing)\b", re.I)
_THIS_MONTH = re.compile(r"\bthis month\b", re.I)

STRINGS: dict[str, dict[str, str]] = {
    "wc_need_both": {"en": (
        "🔎 *Wage check*\nI can work out what may be owed. Send both amounts in one message, e.g. "
        "*contract 1800, received 1000*.")},
    "wc_result": {"en": (
        "🔎 *Wage check · {month}*\n"
        "• Agreed salary: *AED {agreed}*{source}\n"
        "• Received: *AED {got}*\n"
        "• Potential shortfall: *AED {short}*\n\n"
        "{rule}\n\n"
        "_This comes from what you told me. It isn't a legal decision: MOHRE or a court decides what is owed._")},
    "wc_src_contract": {"en": " (your saved contract)"},
    "wc_src_said": {"en": " (as you told me)"},
    "wc_src_differs": {"en": " (you said; your saved contract says AED {saved})"},
    "wc_rule_private": {"en": "Rule (private sector): last month's salary is due on the 1st, through WPS; MOHRE can act from day 2."},
    "wc_rule_domestic": {"en": "Rule (domestic workers): salary is due within 10 working days of the date in your contract."},
    "wc_ask_deduction": {"en": "One question first: did you agree *in writing* to a deduction this month (an advance or a loan)?"},
    "wc_none": {"en": "✅ No shortfall: you received at least your agreed salary for {month}. I've saved it."},
    "wc_agreed": {"en": (
        "Then this month may not be owed. Keep a copy of what you signed. If the deduction seems too big, "
        "MOHRE's free line *80084* can advise.")},
    "wc_owed": {"en": "📌 Saved. Potential shortfall so far: *AED {total}*{streak}."},
    "wc_streak": {"en": ", and {n} months in a row"},
    "wc_next": {"en": "Here's what I can do next. Nothing happens unless you tap:"},
    "wc_pack_done": {"en": (
        "📂 Case file saved in Rafiq (this is your record, not an official complaint). Your evidence pack is attached: "
        "Arabic first for MOHRE, then English.\n\nAdd proof: save photos of your contract and payslips or bank transfers in "
        "*My documents* (encrypted).")},
    "wc_draft_head": {"en": "✍️ *Draft for you to review.* Nothing has been sent. Change anything that isn't right, then file it yourself."},
    "wc_draft_tail": {"en": (
        "*Where to file:* the MOHRE app or website, or call *80084* (free). Domestic workers use the domestic-worker "
        "complaint service. Bring your evidence pack.\nTap *I've filed it* after you file, and I'll keep track and remind you.")},
    "btn_wc_pack": {"en": "Build evidence pack"},
    "btn_wc_draft": {"en": "Draft complaint"},
    "btn_wc_filed": {"en": "I've filed it"},
    "btn_wc_no": {"en": "No"},
    "btn_wc_yes": {"en": "Yes, I agreed"},
    "btn_wc_unsure": {"en": "Not sure"},
    "btn_not_now": {"en": "Not now"},
}
S.update(STRINGS)


def looks_like_shortfall(text: str) -> bool:
    """A typed or spoken message about being paid less than agreed (or not at all)."""
    s = text or ""
    if len(s) < 15 or not _PAY_WORD.search(s) or not _SHORT_WORD.search(s):
        return False
    return bool(_AMT.search(s)) or bool(_ZERO.search(s)) or bool(_AGREED_WORD.search(s))


def _amounts(text: str) -> list[int]:
    out = []
    for m in _AMT.finditer(text or ""):
        v = int(m.group(1).replace(",", ""))
        if am.MIN_SALARY <= v <= am.MAX_SALARY:
            out.append(v)
    return out


def parse(text: str, saved_salary: int | None) -> tuple[int | None, int | None, str]:
    """(agreed, received, source of agreed). Rules only."""
    nums = _amounts(text)
    zero = bool(_ZERO.search(text or ""))
    if len(nums) >= 2:
        return max(nums[:2]), min(nums[:2]), "said"
    if len(nums) == 1:
        v = nums[0]
        if zero:
            return v, 0, "said"                       # "my salary of 1800 was not paid"
        if saved_salary and v < saved_salary:
            return saved_salary, v, "contract"        # "I only got 1000" + saved contract salary
        return None, v, "said"
    if zero and saved_salary:
        return saved_salary, 0, "contract"
    return None, None, "said"


def month_for(text: str, today: date) -> str:
    if _THIS_MONTH.search(text or ""):
        return f"{today.year:04d}-{today.month:02d}"
    y, m = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{y:04d}-{m:02d}"


def start(user, text: str, today: date, lang: str | None, month_label: Any, domestic: bool) -> tuple[list[Outgoing], dict | None]:  # type: ignore[no-untyped-def]
    """Steps 1-3. Returns the messages and the draft to keep (None if nothing to keep)."""
    saved = am.contract_salary(user)
    agreed, got, src = parse(text, saved)
    if agreed is None or got is None:
        return [Outgoing(text=t("wc_need_both", lang))], None
    month = month_for(text, today)
    if got >= agreed:
        am.record_received(user, month, got)
        return [Outgoing(text=t("wc_none", lang, month=month_label(month, lang)))], None
    if saved is None:
        repo.update_toolkit(user, salary=agreed)
    source = (t("wc_src_contract", lang) if src == "contract" else
              t("wc_src_differs", lang, saved=f"{saved:,}") if saved and saved != agreed else t("wc_src_said", lang))
    rule = t("wc_rule_domestic" if domestic else "wc_rule_private", lang)
    msgs = [Outgoing(text=t("wc_result", lang, month=month_label(month, lang), agreed=f"{agreed:,}", got=f"{got:,}",
                            short=f"{agreed - got:,}", source=source, rule=rule)),
            Outgoing(text=t("wc_ask_deduction", lang),
                     buttons=[Button(id="pay:wc_ded:no", title=t("btn_wc_no", lang)),
                              Button(id="pay:wc_ded:yes", title=t("btn_wc_yes", lang)),
                              Button(id="pay:wc_ded:unsure", title=t("btn_wc_unsure", lang))])]
    return msgs, {"month": month, "agreed": agreed, "got": got}


def after_deduction(user, draft: dict, answer: str, lang: str | None) -> list[Outgoing]:  # type: ignore[no-untyped-def]
    """Step 4: her answer decides whether it counts as owed."""
    month, got = draft["month"], int(draft["got"])
    if not am.contract_salary(user):
        repo.update_toolkit(user, salary=int(draft["agreed"]))
    am.record_received(user, month, got)
    am.mark_agreed(user, month, answer == "yes")
    if answer == "yes":
        return [Outgoing(text=t("wc_agreed", lang), buttons=[Button(id="menu:pay", title="Pay & Rights")])]
    _, total = am.gaps(user)
    n = am.shortfall_streak(user)
    return [Outgoing(text=t("wc_owed", lang, total=f"{total:,}", streak=t("wc_streak", lang, n=n) if n >= 2 else "")),
            Outgoing(text=t("wc_next", lang), buttons=[Button(id="pay:wc_pack", title=t("btn_wc_pack", lang)),
                                                      Button(id="pay:wc_draft", title=t("btn_wc_draft", lang)),
                                                      Button(id="menu:pay", title=t("btn_not_now", lang))])]
