"""Page web perso : écrit `offres.js` (lu par la page /alternance/) à partir des offres retenues.

Le bot ne garde en base ni la description ni le salaire des offres ; pour que la page puisse
afficher rythme / début / durée, chaque passage ajoute ses offres retenues à un petit fichier
JSON (data/site_<profil>.json), purgé après `conserver_jours`, puis réécrit `offres.js`.
Configuration : section `site:` de config.yaml. Rien n'est écrit si elle est absente.

Si `site.git_push` est vrai, `dossier` doit être un clone git du dépôt de la page : après chaque
changement, `offres.js` est commité et poussé (GitHub Pages republie alors la page tout seul).
"""

import json
import logging
import re
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from jobbot.filters import Verdict
from jobbot.models import Offer

log = logging.getLogger("jobbot.site")

SITES = {"indeed": "Indeed", "hellowork": "HelloWork", "linkedin": "LinkedIn", "makesense": "Jobs that make sense",
         "lesjeudis": "Les Jeudis", "coordinationsud": "Coordination SUD", "labonnealternance": "La bonne alternance"}
MOIS = "janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre"
RX_DEBUT = re.compile(rf"(?:d[ée]but|d[ée]marrage|[àa] partir (?:de|du)|rentr[ée]e)[^.\n]{{0,40}}?"
                      rf"((?:{MOIS})\s*20\d\d|rentr[ée]e\s*20\d\d|20\d\d)", re.I)
RX_RYTHME = [
    (re.compile(r"\b(\d)\s*(?:j|jours?)\s*/\s*(\d)\s*(?:j|jours?)\b", re.I), "{} j / {} j"),
    (re.compile(r"\b(\d)\s*(?:sem\.?|semaines?)\s*/\s*(\d)\s*(?:sem\.?|semaines?)\b", re.I), "{} sem. / {} sem."),
    (re.compile(r"\b(\d)\s*semaines? (?:en entreprise )?sur\s*(\d)\b", re.I), "{} sem. sur {}"),
]
RX_DUREE = re.compile(r"(?:dur[ée]e|contrat)[^.\n]{0,25}?(\d{1,2})\s*(mois|ans?)\b", re.I)
RX_ETOILE = re.compile(r"design|graphi|direction artistique|textile|mode\b|fashion|[ée]dition|mus[ée]e|culture", re.I)

LIENS = [
    ["LinkedIn", "Stage design · France",
     "https://www.linkedin.com/jobs/search/?keywords=stage%20design&location=France"],
    ["LinkedIn", "Stage design · Europe",
     "https://www.linkedin.com/jobs/search/?keywords=design%20internship&location=Europe"],
    ["Welcome to the Jungle", "Stage design / graphisme",
     "https://www.welcometothejungle.com/fr/jobs?query=stage%20design"],
    ["Culture Jobs", "Emploi et stages culture (Paris)", "https://www.culturejobs.fr/"],
    ["Choisir le service public", "Stages dans la fonction publique (musées…)", "https://choisirleservicepublic.gouv.fr/"],
    ["Erasmus+ stage", "Stage à l'étranger avec bourse", "https://www.erasmusplus.fr/"],
]



def infos(o: Offer) -> list[str]:
    """Début / rythme / durée lus dans le texte de l'annonce (« non précisé » sinon)."""
    texte = f"{o.title} {o.description} {o.fiche}"
    m = RX_DEBUT.search(texte)
    debut = m.group(1).lower() if m else None
    rythme = None
    for rx, fmt in RX_RYTHME:
        if (m := rx.search(texte)):
            rythme = fmt.format(*m.groups())
            break
    m = RX_DUREE.search(texte)
    duree = f"{m.group(1)} {m.group(2).lower()}" if m else None
    return [f"Début : {debut}" if debut else "Début : non précisé",
            f"Rythme : {rythme}" if rythme else "Rythme : non précisé",
            f"Durée : {duree}" if duree else "Durée : non précisée"]


