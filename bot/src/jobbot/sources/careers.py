"""Source : pages carrières d'entreprises ciblées, via les API publiques de leur outil de recrutement.

Ces API sont faites pour être lues par des sites tiers (pas de clé, pas de scraping) et
donnent l'annonce complète, rangée dans `Offer.fiche` : les profils peuvent y chercher des
mots-clés (`fiche:` dans profiles.yaml) même quand le titre ne dit rien.

Outils gérés (l'identifiant est celui de l'entreprise dans l'outil, voir config.yaml) :
- greenhouse      : boards-api.greenhouse.io/v1/boards/<id>/jobs?content=true
- lever           : api.lever.co/v0/postings/<id>?mode=json (ou api.eu.lever.co)
- ashby           : api.ashbyhq.com/posting-api/job-board/<id>
- workable        : apply.workable.com/api/v1/widget/accounts/<id>?details=true
- recruitee       : <id>.recruitee.com/api/offers/
- smartrecruiters : api.smartrecruiters.com/v1/companies/<id>/postings?country=fr
  (la liste ne contient pas l'annonce : pas de `fiche`, le titre seul compte)

Un passage par heure suffit (`carrieres.intervalle_minutes`) : les offres ne bougent pas vite
et on reste discret avec ces API.
"""

import html
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from jobbot.models import Offer

log = logging.getLogger(__name__)

TAGS = re.compile(r"<[^>]+>")


def plain(text: str | None) -> str:
    """Texte brut d'un fragment HTML (Greenhouse l'échappe une fois de plus)."""
    t = html.unescape(text or "")
    if "&lt;" in t or "&amp;" in t:
        t = html.unescape(t)
    return " ".join(html.unescape(TAGS.sub(" ", t)).split())


def _greenhouse(c: httpx.Client, ident: str, nom: str) -> list[Offer]:
    r = c.get(f"https://boards-api.greenhouse.io/v1/boards/{ident}/jobs", params={"content": "true"})
    r.raise_for_status()
    return [Offer(
        source="greenhouse", source_id=f"{ident}:{j['id']}", title=j["title"].strip(), company=nom,
        location=(j.get("location") or {}).get("name") or "", url=j["absolute_url"],
        fiche=plain(j.get("content")),
    ) for j in r.json().get("jobs", [])]


def _lever(c: httpx.Client, ident: str, nom: str) -> list[Offer]:
    for host in ("api.lever.co", "api.eu.lever.co"):
        r = c.get(f"https://{host}/v0/postings/{ident}", params={"mode": "json"})
        if r.status_code == 200 and isinstance(r.json(), list):
            break
    r.raise_for_status()
    out = []
    for j in r.json():
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or [cat.get("location") or ""]
        lists = " ".join(f"{x.get('text', '')} {plain(x.get('content'))}" for x in j.get("lists") or [])
        out.append(Offer(
            source="lever", source_id=f"{ident}:{j['id']}", title=j["text"].strip(), company=nom,
            location=" / ".join(x for x in locs if x), url=j["hostedUrl"],
            contract=cat.get("commitment"),
            fiche=" ".join([j.get("descriptionPlain") or "", lists, j.get("additionalPlain") or ""]),
        ))
    return out


def _ashby(c: httpx.Client, ident: str, nom: str) -> list[Offer]:
    r = c.get(f"https://api.ashbyhq.com/posting-api/job-board/{ident}")
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [x.get("location") or "" for x in j.get("secondaryLocations") or []]
        out.append(Offer(
            source="ashby", source_id=f"{ident}:{j['id']}", title=j["title"].strip(), company=nom,
            location=" / ".join(x for x in locs if x), url=j["jobUrl"],
            contract=j.get("employmentType"), fiche=j.get("descriptionPlain") or "",
        ))
    return out


