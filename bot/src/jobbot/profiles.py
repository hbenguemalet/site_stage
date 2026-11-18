"""Profils de recherche (profiles.yaml) : chargement + validation stricte."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from jobbot.contracts import CONTRATS

CHAMPS = {"id", "nom", "description", "actif", "villes", "contrats", "contrat_inconnu",
          "inclure", "exclure", "exclure_entreprises", "etoile", "webhook", "bonus", "score_min",
          "recap_a_partir_de", "fiche", "alertes_fiche", "avatar", "exiger", "exclure_titre"}


@dataclass
class Profile:
    id: str
    nom: str
    villes: list[str]
    contrats: set[str]
    inclure: list[re.Pattern]
    exclure: list[re.Pattern] = field(default_factory=list)
    exclure_entreprises: list[re.Pattern] = field(default_factory=list)
    etoile: list[re.Pattern] = field(default_factory=list)
    contrat_inconnu: str = "garder"
    bonus: list[tuple[re.Pattern, int]] = field(default_factory=list)
    score_min: int = 0
    recap_a_partir_de: int | None = None  # None : réglage global de config.yaml
    # Mots-clés cherchés dans l'annonce complète (sources API) quand le titre n'a rien donné
    fiche: list[re.Pattern] = field(default_factory=list)
    # Alertes e-mail dont la recherche (faite par le site dans toute l'annonce) suffit
    alertes_fiche: list[re.Pattern] = field(default_factory=list)
    # Stack technique obligatoire dans l'annonce (au moins une regex) quand son texte est disponible
    exiger: list[re.Pattern] = field(default_factory=list)
    # Rejette si le TITRE contient un autre domaine (compta, RH…) ; ne regarde jamais la description
    exclure_titre: list[re.Pattern] = field(default_factory=list)
    webhook: str = ""
    avatar: str = ""  # URL https d'une image : avatar des messages Discord du profil
    description: str = ""
    actif: bool = True


def _regex(pid: str, champ: str, motifs) -> list[re.Pattern]:
    out = []
    for m in motifs or []:
        try:
            out.append(re.compile(m, re.IGNORECASE | re.DOTALL))
        except re.error as e:
            raise SystemExit(f"profiles.yaml, profil « {pid} », {champ} : regex invalide {m!r} ({e})")
    return out


def parse(data: dict, villes_connues: set[str]) -> list[Profile]:
    erreurs, profils, ids = [], [], set()
    for i, p in enumerate((data or {}).get("profils") or []):
        pid = p.get("id") or f"#{i + 1}"
        if inconnus := set(p) - CHAMPS:
            erreurs.append(f"{pid} : champ(s) inconnu(s) {sorted(inconnus)}")
        for champ in ("id", "nom", "villes", "contrats", "inclure", "webhook"):
            if not p.get(champ):
                erreurs.append(f"{pid} : champ « {champ} » obligatoire")
        if pid in ids:
            erreurs.append(f"{pid} : id en double")
        ids.add(pid)
        if bad := set(p.get("villes") or []) - villes_connues:
            erreurs.append(f"{pid} : ville(s) absente(s) de config.yaml {sorted(bad)}")
        contrats = {c.lower() for c in p.get("contrats") or []}
        if bad := contrats - CONTRATS:
            erreurs.append(f"{pid} : contrat(s) inconnu(s) {sorted(bad)} (possibles : {sorted(CONTRATS)})")
        ci = p.get("contrat_inconnu", "garder")
        if ci not in ("garder", "rejeter"):
            erreurs.append(f"{pid} : contrat_inconnu doit valoir garder ou rejeter")
        bonus = p.get("bonus") or {}
        if not isinstance(bonus, dict) or not all(isinstance(v, int) for v in bonus.values()):
            erreurs.append(f"{pid} : bonus doit être une liste « regex: points » (points entiers)")
            bonus = {}
        score_min = p.get("score_min", 0)
        if not isinstance(score_min, int) or not 0 <= score_min <= 100:
            erreurs.append(f"{pid} : score_min doit être un entier entre 0 et 100")
        recap = p.get("recap_a_partir_de")
        if recap is not None and (not isinstance(recap, int) or recap < 1):
            erreurs.append(f"{pid} : recap_a_partir_de doit être un entier ≥ 1")
        avatar = p.get("avatar") or ""
        if avatar and not (isinstance(avatar, str) and avatar.startswith("https://")):
            erreurs.append(f"{pid} : avatar doit être une URL https://")
        if erreurs:
            continue
        profils.append(Profile(
            id=pid, nom=p["nom"], villes=list(p["villes"]), contrats=contrats,
            inclure=_regex(pid, "inclure", p["inclure"]),
            exclure=_regex(pid, "exclure", p.get("exclure")),
            exclure_entreprises=_regex(pid, "exclure_entreprises", p.get("exclure_entreprises")),
            etoile=_regex(pid, "etoile", p.get("etoile")),
            contrat_inconnu=ci, webhook=p["webhook"], avatar=avatar,
            bonus=list(zip(_regex(pid, "bonus", list(bonus)), bonus.values(), strict=True)),
            score_min=score_min, recap_a_partir_de=recap,
            fiche=_regex(pid, "fiche", p.get("fiche")),
            alertes_fiche=_regex(pid, "alertes_fiche", p.get("alertes_fiche")),
            exiger=_regex(pid, "exiger", p.get("exiger")),
            exclure_titre=_regex(pid, "exclure_titre", p.get("exclure_titre")),
            description=" ".join((p.get("description") or "").split()),
            actif=p.get("actif", True),
        ))
    if erreurs:
        raise SystemExit("profiles.yaml invalide :\n  - " + "\n  - ".join(erreurs))
    if not profils:
        raise SystemExit("profiles.yaml : aucun profil défini")
    return profils


def load(path: Path, villes_connues: set[str]) -> list[Profile]:
    with open(path, encoding="utf-8") as f:
        return parse(yaml.safe_load(f), villes_connues)
