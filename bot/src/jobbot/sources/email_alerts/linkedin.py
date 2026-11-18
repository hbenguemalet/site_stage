"""Parser des mails « votre alerte Emploi pour … » de LinkedIn (jobalerts-noreply@linkedin.com).

Carte d'offre : [titre, « Entreprise · Lieu », (salaire), (badges : « Recrutement actif »…)].
Le lien de chaque carte (logo, titre…) pointe vers /comm/jobs/view/<id> : on garde l'id et on
publie le lien canonique, sans les paramètres de suivi.
"""

import re
from html import unescape

from bs4 import BeautifulSoup

from jobbot.models import Offer
from jobbot.sources.email_alerts.common import card_lines

JOB_LINK = re.compile(r"linkedin\.com/(comm/)?jobs/view/(\d+)")
SEP = " · "


def parse(html: str) -> list[Offer]:
    soup = BeautifulSoup(html, "lxml")
    offers, seen = [], set()
    for a in soup.find_all("a", href=JOB_LINK):
        title = " ".join(a.stripped_strings)
        if not title:  # lien du logo / de l'image : la carte a aussi un lien sur le titre
            continue
        jid = JOB_LINK.search(a["href"]).group(2)
        if jid in seen:
            continue
        lines = card_lines(a, min_lines=2)
        if len(lines) < 2 or lines[0] != title or SEP not in lines[1]:
            continue
        # certains titres arrivent doublement échappés (« Stratégie &amp;amp; Développement »)
        title = unescape(title)
        company, location = (unescape(x).strip() for x in lines[1].split(SEP, 1))
        salary = next((x for x in lines[2:] if "€" in x), None)
        seen.add(jid)
        offers.append(Offer(
            source="linkedin", source_id=jid, title=title, company=company or None,
            location=location, url=f"https://www.linkedin.com/jobs/view/{jid}/", salary=salary,
        ))
    return offers