def _workable(c: httpx.Client, ident: str, nom: str) -> list[Offer]:
    r = c.get(f"https://apply.workable.com/api/v1/widget/accounts/{ident}", params={"details": "true"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        locs = [f"{x.get('city', '')}, {x.get('country', '')}" for x in j.get("locations") or []]
        out.append(Offer(
            source="workable", source_id=f"{ident}:{j['shortcode']}", title=j["title"].strip(),
            company=nom, location=" / ".join(locs) or f"{j.get('city', '')}, {j.get('country', '')}",
            url=j.get("url") or f"https://apply.workable.com/{ident}/j/{j['shortcode']}/",
            contract=j.get("employment_type"), fiche=plain(j.get("description")),
        ))
    return out


def _recruitee(c: httpx.Client, ident: str, nom: str) -> list[Offer]:
    r = c.get(f"https://{ident}.recruitee.com/api/offers/")
    r.raise_for_status()
    return [Offer(
        source="recruitee", source_id=f"{ident}:{j['id']}", title=j["title"].strip(), company=nom,
        location=j.get("location") or j.get("city") or "", url=j["careers_url"],
        contract=j.get("employment_type_code"),
        fiche=plain(f"{j.get('description') or ''} {j.get('requirements') or ''}"),
    ) for j in r.json().get("offers", [])]


def _smartrecruiters(c: httpx.Client, ident: str, nom: str) -> list[Offer]:
    out, offset = [], 0
    while True:
        r = c.get(f"https://api.smartrecruiters.com/v1/companies/{ident}/postings",
                  params={"country": "fr", "limit": 100, "offset": offset})
        r.raise_for_status()
        d = r.json()
        for j in d.get("content", []):
            loc = j.get("location") or {}
            out.append(Offer(
                source="smartrecruiters", source_id=f"{ident}:{j['id']}", title=j["name"].strip(),
                company=nom, location=loc.get("address") or loc.get("city") or "",
                url=f"https://jobs.smartrecruiters.com/{ident}/{j['id']}",
                contract=(j.get("typeOfEmployment") or {}).get("id"),
            ))
        offset += 100
        if offset >= min(d.get("totalFound", 0), 1000):
            return out


ATS: dict[str, Callable[[httpx.Client, str, str], list[Offer]]] = {
    "greenhouse": _greenhouse, "lever": _lever, "ashby": _ashby, "workable": _workable,
    "recruitee": _recruitee, "smartrecruiters": _smartrecruiters,
}


def check_config(entreprises: list[dict]) -> None:
    bad = [e for e in entreprises if e.get("ats") not in ATS or not e.get("id") or not e.get("nom")]
    if bad:
        raise SystemExit(f"config.yaml, carrieres.entreprises : entrée(s) invalide(s) {bad} "
                         f"(il faut nom, ats parmi {sorted(ATS)}, id)")


class Careers:
    name = "carrieres"

    def __init__(self, entreprises: list[dict], stamp: Path | None = None, every_min: int = 60,
                 client: httpx.Client | None = None):
        check_config(entreprises)
        self.entreprises, self.stamp, self.every_min = entreprises, stamp, every_min
        self.client = client or httpx.Client(timeout=20, follow_redirects=True,
                                             headers={"User-Agent": "jobbot (offres d'emploi perso)"})
        self.failed: dict[str, str] = {}

    def due(self) -> bool:
        if self.stamp is None or not self.stamp.exists():
            return True
        # L'heure est écrite dans le fichier : la date du fichier change à chaque checkout Git.
        try:
            dernier = float(self.stamp.read_text().strip())
        except ValueError:
            return True
        return time.time() - dernier >= self.every_min * 60 - 30

    def fetch(self) -> list[Offer]:
        if not self.due():
            log.info("carrieres : dernier passage il y a moins de %d min, on attend", self.every_min)
            return []
        offers, self.failed = [], {}
        for e in self.entreprises:
            try:
                got = ATS[e["ats"]](self.client, e["id"], e["nom"])
            # une entreprise en panne (réseau, réponse inattendue) ne bloque pas les autres
            except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError) as ex:
                self.failed[e["nom"]] = f"{type(ex).__name__}"
                log.warning("carrieres : %s (%s/%s) en échec : %s", e["nom"], e["ats"], e["id"], ex)
                continue
            log.info("carrieres : %s : %d offres", e["nom"], len(got))
            offers += got
        if self.failed and len(self.failed) == len(self.entreprises):
            raise RuntimeError("toutes les pages carrières sont en échec")
        if self.stamp is not None:
            self.stamp.parent.mkdir(parents=True, exist_ok=True)
            self.stamp.write_text(str(time.time()))
        return offers