def entry(o: Offer, v: Verdict, now: datetime) -> dict:
    return {
        "titre": o.title, "entreprise": o.company or "", "lieu": o.location or "", "url": o.url,
        "etoile": bool(RX_ETOILE.search(o.title)), "salaire": o.salary or "",
        "site": SITES.get(o.source, o.source.capitalize()), "pourquoi": [], "note": None,
        "infos": infos(o), "score": v.score, "vu": now.isoformat(timespec="seconds"),
        "texte": " ".join((o.fiche or o.description or "").split())[:6000],
    }


def update(profil_id: str, retenues: list[tuple[Offer, Verdict]], scfg: dict, root: Path,
           now: datetime | None = None) -> int:
    """Ajoute `retenues` au fichier JSON du profil et réécrit offres.js. Rend le nombre d'offres publiées."""
    now = now or datetime.now(UTC)
    store = root / "data" / f"site_{profil_id}.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    gardees: dict[str, dict] = json.loads(store.read_text("utf-8")) if store.exists() else {}
    for o, v in retenues:  # chaque passage rafraîchit « vu » : une offre disparue vieillit puis est purgée
        e = entry(o, v, now)
        e["premiere"] = gardees.get(o.url, {}).get("premiere", e["vu"])
        if not e["texte"]:
            e["texte"] = gardees.get(o.url, {}).get("texte", "")
        gardees[o.url] = e
    limite = (now - timedelta(days=scfg.get("conserver_jours", 21))).isoformat()
    gardees = {u: e for u, e in gardees.items() if e["vu"] >= limite}
    store.write_text(json.dumps(gardees, ensure_ascii=False), "utf-8")

    seuil = scfg.get("score_proche", 60)
    tri = [{k: v for k, v in e.items() if k != "texte"}  # le texte des annonces reste dans le JSON, pas dans la page
           for e in sorted(gardees.values(), key=lambda e: (e["score"], e["premiere"]), reverse=True)]
    data = {"date": now.date().isoformat(),
            "meilleures": [e for e in tri if e["score"] >= seuil],
            "autres": [e for e in tri if e["score"] < seuil],
            "liens": LIENS}
    if scfg.get("depot_candidature"):
        data["candidature"] = scfg["depot_candidature"]
    dossier = Path(scfg["dossier"])
    if not dossier.is_absolute():
        dossier = root / dossier
    dossier.mkdir(parents=True, exist_ok=True)
    cible = dossier / "offres.js"
    corps = f"window.STAGES = {json.dumps(data, ensure_ascii=False, indent=1)};\n"
    if cible.exists() and _sans_date(cible.read_text("utf-8")) == _sans_date(corps):
        return len(gardees)  # rien de neuf : pas de réécriture, pas de commit
    cible.write_text(f"/* Généré par le bot d'offres (profil {profil_id}) — ne pas modifier à la main. */\n" + corps, "utf-8")
    if scfg.get("git_push"):
        publier(dossier, f"Offres du {now.date().isoformat()} ({len(gardees)})")
    return len(gardees)


def _sans_date(texte: str) -> str:
    return re.sub(r'"date": "[^"]*",?', "", texte.split("window.STAGES", 1)[-1])


def publier(dossier: Path, message: str) -> bool:
    """Commit + push de offres.js depuis `dossier`. N'arrête jamais le bot : une erreur est journalisée."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(dossier), *args], capture_output=True, text=True, timeout=60, check=True)

    try:
        git("add", "offres.js")
        if subprocess.run(["git", "-C", str(dossier), "diff", "--cached", "--quiet"], timeout=60).returncode == 0:
            return False
        git("-c", "user.name=jobbot", "-c", "user.email=jobbot@localhost", "commit", "-m", message)
        git("pull", "--rebase", "--autostash", "-q")
        git("push", "-q")
        log.info("page web : offres.js poussé sur git")
        return True
    except (subprocess.SubprocessError, OSError) as e:
        log.error("page web : push git impossible (%s)", getattr(e, "stderr", None) or e)
        return False
