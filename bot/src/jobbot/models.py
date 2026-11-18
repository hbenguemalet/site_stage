from dataclasses import dataclass
from datetime import datetime


@dataclass
class Offer:
    """Format commun à toutes les sources."""

    source: str  # "adzuna", "indeed", "hellowork"…
    source_id: str  # identifiant unique côté source
    title: str
    company: str | None
    location: str
    url: str
    description: str = ""  # vide si la source ne la fournit pas
    published_at: datetime | None = None
    contract: str | None = None
    salary: str | None = None
    city_key: str | None = None  # "lille" / "paris" (rempli par la source ou CityResolver)
    # Nom de l'alerte e-mail qui a amené l'offre (« data OR sql (Lille (59)) ») : le site a
    # cherché ces mots dans toute l'annonce, même s'ils ne sont pas dans le titre.
    alert: str = ""
    # Texte complet de l'annonce (sources API : pages carrières). Lu seulement par les
    # regex `fiche` des profils, jamais affiché ni utilisé par les exclusions.
    fiche: str = ""
