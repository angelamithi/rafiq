"""PII masking.

Used in three places:
- before any text is sent to an external AI model,
- in logs (via a logging filter),
- by the output guard, so the agent never echoes another person's data.

Rule-based so it works offline. Microsoft Presidio can be plugged in later for
names and addresses (see README).
"""

from __future__ import annotations

import logging
import re

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("EMIRATES_ID", re.compile(r"\b784[- ]?\d{4}[- ]?\d{7}[- ]?\d\b")),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    # 10-15 digits with optional separators; dates like 2026-12-15 (8 digits) are not phones.
    ("PHONE", re.compile(r"(?<![\w/])\+?(?:\d[\s\-()]{0,2}){9,14}\d\b")),
    ("PASSPORT", re.compile(r"\b[A-Z]{1,2}\d{6,8}\b")),
    ("LONG_NUMBER", re.compile(r"\b\d{7,}\b")),
]


def mask(text: str | None) -> str:
    if not text:
        return text or ""
    out = text
    for label, pattern in _PATTERNS:
        out = pattern.sub(f"[{label}]", out)
    return out


def contains_pii(text: str | None) -> list[str]:
    if not text:
        return []
    return [label for label, pattern in _PATTERNS if pattern.search(text)]


class PIIMaskingFilter(logging.Filter):
    """Masks PII in every log record before it is written."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover
            return True
        record.msg = mask(msg)
        record.args = ()
        return True
