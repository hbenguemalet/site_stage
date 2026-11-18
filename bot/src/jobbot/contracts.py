"""Détection du type de contrat d'une offre."""

import re

from jobbot.models import Offer

CONTRATS = {"cdi", "cdd", "stage", "alternance", "freelance", "interim"}

# Valeurs fournies par les sources (HelloWork : « CDI », « Stage », « Indépendant »…)
CHAMP_SOURCE = {
    "cdi": "cdi", "cdd": "cdd", "stage": "stage", "alternance": "alternance",
    "apprentissage": "alternance", "independant": "freelance", "indépendant": "freelance",
    "freelance": "freelance", "interim": "interim", "intérim": "interim",
    # pages carrières (Greenhouse, Lever, Ashby, Workable, Recruitee, SmartRecruiters)
    "intern": "stage", "internship": "stage", "stagiaire": "stage",
    "apprenticeship": "alternance", "apprentice": "alternance", "work-study": "alternance",
    "permanent": "cdi", "fulltime_permanent": "cdi", "temporary": "cdd", "fixed-term": "cdd",
    "fulltime_fixed_term": "cdd", "contract": "freelance",
}

# Le titre prime sur le champ de la source pour stage / alternance : HelloWork classe
# parfois « Data Platform Intern » en CDI.
TITRE_PRIORITAIRE = [
    ("alternance", re.compile(r"\balternan(ce|t)|\bapprenti|\bapprentissage|\bcontrat pro", re.IGNORECASE)),
    ("stage", re.compile(r"\bstage\b|\bstagiaire|\bintern\b|\binternship", re.IGNORECASE)),
]
TITRE_SECONDAIRE = [
    ("cdd", re.compile(r"\bcdd\b", re.IGNORECASE)),
    ("cdi", re.compile(r"\bcdi\b", re.IGNORECASE)),
    ("freelance", re.compile(r"\bfreelance\b|\bind[ée]pendant|\bportage\b|\bmission courte\b", re.IGNORECASE)),
    ("interim", re.compile(r"\bint[ée]rim", re.IGNORECASE)),
]


def detect(o: Offer) -> str | None:
    for nom, rx in TITRE_PRIORITAIRE:
        if rx.search(o.title):
            return nom
    if o.contract and (c := CHAMP_SOURCE.get(o.contract.strip().lower())):
        return c
    for nom, rx in TITRE_SECONDAIRE:
        if rx.search(o.title):
            return nom
    return None
