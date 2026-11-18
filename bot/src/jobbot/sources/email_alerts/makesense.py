"""Parser des mails d'alerte Jobs that make sense (jobs@makesense.org, envoyés via customer.io).

Carte d'offre : [entreprise, titre, description, contrat(s)…, lieu].
Chaque lien passe par e.customeriomail.com/e/c/<base64 JSON> : le JSON contient la vraie URL
(« href »), qu'on publie à la place du lien de suivi. Les « Partenariats sponsorisés »
(formations, lien /exclusivities/) sont ignorés.
"""

import base64
import json
import re

from bs4 import BeautifulSoup

from jobbot.models import Offer
from jobbot.sources.email_alerts.common import card_lines

TRACK = re.compile(r"customeriomail\.com/e/c/([A-Za-z0-9_-]+)")
JOB = re.compile(r"^https://jobs\.makesense\.org/(?:fr/)?jobs/([A-Za-z0-9]+)")
ALERTE = re.compile(r"Votre alerte · .*?\b(Paris|Lille)\b", re.IGNORECASE)
# Lieu exploitable par le filtre ville : code postal, ou « Ville, Pays »
LIEU_PRECIS = re.compile(r"\b\d{5}\b|,")


def real_url(href: str) -> str | None:
    m = TRACK.search(href)
    if not m:
        return None
    seg = m.group(1)
    try:
        data = json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))
    except ValueError:
        return None
    return data.get("href") if isinstance(data, dict) else None


def parse(html: str) -> list[Offer]:
    soup = BeautifulSoup(html, "lxml")
    m = ALERTE.search(" ".join(soup.stripped_strings))
    alert_city = m.group(1).lower() if m else None
    offers, seen = [], set()
    for a in soup.find_all("a", href=TRACK):
        title = " ".join(a.stripped_strings)
        if not title:
            continue
        url = real_url(a["href"])
        job = JOB.match(url or "")
        if not job or job.group(1) in seen:
            continue
        lines = card_lines(a, min_lines=4)
        if len(lines) < 4 or lines[1] != title:
            continue
        company, location = lines[0], lines[-1]
        contracts = lines[3:-1]
        seen.add(job.group(1))
        offers.append(Offer(
            source="makesense", source_id=job.group(1), title=title, company=company,
            location=location, url=url.split("?")[0], description=lines[2],
            contract=contracts[0] if contracts else None,
            # adresse sans ville (« 9 Rue des Filles Saint-Thomas ») : ville de l'alerte
            city_key=None if LIEU_PRECIS.search(location) else alert_city,
        ))
    return offers
