"""Source : API officielle La bonne alternance (offres d'alternance, service public).

API gratuite, réservée aux usages non lucratifs ; jeton personnel à garder secret
(compte sur https://api.apprentissage.beta.gouv.fr, variable LBA_API_KEY dans .env).

Route : GET /api/job/v1/search?romes=…&latitude=…&longitude=…&radius=…
Réponse : {"jobs": [...], "recruiters": [...]}. On ne garde que `jobs` (offres publiées) :
`recruiters` liste des entreprises « susceptibles de recruter », sans offre.
Schéma relevé dans la doc de l'API et dans alternabot (MIT, github.com/tarikanders/alternabot).
"""

import logging

import httpx

from jobbot.models import Offer

log = logging.getLogger(__name__)

ENDPOINT = "https://api.apprentissage.beta.gouv.fr/api/job/v1/search"
RAYONS = (10, 30, 60, 100)  # seuls rayons acceptés par l'API (km)
SITE = "https://labonnealternance.apprentissage.beta.gouv.fr"


class LBAError(RuntimeError):
    pass


def arrondir_rayon(km: float) -> int:
    return next((r for r in RAYONS if km <= r), RAYONS[-1])


def _get(d, *path, default=None):
    for k in path:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return default if d is None else d


def to_offer(job: dict, city_key: str) -> Offer | None:
    title = _get(job, "offer", "title")
    jid = _get(job, "identifier", "id") or _get(job, "identifier", "partner_job_id")
    if not title or not jid:
        return None
    wp = job.get("workplace") or {}
    company = wp.get("brand") or wp.get("name") or wp.get("legal_name")
    loc = wp.get("location") or {}
    location = loc.get("address") or loc.get("city") or ""
    url = _get(job, "apply", "url") or f"{SITE}/recherche?jobId={jid}"
    return Offer(
        source="labonnealternance", source_id=str(jid), title=title.strip(),
        company=(company or "").strip() or None, location=location, url=url,
        description=_get(job, "offer", "description", default="") or "",
        contract="alternance", city_key=city_key,
    )


class LaBonneAlternance:
    name = "labonnealternance"

    def __init__(self, token: str, villes: dict, romes: list[str], rayon_km: int = 30,
                 client: httpx.Client | None = None):
        self.token, self.romes = token, romes
        self.rayon = arrondir_rayon(rayon_km)
        # Une recherche par ville qui a des coordonnées dans config.yaml (lat / lon)
        self.points = {k: (v["lat"], v["lon"]) for k, v in villes.items() if "lat" in v and "lon" in v}
        self.client = client or httpx.Client(timeout=20)

    def search(self, lat: float, lon: float) -> list[dict]:
        r = self.client.get(ENDPOINT, params={
            "romes": ",".join(self.romes[:20]), "latitude": lat, "longitude": lon, "radius": self.rayon,
        }, headers={"Authorization": f"Bearer {self.token}", "Accept": "application/json"})
        if r.status_code in (401, 403):
            raise LBAError("jeton La bonne alternance refusé : vérifier LBA_API_KEY dans .env")
        if r.status_code >= 400:
            raise LBAError(f"API La bonne alternance : erreur HTTP {r.status_code}")
        data = r.json()
        return data.get("jobs") or data.get("offers") or []

    def fetch(self) -> list[Offer]:
        offers, seen = [], set()
        for city, (lat, lon) in self.points.items():
            jobs = self.search(lat, lon)
            got = [o for o in (to_offer(j, city) for j in jobs) if o and o.source_id not in seen]
            seen.update(o.source_id for o in got)
            log.info("La bonne alternance [%s] : %d offres", city, len(got))
            offers += got
        return offers
