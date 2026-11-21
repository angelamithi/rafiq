"""Detection of prompt injection and jailbreak attempts.

Two layers:
1. Fast rule-based scoring (always on, works offline; English plus common Swahili attack phrases).
2. Optional LLM classifier (app/agent/llm.py) for messages the rules flag as
   borderline. It can only answer from a fixed set of labels, so it cannot be
   steered into doing anything else.

The same detector scans *untrusted external content* (documents, web pages,
forwarded messages) for indirect prompt injection.

Rules are tuned so ordinary job seekers are not blocked: "I'm a database
developer", "how do I use the visa app?" or "ignore the agent who asked me for
money" must pass. Tests in tests/test_injection.py pin both sides.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Zero-width, bidi-override and other invisible characters used to hide text.
INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤﻿­]")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_ROLE_WORDS = r"(instruction|instructions|rules|prompt|prompts|guidelines|directions|programming|training)"

# (pattern, weight, category). Patterns run on normalised lower-case text.
_RULES: list[tuple[re.Pattern[str], int, str]] = [
    # --- Instruction override (direct prompt injection) ---
    # Only AI-directed targets ("your/previous/system instructions"), so "ignore the
    # contract rules" (a real worker question) is not blocked.
    (re.compile(r"\b(ignore|disregard|forget|override|bypass)\b\s+(all\s+)?(of\s+)?(your|my|these|any|previous|prior|above|earlier|system|initial|original)?\s*(previous|prior|above|earlier|initial|original|system)?\s*" + _ROLE_WORDS + r"\b"), 6, "prompt_injection"),
    (re.compile(r"\b(ignore|disregard|forget)\b\s+(everything|all)\s+(above|before|you were told)\b"), 6, "prompt_injection"),
    (re.compile(r"\bnew (instructions|rules|system prompt)\b"), 4, "prompt_injection"),
    (re.compile(r"\b(system|developer|hidden|initial)\s*(prompt|message|instructions?)\b"), 3, "prompt_injection"),
    (re.compile(r"(^|\n)\s*(system|assistant|developer)\s*:"), 4, "prompt_injection"),
    (re.compile(r"<\s*/?\s*(system|instructions?|im_start|im_end|tool|function)[^>]*>"), 6, "prompt_injection"),
    (re.compile(r"\[(system|inst)\]|\{\{.*system.*\}\}"), 4, "prompt_injection"),
    # Swahili: "puuza maagizo", "sahau maelekezo yako"
    (re.compile(r"\b(puuza|sahau|acha)\b.{0,30}\b(maagizo|maelekezo|sheria zako|kanuni zako)\b"), 6, "prompt_injection"),
    # --- Jailbreak / persona hijack ---
    (re.compile(r"\b(jailbreak|jailbroken|dan mode|developer mode|god mode|unfiltered mode|uncensored|no restrictions|without (any )?restrictions|no limits)\b"), 6, "jailbreak"),
    (re.compile(r"\b(you are|you're|act as|pretend (to be|you are)|roleplay as|from now on you)\b.{0,40}\b(no longer|not bound|free from|evil|hacker|unrestricted|another ai|a different ai|no rules|no limits)\b"), 6, "jailbreak"),
    (re.compile(r"\bhypothetically\b.{0,60}\b(no rules|ignore|bypass)\b"), 4, "jailbreak"),
    # --- Data exfiltration / leakage ---
    (re.compile(r"\b(reveal|show|print|repeat|output|tell me|give me|leak|dump|share)\b.{0,40}\b(system prompt|your prompt|your instructions|hidden instructions|secret|api key|access token|password|credentials|environment variables?|\.env|config file)\b"), 6, "data_exfiltration"),
    (re.compile(r"\b(other|another|all|every) (users?|people|customers?|members?)('s)?\b.{0,40}\b(data|phone|numbers?|details|profiles?|messages?|visas?|names?)\b"), 6, "data_exfiltration"),
    (re.compile(r"\b(phone|numbers?|data|details|profiles?|visas?|names?|messages?|records?)\b.{0,40}\b(of|for|from|about|belonging to)\s+(all\s+)?(the\s+)?(other|all|every|another)\s+(users?|people|customers?|members?)\b"), 6, "data_exfiltration"),
    (re.compile(r"\b(your|rafiq'?s|the bot'?s|the system'?s)\s+(api keys?|access tokens?|secret keys?|credentials|env file|environment variables?|passwords?)\b"), 6, "data_exfiltration"),
    (re.compile(r"(^|[\s'\"(])\.env\b"), 6, "data_exfiltration"),
    (re.compile(r"(select \* from|drop table|union select|insert into|;\s*--)"), 6, "data_exfiltration"),
    (re.compile(r"\b(your|the bot'?s|rafiq'?s) (database|server|backend|source code)\b"), 3, "data_exfiltration"),
    # --- Privilege escalation (claims of authority over the bot) ---
    (re.compile(r"\b(i am|i'm|im|this is)\b.{0,12}\b(your|rafiq'?s)\b.{0,12}\b(admin|administrator|developer|owner|creator|moderator|operator)\b"), 5, "privilege_escalation"),
    (re.compile(r"\b(admin|administrator|developer|owner|creator|operator)s? of (rafiq|this bot|this app|this system|the bot|this ai|you)\b"), 5, "privilege_escalation"),
    (re.compile(r"\b(i am|i'm|this is)\b.{0,20}\bfrom (anthropic|openai|meta|whatsapp|the dubai chamber)\b"), 4, "privilege_escalation"),
    (re.compile(r"\b(admin|sudo|root|superuser|debug|maintenance) (mode|access|command|panel|override)\b"), 5, "privilege_escalation"),
    (re.compile(r"\b(grant|give) me\b.{0,20}\b(admin|root|full access|permissions?|privileges?)\b"), 5, "privilege_escalation"),
    # --- Tool misuse ---
    (re.compile(r"\b(call|run|execute|invoke|trigger)\b.{0,20}\b(the )?(tool|function|command|shell|script|api)\b"), 3, "tool_misuse"),
    (re.compile(r"\b(delete|erase|wipe|remove)\b.{0,30}\b(all|every|other|everyone'?s?)\b.{0,20}\b(users?|data|records|accounts?|profiles?)\b"), 6, "tool_misuse"),
    (re.compile(r"\b(send|message|text|email|forward|broadcast)\b.{0,30}\b(to\s+)?(all|every|each)\s+(of\s+)?(your\s+|the\s+)?(users?|contacts|customers?|members?)\b"), 6, "tool_misuse"),
    (re.compile(r"\b(send|message|text|email|forward)\b.{0,30}\b(this number|\+?\d{9,})\b"), 3, "tool_misuse"),
]

_BASE64_BLOB = re.compile(r"[A-Za-z0-9+/]{120,}={0,2}")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


@dataclass
class GuardResult:
    verdict: str = "allow"  # allow | flag | block
    score: int = 0
    categories: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.verdict == "block"


def clean_input(text: str) -> str:
    """Normalise user input before it is processed or stored: NFKC, no
    invisible or control characters, trimmed."""
    text = unicodedata.normalize("NFKC", text or "")
    text = INVISIBLE.sub("", text)
    text = CONTROL.sub("", text)
    return text.strip()


def normalise(text: str) -> str:
    """Aggressive normalisation for *scanning only* (never shown to users)."""
    text = clean_input(text).lower()
    # "i g n o r e" -> "ignore"
    text = re.sub(r"\b(?:[a-z][\s._-]){2,}[a-z]\b", lambda m: re.sub(r"[\s._-]", "", m.group(0)), text)
    # leetspeak only inside words that contain letters (keeps phone numbers intact)
    text = re.sub(r"\b(?=\w*[a-z])\w+\b", lambda m: m.group(0).translate(_LEET), text)
    return re.sub(r"\s+", " ", text)


def scan(text: str, *, block_threshold: int = 6, flag_threshold: int = 3) -> GuardResult:
    """Score a piece of text. Higher score = more likely an attack."""
    if not text:
        return GuardResult()
    norm = normalise(text)
    score = 0
    cats: list[str] = []
    for pattern, weight, cat in _RULES:
        if pattern.search(norm):
            score += weight
            if cat not in cats:
                cats.append(cat)
    if _BASE64_BLOB.search(text):
        score += 3
        cats.append("obfuscation")
    if INVISIBLE.search(text):
        score += 2
        cats.append("obfuscation")
    verdict = "block" if score >= block_threshold else "flag" if score >= flag_threshold else "allow"
    return GuardResult(verdict=verdict, score=score, categories=cats)
