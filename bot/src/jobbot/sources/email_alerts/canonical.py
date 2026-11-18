"""Identifiant unique d'une offre, lu dans son lien, et lien canonique propre.

Une même offre arrive avec des liens différents (paramètres, sous-domaine, langue, lien
« currentJobId »…). On la ramène à (site, id) et à une URL unique, ce qui sert :
- de `source_id` stable pour le parser générique ;
- de clé de dédoublonnage entre mails et entre sources (seulement pour les liens reconnus :
  un lien générique, partagé par plusieurs offres, ne doit pas les confondre) ;
- de lien propre à publier.

Formats vérifiés : LinkedIn, Indeed, HelloWork, Jobs that make sense. Les autres sont tirés
de leurs URL publiques et seront confirmés sur les premiers vrais mails.
"""

import re
from collections.abc import Callable
from typing import NamedTuple
from urllib.parse import parse_qs, urlsplit


class Canon(NamedTuple):
    site: str
    id: str
    url: str

    @property
    def key(self) -> str:
        return f"{self.site}:{self.id}"


def _q(url: str, name: str) -> str | None:
    return (parse_qs(urlsplit(url).query).get(name) or [None])[0]


def _linkedin(url: str, path: str) -> Canon | None:
    m = re.search(r"/jobs/view/(?:[^/]*-)?(\d{6,})", path)
    jid = m.group(1) if m else _q(url, "currentJobId")
    return Canon("linkedin", jid, f"https://www.linkedin.com/jobs/view/{jid}/") if jid and jid.isdigit() else None


def _indeed(url: str, path: str) -> Canon | None:
    jk = _q(url, "jk") or _q(url, "vjk")
    ok = jk and re.fullmatch(r"[0-9a-f]{16}", jk)
    return Canon("indeed", jk, f"https://fr.indeed.com/viewjob?jk={jk}") if ok else None


def _path(site: str, rx: str, build: Callable[[re.Match, str], tuple[str, str]]):
    """Règle simple : l'identifiant est dans le chemin de l'URL."""
    def rule(url: str, path: str) -> Canon | None:
        m = re.search(rx, path)
        return Canon(site, *build(m, path)) if m else None
    return rule


# (fin du nom d'hôte, règle) : la première règle qui reconnaît le lien gagne
RULES: list[tuple[tuple[str, ...], Callable[[str, str], Canon | None]]] = [
    (("linkedin.com",), _linkedin),
    (("indeed.com", "indeed.fr"), _indeed),
    (("hellowork.com",), _path("hellowork", r"/emplois/(\d+)\.html", lambda m, p: (
        m[1], f"https://www.hellowork.com/fr-fr/emplois/{m[1]}.html"))),
    (("jobs.makesense.org",), _path("makesense", r"/jobs/([A-Za-z0-9-]+)", lambda m, p: (
        m[1].rsplit("-", 1)[-1], f"https://jobs.makesense.org/fr/jobs/{m[1]}"))),
    (("welcometothejungle.com",), _path("wttj", r"/companies/([^/]+)/jobs/([^/?#]+)", lambda m, p: (
        f"{m[1]}/{m[2]}", f"https://www.welcometothejungle.com/fr/companies/{m[1]}/jobs/{m[2]}"))),
    (("apec.fr",), _path("apec", r"/detail-offre/([A-Za-z0-9]+)", lambda m, p: (
        m[1], f"https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/{m[1]}"))),
    (("jobteaser.com",), _path("jobteaser", r"/job-offers/([0-9a-f-]{8,})", lambda m, p: (
        m[1], f"https://www.jobteaser.com/fr/job-offers/{m[1]}"))),
    (("free-work.com",), _path("freework", r"/job-mission/([^/?#]+)", lambda m, p: (
        m[1], f"https://www.free-work.com{p}"))),
]


def canonical(url: str) -> Canon | None:
    """(site, id, URL canonique) si le lien est reconnu comme une offre, sinon None."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    for suffixes, rule in RULES:
        if host.endswith(suffixes) and (c := rule(url, parts.path)):
            return c
    return None
