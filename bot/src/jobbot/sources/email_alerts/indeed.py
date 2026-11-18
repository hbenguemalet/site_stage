"""Parser des mails d'alerte emploi Indeed (jobalert.indeed.com)."""

import re
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from jobbot.models import Offer
from jobbot.sources.email_alerts.common import card_lines, stable_id

JOB_LINK = re.compile(r"indeed\.com/(rc|pagead)/clk")


def parse(html: str) -> list[Offer]:
    soup = BeautifulSoup(html, "lxml")
    offers, seen = [], set()
    for a in soup.find_all("a", href=JOB_LINK):
        title = " ".join(a.stripped_strings)
        # Carte d'offre : [titre, entreprise, lieu, (salaire), (badges…), « il y a N jours »]
        lines = card_lines(a, min_lines=3)
        if len(lines) < 3 or lines[0] != title:
            continue
        company, location = lines[1], lines[2]
        salary = next((x for x in lines[3:] if "€" in x), None)
        jk = parse_qs(urlparse(a["href"]).query).get("jk", [None])[0]
        if jk:  # offre classique : identifiant Indeed stable → URL propre sans suivi
            sid, url = jk, f"https://fr.indeed.com/viewjob?jk={jk}"
        else:   # offre sponsorisée : pas d'identifiant, on garde le lien fourni
            sid, url = stable_id(title, company, location), a["href"]
        if sid in seen:
            continue
        seen.add(sid)
        offers.append(Offer(
            source="indeed", source_id=sid, title=title, company=company,
            location=location, url=url, salary=salary,
        ))
    return offers
