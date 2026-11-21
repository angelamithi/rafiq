"""Medicine lookup for travellers to the UAE.

Deliberately conservative:
- CONTROLLED lists active ingredients in groups the UAE controls (opioid
  painkillers, benzodiazepines, sleep medicines, ADHD stimulants, tramadol,
  pregabalin, gabapentin, codeine), plus common brand names for them.
- COMMON lists everyday medicines that published guidance says are NOT on
  the controlled list (paracetamol, ibuprofen, antihistamines, insulin,
  blood-pressure tablets, antibiotics such as ciprofloxacin).
- Anything else is "unknown" and the user is sent to the official list.
  Rafiq never says a medicine is allowed just because it isn't listed here.

Medicine names are health data: they are matched in memory and never stored.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ingredient -> group (shown to the user)
CONTROLLED: dict[str, str] = {
    # opioid painkillers
    "codeine": "opioid painkiller", "tramadol": "opioid painkiller", "oxycodone": "opioid painkiller",
    "morphine": "opioid painkiller", "fentanyl": "opioid painkiller", "hydrocodone": "opioid painkiller",
    "methadone": "opioid painkiller", "buprenorphine": "opioid painkiller", "tapentadol": "opioid painkiller",
    "dihydrocodeine": "opioid painkiller", "pethidine": "opioid painkiller",
    # benzodiazepines
    "alprazolam": "benzodiazepine", "diazepam": "benzodiazepine", "lorazepam": "benzodiazepine",
    "clonazepam": "benzodiazepine", "bromazepam": "benzodiazepine", "temazepam": "benzodiazepine",
    "midazolam": "benzodiazepine", "chlordiazepoxide": "benzodiazepine", "nitrazepam": "benzodiazepine",
    # sleep medicines
    "zolpidem": "sleep medicine", "zopiclone": "sleep medicine", "eszopiclone": "sleep medicine", "zaleplon": "sleep medicine",
    # ADHD stimulants
    "methylphenidate": "ADHD stimulant", "amphetamine": "ADHD stimulant", "dextroamphetamine": "ADHD stimulant",
    "lisdexamfetamine": "ADHD stimulant", "dexmethylphenidate": "ADHD stimulant",
    # nerve-pain medicines
    "pregabalin": "controlled nerve-pain medicine", "gabapentin": "controlled nerve-pain medicine",
}

BRANDS: dict[str, str] = {
    "tramal": "tramadol", "ultram": "tramadol", "tramacet": "tramadol",
    "oxycontin": "oxycodone", "percocet": "oxycodone",
    "solpadeine": "codeine", "tylenol 3": "codeine", "co-codamol": "codeine", "panadeine": "codeine",
    "xanax": "alprazolam", "valium": "diazepam", "ativan": "lorazepam", "rivotril": "clonazepam",
    "klonopin": "clonazepam", "lexotan": "bromazepam",
    "ambien": "zolpidem", "stilnox": "zolpidem", "imovane": "zopiclone",
    "ritalin": "methylphenidate", "concerta": "methylphenidate", "adderall": "amphetamine",
    "vyvanse": "lisdexamfetamine", "elvanse": "lisdexamfetamine",
    "lyrica": "pregabalin", "neurontin": "gabapentin",
}

BANNED = ("cannabis", "cbd", "cannabidiol", "marijuana", "thc", "hemp oil", "weed")

# ingredient -> shown name; brand aliases map to the ingredient
COMMON: dict[str, str] = {
    "paracetamol": "paracetamol", "acetaminophen": "paracetamol", "panadol": "paracetamol", "calpol": "paracetamol",
    "ibuprofen": "ibuprofen", "brufen": "ibuprofen", "advil": "ibuprofen", "nurofen": "ibuprofen",
    "cetirizine": "cetirizine (antihistamine)", "zyrtec": "cetirizine (antihistamine)",
    "loratadine": "loratadine (antihistamine)", "claritin": "loratadine (antihistamine)",
    "fexofenadine": "fexofenadine (antihistamine)", "telfast": "fexofenadine (antihistamine)",
    "insulin": "insulin",
    "amlodipine": "amlodipine (blood pressure)", "losartan": "losartan (blood pressure)",
    "lisinopril": "lisinopril (blood pressure)", "enalapril": "enalapril (blood pressure)",
    "ciprofloxacin": "ciprofloxacin (antibiotic)", "amoxicillin": "amoxicillin (antibiotic)",
    "augmentin": "amoxicillin (antibiotic)", "azithromycin": "azithromycin (antibiotic)",
    "metformin": "metformin (diabetes)",
}


@dataclass(frozen=True)
class MedicineMatch:
    status: str            # controlled | banned | common | unknown
    name: str              # what the user wrote / what was found
    ingredient: str = ""
    group: str = ""


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", t)).strip()


def _has(term: str, text: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", text) is not None


def find_medicines(text: str) -> list[MedicineMatch]:
    """All medicines recognised in a piece of text (typed name or OCR of a box),
    most serious first. Empty if none recognised."""
    t = _norm(text)
    found: dict[str, MedicineMatch] = {}
    for term in BANNED:
        if _has(term, t):
            found.setdefault("banned", MedicineMatch("banned", term.upper() if term in ("cbd", "thc") else term.title()))
    for ing, group in CONTROLLED.items():
        if _has(ing, t):
            found.setdefault(ing, MedicineMatch("controlled", ing.title(), ing, group))
    for brand, ing in BRANDS.items():
        if _has(brand, t):
            found.setdefault(ing, MedicineMatch("controlled", brand.title(), ing, CONTROLLED[ing]))
    if not any(m.status in ("banned", "controlled") for m in found.values()):
        for alias, shown in COMMON.items():
            if _has(alias, t):
                found.setdefault(shown, MedicineMatch("common", alias.title(), shown))
    order = {"banned": 0, "controlled": 1, "common": 2}
    return sorted(found.values(), key=lambda m: order[m.status])


def check_medicine(text: str) -> MedicineMatch:
    matches = find_medicines(text)
    if matches:
        return matches[0]
    shown = re.sub(r"\s+", " ", (text or "").strip())[:40] or "That medicine"
    return MedicineMatch("unknown", shown)


def mentions_medicine(text: str) -> bool:
    """For routing free text like "can I bring tramadol?" to the checker."""
    return bool(find_medicines(text))
