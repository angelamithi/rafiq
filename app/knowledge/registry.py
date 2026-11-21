"""The official knowledge base: every rule Rafiq relies on, where it comes
from, and how the monitor watches it.

Modes:
- "tokens":    fetch the page and track the *meaningful numbers* on it (AED
               amounts, day/month counts, toll-free numbers, percentages).
               A change means a fee, deadline or number may have moved.
- "reachable": the page must still load (busy home pages change every day,
               so only "is it still there?" is useful).
- "manual":    no stable official page (e.g. a ministerial resolution reported
               in the news); a person re-checks it before `review_by`.

`must_contain`: phrases that must still be on the page; if one disappears,
that's a strong signal the rule changed.

Nothing here is ever changed automatically. The monitor only raises alerts
for a person to review (see README: "Rule Monitor").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.modules.arrival.content import ILOE
from app.modules.departure.content import CLEARANCE_LINKS, EDE, U_AE_PREPARING
from app.modules.help.content import U_AE_LOST_PASSPORT
from app.modules.social.content import DFC, MBRL
from app.modules.stay_legal.content import U_AE_PART_TIME

REVIEW_AFTER_DAYS = 180
U_AE_CRIME = "https://u.ae/en/information-and-services/justice-safety-and-the-law/handling-emergencies/crime"
U_AE_ILOE = "https://u.ae/en/information-and-services/jobs/insurance/unemployment-insurance-scheme"
U_AE_LABOUR_DISPUTE = "https://u.ae/en/information-and-services/jobs/Sector-of-employment/employment-in-the-private-sector/labour-dispute"


@dataclass(frozen=True)
class Fact:
    id: str
    module: str               # graph route the fact belongs to (job_safety, stay_legal, ...)
    summary: str
    url: str | None
    mode: str                 # tokens | reachable | manual
    checked_on: date
    must_contain: tuple[str, ...] = field(default_factory=tuple)

    @property
    def review_by(self) -> date:
        return self.checked_on + timedelta(days=REVIEW_AFTER_DAYS)


D = date(2026, 11, 19)

FACTS: tuple[Fact, ...] = (
    # ---- Help & emergency
    Fact("safety_hotlines", "help", "Al Ameen 8004888, trafficking 8007283, DFWAC 800111, MOI 116111",
         U_AE_CRIME, "tokens", D, ("8004888", "8007283")),
    Fact("lost_passport", "help", "Lost passport: police certificate, embassy, move visa", U_AE_LOST_PASSPORT, "tokens", D,
         ("lost passport certificate",)),
    # ---- Departure planner
    Fact("passport_validity", "departure", "Passport valid 6 months; entry permit valid 2 months", U_AE_PREPARING,
         "tokens", D, ("six months",)),
    Fact("medicine_permit", "stay_legal", "Controlled medicines need an EDE permit", EDE, "reachable", D),
    *(Fact(f"exit_clearance_{c.lower()}", "departure", f"Exit clearance rules: {c}", url, "reachable", D)
      for c, url in CLEARANCE_LINKS.items()),
    # ---- Stay legal
    Fact("part_time_work", "stay_legal", "Second / part-time job needs a permit", U_AE_PART_TIME, "tokens", D),
    Fact("overstay_fine", "stay_legal", "Overstay fine AED 50 per day (ICP)", None, "manual", D),
    # ---- Arrival
    Fact("iloe_fine", "arrival", "ILOE: AED 400 fine for not subscribing", U_AE_ILOE, "tokens", D, ("400",)),
    Fact("iloe_portal", "arrival", "ILOE official subscription site", ILOE, "reachable", D),
    Fact("health_insurance", "arrival", "Employer-paid health insurance in all emirates since Jan 2025", None, "manual", D),
    Fact("shared_housing_dubai", "arrival", "Dubai 2026 shared-housing permits (bed spaces, partitions)", None, "manual", D),
    # ---- Pay & rights
    Fact("labour_complaints", "pay", "MOHRE complaints: 80084, app, website", U_AE_LABOUR_DISPUTE, "tokens", D, ("80084",)),
    Fact("wps_due_date", "pay", "Salary due on the 1st since 1 June 2026 (Resolution 340/2026)", None, "manual", D),
    Fact("gratuity", "pay", "Gratuity 21/30 days' basic pay, 2-year cap", None, "manual", D),
    # ---- Friends & wellbeing
    Fact("support_lines", "social", "800 HOPE, 800 SAKINA, Itma'en 800 506", None, "manual", D),
    Fact("library_membership", "social", "MBRL membership free for residents", f"{MBRL}/membership", "tokens", D),
    Fact("fitness_challenge", "social", "Dubai Fitness Challenge dates", DFC, "reachable", D),
    # ---- Money
    Fact("banks_no_whatsapp", "money", "CBUAE: no WhatsApp for banking since April 2026", None, "manual", D),
)

FACTS_BY_ID = {f.id: f for f in FACTS}
