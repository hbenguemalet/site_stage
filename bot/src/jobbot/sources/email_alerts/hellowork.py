"""Parser des mails « Votre alerte … : N nouvelles offres » de HelloWork."""

import base64
import re

from bs4 import BeautifulSoup

from jobbot.models import Offer
from jobbot.sources.email_alerts.common import card_lines

CLIC = re.compile(r"emails\.hellowork\.com/clic/")
REAL_URL = re.compile(r"https://www\.hellowork\.com/fr-fr/emplois/(\d+)\.html")
CONTRATS = {"cdi", "cdd", "stage", "alternance", "interim", "intérim", "freelance", "indépendant"}


def real_offer(clic_url: str) -> tuple[str, str] | None:
    """Le lien de suivi embarque en base64 l'adresse du destinataire et la vraie URL de
    l'offre : on en extrait (id, URL propre) pour ne jamais republier le lien de suivi."""
    for seg in clic_url.rstrip("/").split("/")[-1:]:
        try:
            raw = base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)).decode("utf-8", "ignore")
        except ValueError:
            return None
        if m := REAL_URL.search(raw):
            return m.group(1), m.group(0)
    return None


def parse(html: str) -> list[Offer]:
    soup = BeautifulSoup(html, "lxml")
    offers = []
    for a in soup.find_all("a", href=CLIC):
        title = " ".join(a.stripped_strings)
        # Carte d'offre : [titre, entreprise, lieu, contrat, (salaire), « Voir l'offre »]
        lines = card_lines(a, min_lines=4)
        if len(lines) < 4 or lines[0] != title or not lines[-1].startswith("Voir"):
            continue
        company = lines[1]
        # Des badges (« Super recruteur »…) peuvent s'intercaler : le lieu est juste avant le contrat
        i = next((k for k, x in enumerate(lines) if k >= 2 and x.lower() in CONTRATS), None)
        contract = lines[i] if i is not None else None
        location = lines[i - 1] if i is not None else lines[2]
        salary = next((x for x in lines[3:-1] if "€" in x), None)
        real = real_offer(a["href"])
        if real is None:  # format inconnu : on ne publie pas un lien qui contient l'adresse mail
            continue
        sid, url = real
        offers.append(Offer(
            source="hellowork",
            source_id=sid,
            title=title,
            company=company,
            location=location,
            url=url,
            contract=contract,
            salary=salary,
        ))
    return offers
