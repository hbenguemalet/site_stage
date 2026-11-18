"""Filtres : ville (commune à tous) puis, pour chaque profil, contrat + mots-clés."""

import re
import unicodedata
from dataclasses import dataclass, field

from jobbot.contracts import detect
from jobbot.models import Offer
from jobbot.profiles import Profile


def norm(s: str | None) -> str:
    """Minuscules, sans accents."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return s.lower()


class CityResolver:
    """Trouve la ville (clé de config.yaml) d'une offre à partir de son lieu."""

    def __init__(self, villes: dict):
        self.cities = {
            key: {
                "alias": [norm(a) for a in v.get("alias", [])],
                "deps": [str(d) for d in v.get("departements", [])],
            }
            for key, v in villes.items()
        }

    def city_of(self, offer: Offer) -> str | None:
        loc = norm(offer.location)
        for key, c in self.cities.items():
            if any(re.search(rf"\b{re.escape(a)}\b", loc) for a in c["alias"]):
                return key
        # Formats du type "59 - Villeneuve-d'Ascq", "75 - Paris 9e", "Lille (59)", "Paris - 75"
        for key, c in self.cities.items():
            for d in c["deps"]:
                if re.match(rf"^{d}\b", loc) or re.search(rf"\({d}\)|- {d}$", loc):
                    return key
        return offer.city_key  # sinon : on fait confiance à la ville de la requête source


@dataclass
class Verdict:
    ok: bool
    raison: str = ""
    matched_on: list[str] = field(default_factory=list)
    etoile: bool = False
    contrat: str | None = None
    score: int = 0
    score_detail: list[str] = field(default_factory=list)
    # Texte réellement trouvé, un par entrée de `matched_on` (« Développeur », « SQL », nom de l'alerte)
    matched_text: list[str] = field(default_factory=list)

    @property
    def title_match(self) -> bool:
        return any(m.startswith("titre:") for m in self.matched_on)


# En dessous de ce nombre de caractères, on n'a pas le texte de l'annonce (mail d'alerte) : pas de contrôle
TEXTE_MIN = 200


def evaluate(p: Profile, o: Offer) -> Verdict:
    """Décide si l'offre `o` (ville déjà résolue) convient au profil `p`."""
    contrat = detect(o)
    if o.city_key not in p.villes:
        return Verdict(False, f"ville hors zone ({o.location or '?'})", contrat=contrat)
    if contrat is None and p.contrat_inconnu == "rejeter":
        return Verdict(False, "contrat inconnu", contrat=contrat)
    if contrat is not None and contrat not in p.contrats:
        return Verdict(False, f"contrat {contrat}", contrat=contrat)
    for rx in p.exclure_entreprises:
        if rx.search(o.company or ""):
            return Verdict(False, f"entreprise exclue ({o.company})", contrat=contrat)
    for rx in p.exclure:
        if rx.search(o.title) or rx.search(o.description):
            return Verdict(False, f"exclu par {rx.pattern!r}", contrat=contrat)
    for rx in p.exclure_titre:
        if m := rx.search(o.title):
            return Verdict(False, f"autre domaine dans le titre ({matched_word(m)})", contrat=contrat)
    hits, texts = [], []
    for rx in p.inclure:
        if m := rx.search(o.title):
            hits.append(f"titre:{rx.pattern}")
        elif m := rx.search(o.description):
            hits.append(f"description:{rx.pattern}")
        else:
            continue
        texts.append(matched_word(m))
    if not hits:  # rien dans le titre : l'annonce complète, ou la recherche faite par le site
        if m := next((m for r in p.fiche if (m := r.search(o.fiche))), None):
            hits.append(f"fiche:{m.re.pattern}")
            texts.append(matched_word(m))
        elif o.alert and any(r.search(o.alert) for r in p.alertes_fiche):
            hits.append(f"alerte:{o.alert}")
            texts.append(o.alert)
    if not hits:
        return Verdict(False, "aucun mot-clé", contrat=contrat)
    if p.exiger:  # « data » dans le titre ne suffit pas : il faut une vraie stack dans l'annonce
        annonce = f"{o.description} {o.fiche}"
        if len(annonce.strip()) >= TEXTE_MIN and not any(rx.search(f"{o.title} {annonce}") for rx in p.exiger):
            return Verdict(False, "aucune stack technique dans l'annonce", contrat=contrat)
    etoile = any(rx.search(o.title) or rx.search(o.description) for rx in p.etoile)
    score, detail = compute_score(p, o, hits, etoile, contrat)
    if score < p.score_min:
        return Verdict(False, f"score {score} < {p.score_min} ({', '.join(detail)})", contrat=contrat,
                       score=score, score_detail=detail)
    return Verdict(True, matched_on=hits, etoile=etoile, contrat=contrat, score=score, score_detail=detail,
                   matched_text=texts)


def matched_word(m: re.Match, max_len: int = 40) -> str:
    """Texte trouvé par une regex, étendu aux mots entiers (« d[ée]veloppeu » → « Développeur »)."""
    text, start, end = m.string, m.start(), m.end()
    while start > 0 and text[start - 1].isalnum():
        start -= 1
    while end < len(text) and text[end].isalnum():
        end += 1
    word = " ".join(text[start:end].split()).strip(" -_/.,;:()'\"")
    return word if len(word) <= max_len else word[:max_len - 1] + "…"


# Barème du score (0–100). Les points propres à chaque profil sont dans `bonus` (profiles.yaml).
SCORE_BASE, SCORE_TITRE, SCORE_AUTRE_MOT, SCORE_AUTRES_MAX = 40, 20, 5, 15
SCORE_ETOILE, SCORE_CONTRAT_INCONNU = 15, -10
SCORE_ALERTE_SEULE = -10  # trouvé seulement par la recherche du site : moins sûr


def compute_score(p: Profile, o: Offer, hits: list[str], etoile: bool,
                  contrat: str | None) -> tuple[int, list[str]]:
    """Score de pertinence et son explication, ligne par ligne (« +20 mot-clé dans le titre »)."""
    detail, score = [f"base {SCORE_BASE}"], SCORE_BASE
    if any(h.startswith("titre:") for h in hits):
        score += SCORE_TITRE
        detail.append(f"+{SCORE_TITRE} mot-clé dans le titre")
    if autres := min(SCORE_AUTRES_MAX, SCORE_AUTRE_MOT * (len(hits) - 1)):
        score += autres
        detail.append(f"+{autres} {len(hits) - 1} autre(s) mot(s)-clé(s)")
    if hits and hits[0].startswith("alerte:"):
        score += SCORE_ALERTE_SEULE
        detail.append(f"{SCORE_ALERTE_SEULE} trouvé seulement par l'alerte du site")
    if etoile:
        score += SCORE_ETOILE
        detail.append(f"+{SCORE_ETOILE} ⭐")
    for rx, points in p.bonus:
        if rx.search(o.title) or rx.search(o.description) or rx.search(o.company or ""):
            score += points
            detail.append(f"{points:+d} {rx.pattern}")
    if contrat is None:
        score += SCORE_CONTRAT_INCONNU
        detail.append(f"{SCORE_CONTRAT_INCONNU} contrat inconnu")
    return max(0, min(100, score)), detail
