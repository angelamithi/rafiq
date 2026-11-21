"""Official sources used by the Job Safety module. Only links verified to be
the authority's own site are listed; the output guard also allow-lists them."""

from __future__ import annotations

MOHRE = "https://www.mohre.gov.ae"  # UAE Ministry of Human Resources and Emiratisation

# Where a worker can check that a recruitment agency is licensed, by home country.
AGENCY_CHECK: dict[str, tuple[str, str]] = {
    "Kenya": ("National Employment Authority (NEA) agency list", "https://neaims.go.ke/EmploymentAgencyList.aspx"),
    "Nepal": ("Department of Foreign Employment agency list", "https://dofe.gov.np/Recruting-Agences.aspx"),
    "Pakistan": ("Bureau of Emigration & Overseas Employment list of OEPs", "https://beoe.gov.pk/list-of-oeps"),
    "Bangladesh": ("Bureau of Manpower, Employment and Training (BMET)", "https://www.bmet.gov.bd"),
    "Uganda": ("Ministry of Gender, Labour and Social Development", "https://mglsd.go.ug"),
    "India": ("eMigrate portal (Ministry of External Affairs)", "https://www.emigrate.gov.in"),
    "Philippines": ("Department of Migrant Workers", "https://www.dmw.gov.ph"),
}

OFFICIAL_DOMAINS = {
    "mohre.gov.ae", "neaims.go.ke", "dofe.gov.np", "beoe.gov.pk", "bmet.gov.bd",
    "mglsd.go.ug", "emigrate.gov.in", "dmw.gov.ph",
}


def agency_check_for(country: str | None) -> tuple[str, str] | None:
    return AGENCY_CHECK.get(country or "")
