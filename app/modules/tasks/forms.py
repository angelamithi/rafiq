"""Letters & forms: a few questions, then a ready-to-print letter (PDF).
Rafiq never sends these; the user prints or forwards them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.i18n import fmt_date, t
from app.media.pdf import Section, build_pdf

# Fields every letter can reuse from the toolkit (asked once, remembered).
REMEMBERED = {"employer"}


@dataclass(frozen=True)
class Field:
    key: str
    question: str
    kind: str = "text"     # text | date


@dataclass(frozen=True)
class Form:
    key: str
    fields: tuple[Field, ...]
    tip: str | None = None


_EMPLOYER = Field("employer", "form_q_employer")
_TO = Field("to", "form_q_manager")
_JOB = Field("job", "form_q_job")

FORMS: dict[str, Form] = {
    "passport": Form("passport", (_EMPLOYER, _TO, Field("reason", "form_q_reason")), tip="form_tip_passport"),
    "leave": Form("leave", (_EMPLOYER, _TO, _JOB, Field("from", "form_q_leave_from", "date"),
                            Field("until", "form_q_leave_to", "date"))),
    "salary_cert": Form("salary_cert", (_EMPLOYER, _TO, _JOB, Field("start", "form_q_start"),
                                        Field("purpose", "form_q_purpose"))),
    "resign": Form("resign", (_EMPLOYER, _TO, _JOB, Field("last_day", "form_q_last_day", "date")), tip="form_tip_resign"),
    "payslip": Form("payslip", (_EMPLOYER, _TO, Field("months", "form_q_months"))),
}


def _body(key: str, a: dict[str, str], name: str) -> tuple[str, list[str]]:
    """(subject, paragraphs)"""
    if key == "passport":
        return "Request for the return of my passport", [
            f"I kindly request the return of my passport, which is currently held by the company. I need it {a['reason']}.",
            "I understand that under UAE law a worker's passport is a personal document that the worker keeps. "
            "Please return it to me within 3 working days.",
        ]
    if key == "leave":
        return "Request for annual leave", [
            f"I would like to request my annual leave from {a['from']} to {a['until']}, as provided by my "
            "employment contract and UAE labour law.",
            "Please confirm my leave in writing. I will make sure my work is handed over before I go.",
        ]
    if key == "salary_cert":
        return "Request for a salary certificate", [
            f"I have worked for the company as {a['job']} since {a['start']}. Please issue me a salary certificate "
            f"showing my position, start date and monthly salary. I need it for {a['purpose']}.",
        ]
    if key == "resign":
        return "Resignation notice", [
            f"Please accept this letter as formal notice of my resignation from my position as {a['job']}. "
            f"My last working day will be {a['last_day']}, in line with the notice period in my contract.",
            "I ask for my final settlement, including any unpaid salary, unused leave and end-of-service gratuity, "
            "to be paid as required by UAE law, and for the cancellation of my work permit and visa to be processed.",
        ]
    return "Request for payslips", [
        f"Please provide me with my payslips (or salary statements) for {a['months']}. "
        "I need them for my personal records.",
    ]


def build_letter(key: str, answers: dict[str, str], name: str, today: date, lang: str | None) -> tuple[str, bytes]:
    subject, paras = _body(key, answers, name)
    letter = [
        f"Date: {fmt_date(today, lang)}",
        f"To: {answers.get('to') or 'HR Manager'}\n{answers.get('employer') or ''}",
        f"Subject: {subject}",
        f"Dear {answers.get('to') or 'Sir or Madam'},",
        *paras,
        "Thank you.",
        f"Yours sincerely,\n\n{name}\nSignature: ____________\nEmirates ID / passport no.: ____________",
    ]
    pdf = build_pdf(subject, f"{name} - {answers.get('employer') or ''}", [Section(None, letter)],
                    t("letter_footer", lang))
    return subject, pdf
