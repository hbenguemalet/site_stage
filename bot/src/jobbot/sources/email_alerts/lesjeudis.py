"""Parser des mails « De nouvelles offres pour votre alerte — LesJeudis » (emploi@alertes.lesjeudis.com).

Chaque offre : un lien vide vers lesjeudis.com/offers/<uuid> suivi, dans la même cellule, de
[titre, « Entreprise · Ville », « NN% match »]. Le lien est déjà propre (pas de suivi).
"""

import re

from bs4 import BeautifulSoup

from jobbot.models import Offer

JOB_LINK = re.compile(r"^https://(?:www\.)?lesjeudis\.com/offers/([0-9a-f-]{36})")
SEP = " · "


def parse(html: str) -> list[Offer]:
    soup = BeautifulSoup(html, "lxml")
    offers, seen = [], set()
    for a in soup.find_all("a", href=JOB_LINK):
        uuid = JOB_LINK.match(a["href"]).group(1)
        if uuid in seen or a.parent is None:
            continue
        lines = [x for x in a.parent.stripped_strings if not x.endswith("% match")]
        if len(lines) < 2 or SEP not in lines[1]:
            continue
        company, location = (x.strip() for x in lines[1].rsplit(SEP, 1))
        seen.add(uuid)
        offers.append(Offer(
            source="lesjeudis", source_id=uuid, title=lines[0], company=company or None,
            location=location, url=f"https://lesjeudis.com/offers/{uuid}",
        ))
    return offers
