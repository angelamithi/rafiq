"""Checks every message before it leaves the agent.

Counters:
- Data leakage: blocks secrets, our system-prompt canary, and other people's
  personal data; only the current user's own details may appear.
- Hallucination: legal/official answers must cite an allow-listed official
  source, otherwise the agent says it is not sure and points to an official
  channel instead of guessing.
- Unsafe links: only allow-listed domains may be sent to users.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.security.pii import _PATTERNS

# A random-looking marker embedded in system prompts. If it ever shows up in an
# outgoing message, the model is leaking its instructions.
SYSTEM_PROMPT_CANARY = "RFQ-CANARY-7f3a9c21"

_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),                 # OpenAI/Anthropic style keys
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bEAA[A-Za-z0-9]{30,}"),                   # Meta access tokens
    re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{30,}\b"),          # Telegram bot tokens
    re.compile(r"\b[A-Za-z0-9_-]{43}=\b"),                   # Fernet keys
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._-]{20,}"),
    re.compile(r"(?i)\b(postgres(ql)?|redis)(\+\w+)?://\S+"),  # connection strings
    re.compile(r"\b(WHATSAPP_ACCESS_TOKEN|WHATSAPP_APP_SECRET|TELEGRAM_BOT_TOKEN|FIELD_ENCRYPTION_KEY|ID_HASH_PEPPER|DATABASE_URL|REDIS_URL|[A-Z]+_API_KEY)\b"),
]

ALLOWED_LINK_DOMAINS = {
    "u.ae", "mohre.gov.ae", "icp.gov.ae", "gdrfad.gov.ae", "dubai.ae", "dha.gov.ae",
    "ede.gov.ae", "mohap.gov.ae", "dubailand.gov.ae", "dubaipolice.gov.ae", "rta.ae",
    "khda.gov.ae", "tas-heel.ae", "amer.ae",
    "mfa.go.ke", "kenyaembassy.ae", "nea.go.ke",
    # Module 2: official recruitment-agency registers by home country
    "neaims.go.ke", "dofe.gov.np", "beoe.gov.pk", "bmet.gov.bd", "mglsd.go.ug", "emigrate.gov.in", "dmw.gov.ph",
    # Module 4: pre-departure clearance authorities
    "labour.go.ke",
    # Module 5: arrival (job-loss insurance)
    "iloe.ae",
    # Module 7: free community places and events
    "mbrl.ae", "dubaiculture.gov.ae", "visitdubai.com", "dubaifitnesschallenge.com",
    # Module 8: money
    "centralbank.ae",
    # Module 9: embassies / consulates (each mission's own domain) and the UAE list of missions
    "cgidubai.gov.in", "indembassyuae.gov.in", "dfa.gov.ph", "pakistanconsulatedubai.ae", "bcgdubai.gov.bd",
    "nepalembassy.gov.np", "mofa.go.ug", "mofa.gov.ae",
}

# Public numbers the agent is allowed to share.
ALLOWED_NUMBERS = {"80084", "999", "998", "997", "901", "800", "600590000", "600522222",
                   # Module 7: mental health support lines
                   "8004673", "800725462", "800506", "80046342",
                   # Module 9: safety lines
                   "8004888", "8007283", "800111", "116111"}

_URL = re.compile(r"https?://[^\s)>\]]+|\bwww\.[^\s)>\]]+", re.IGNORECASE)

WHATSAPP_MAX_TEXT = 4096


@dataclass
class OutputCheck:
    text: str
    blocked: bool = False
    reasons: list[str] = field(default_factory=list)


def _domain_allowed(url: str) -> bool:
    host = (urlparse(url if "://" in url else f"https://{url}").hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in ALLOWED_LINK_DOMAINS)


def check_output(text: str, *, user_own_values: set[str] | None = None, require_citation: bool = False) -> OutputCheck:
    """Return a cleaned message, or blocked=True if it must not be sent."""
    reasons: list[str] = []
    own = {v.strip() for v in (user_own_values or set()) if v and v.strip()}

    if SYSTEM_PROMPT_CANARY in text:
        return OutputCheck(text="", blocked=True, reasons=["system_prompt_leak"])
    for pat in _SECRET_PATTERNS:
        if pat.search(text):
            return OutputCheck(text="", blocked=True, reasons=["secret_leak"])

    # Remove links that are not on the allow-list.
    def _link(m: re.Match[str]) -> str:
        # Sentence punctuation right after a link ("...gov.ae, then") is not part of it.
        url = m.group(0)
        trail = len(url) - len(url.rstrip(".,;:!?'\""))
        url, tail = (url[:-trail], url[-trail:]) if trail else (url, "")
        if _domain_allowed(url):
            return url + tail
        reasons.append("link_removed")
        return "[link removed]" + tail

    cleaned = _URL.sub(_link, text)

    # Mask personal data that is not the user's own (e.g. another person's phone).
    for label, pat in _PATTERNS:
        def _pii(m: re.Match[str], label: str = label) -> str:
            value = m.group(0).strip()
            digits = re.sub(r"\D", "", value)
            if value in own or digits in ALLOWED_NUMBERS or any(value in o or o in value for o in own):
                return m.group(0)
            reasons.append(f"masked_{label.lower()}")
            return f"[{label}]"

        cleaned = pat.sub(_pii, cleaned)

    if require_citation:
        cited = [u for u in _URL.findall(cleaned) if _domain_allowed(u)]
        if not cited:
            return OutputCheck(text="", blocked=True, reasons=reasons + ["uncited_legal_claim"])

    if len(cleaned) > WHATSAPP_MAX_TEXT:
        cleaned = cleaned[: WHATSAPP_MAX_TEXT - 1] + "…"
        reasons.append("truncated")
    return OutputCheck(text=cleaned, reasons=reasons)
