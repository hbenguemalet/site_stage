"""Parser de l'« alerte emploi Coordination SUD » (lettre@coordinationsud.org).

Les offres se suivent dans un même bloc : titre (lien), « Organisation - JJ/MM/AAAA »,
« Contrat », « : Stage ou Alternance », « Localisation(s) », « : Europe, France ».
Lien : http://www.coordinationsud.org?p=<id d'article>&u=<id d'abonné> → on ne garde que
l'article (l'id d'abonné est personnel).

La localisation ne donne que le pays : la ville n'est connue que si le titre la cite
(« … – Paris »), sinon le filtre ville écarte l'offre.
"""

import re
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup

from jobbot.models import Offer

JOB_LINK = re.compile(r"coordinationsud\.org/?\?p=\d+")
ORG_DATE = re.compile(r"^(.*?)\s+-\s+\d{2}/\d{2}/\d{4}$")
VILLE_TITRE = re.compile(r"\b(Paris|Lille)\b", re.IGNORECASE)


def _field(strings: list[str], label: str) -> str | None:
    if label in strings:
        i = strings.index(label)
        if i + 1 < len(strings):
            return strings[i + 1].lstrip(": ").strip() or None
    return None


def parse(html: str) -> list[Offer]:
    soup = BeautifulSoup(html, "lxml")
    offers, seen = [], set()
    for a in soup.find_all("a", href=JOB_LINK):
        title = " ".join(a.stripped_strings)
        pid = (parse_qs(urlsplit(a["href"]).query).get("p") or [None])[0]
        if not title or not pid or pid in seen:
            continue
        # textes qui suivent le titre, jusqu'à l'offre suivante
        after = []
        for s in a.find_all_next(string=True):
            if s.find_parent("a") is not None and after:
                break
            if (t := s.strip()) and s.find_parent("a") is None:
                after.append(t)
            if len(after) >= 5:
                break
        m = ORG_DATE.match(after[0]) if after else None
        if not m:
            continue
        ville = VILLE_TITRE.search(title)
        seen.add(pid)
        offers.append(Offer(
            source="coordinationsud", source_id=pid, title=title, company=m.group(1),
            location=_field(after, "Localisation(s)") or "", contract=_field(after, "Contrat"),
            url=f"https://www.coordinationsud.org/?p={pid}",
            city_key=ville.group(1).lower() if ville else None,
        ))
    return offers
