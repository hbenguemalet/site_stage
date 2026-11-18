"""Aperçu des messages Discord d'un profil, sans toucher à la base ni aux salons des amis.

`jobbot --apercu-discord --profil dev` : affiche le JSON des messages (un message groupé de
quelques offres + un récapitulatif), construits à partir des mails d'alerte enregistrés dans
tests/fixtures/ (s'ils sont là) ou d'exemples intégrés. `--vers-test` les envoie sur le salon
de test (DISCORD_WEBHOOK_TEST).
"""

import json
import logging
from datetime import UTC, datetime

from jobbot.config import ROOT
from jobbot.filters import CityResolver, evaluate
from jobbot.models import Offer
from jobbot.notifiers import discord
from jobbot.profiles import Profile
from jobbot.storage import fingerprint

FIXTURES = ROOT / "tests" / "fixtures"
QUAND = datetime(2026, 11, 18, 7, 30, tzinfo=UTC)

EXEMPLES = [
    Offer("indeed", "a1", "Développeur Back-End Java / Spring (H/F)", "Canopee Group", "Paris (75)",
          "https://fr.indeed.com/viewjob?jk=a1", "Au sein d'une équipe produit, vous développerez des API "
          "Java/Spring Boot et participerez aux revues de code. Stack : Java 21, Spring, PostgreSQL, Angular.",
          QUAND, "CDI", "38 000 € - 42 000 € par an", alert="développeur (Paris (75))"),
    Offer("linkedin", "a2", "Développeur Angular junior", "Claranet France", "Lille, Hauts-de-France, France",
          "https://www.linkedin.com/jobs/view/a2", published_at=QUAND, contract="CDI",
          alert="Développeur (Lille Et Périphérie)"),
    Offer("hellowork", "a3", "Alternance Data Analyst (H/F)", "Decathlon", "Villeneuve-d'Ascq - 59",
          "https://www.hellowork.com/fr-fr/emplois/a3.html", "Tableaux de bord Power BI, requêtes SQL "
          "sur l'entrepôt de données, accompagnement des équipes métier.", QUAND, "Alternance"),
    Offer("greenhouse", "a4", "Alternance Contrôle de gestion", "Back Market", "Paris, France",
          "https://job-boards.greenhouse.io/backmarket/jobs/a4", contract="alternance",
          fiche="Requêtes SQL, Looker et Python au quotidien."),
    Offer("indeed", "a5", "Alternance Chargé de reporting", "ACME", "Paris (75)", "https://fr.indeed.com/viewjob?jk=a5",
          published_at=QUAND, contract="alternance", alert="data OR sql (Paris (75))"),
    Offer("makesense", "a6", "Stage Chargé·e de mission RSE", "Ticket for Change", "Paris",
          "https://jobs.makesense.org/fr/jobs/a6", "Stage de 6 mois à partir d'avril 2027 : bilan carbone, "
          "rapport extra-financier et animation de la démarche RSE.", QUAND, "stage", alert="Stage - Paris"),
    Offer("coordinationsud", "a7", "Stage – Assistant·e plaidoyer (Paris)", "Action contre la Faim", "Paris",
          "https://www.coordinationsud.org/offre/a7", published_at=QUAND, contract="stage"),
    Offer("lesjeudis", "a8", "Développeur Full Stack Java Angular", "Infotel", "Paris - 75",
          "https://www.lesjeudis.com/emploi/a8", published_at=QUAND, contract="CDI", salary="40-45 K€"),
]


def fixture_offers(mailbox: str) -> list[Offer]:
    """Offres des mails d'alerte enregistrés dans tests/fixtures/ (fichiers privés, non commités)."""
    from imap_tools import MailMessage

    from jobbot.sources.email_alerts import EmailAlerts

    src = EmailAlerts("", mailbox, "", "")
    logging.getLogger("jobbot.sources.email_alerts").setLevel(logging.WARNING)
    offers = []
    for path in sorted(FIXTURES.glob("*.eml")):
        offers += src.parse_message(MailMessage.from_bytes(path.read_bytes()))
    return offers


def pick(p: Profile, offers: list[Offer], cities: CityResolver) -> list[tuple[Offer, object]]:
    """Offres retenues par le profil, dédoublonnées, de la mieux à la moins bien notée."""
    out, seen = [], set()
    for o in offers:
        o.city_key = cities.city_of(o)
        v = evaluate(p, o)
        if v.ok and fingerprint(o) not in seen:
            seen.add(fingerprint(o))
            out.append((o, v))
    return sorted(out, key=lambda ov: ov[1].score, reverse=True)


def spread(items: list, n: int) -> list:
    """n éléments répartis sur toute la liste (pour voir des scores variés)."""
    if len(items) <= n:
        return items
    return [items[round(i * (len(items) - 1) / (n - 1))] for i in range(n)]


def build(p: Profile, cfg: dict, env: dict, n: int = 4) -> tuple[list[dict], str]:
    cities = CityResolver(cfg["villes"])
    retenues, origine = [], "exemples intégrés"
    if any(FIXTURES.glob("*.eml")):
        retenues, origine = pick(p, fixture_offers(env.get("IMAP_USER", "")), cities), "mails de tests/fixtures"
    if len(retenues) < n:
        retenues, origine = pick(p, EXEMPLES, cities) + retenues, origine + " + exemples intégrés"
    messages = [m for m, _ in discord.build_messages(spread(retenues, n), p)]
    messages += [m for m, _ in discord.build_recap(retenues[:12], p)][:1]
    return messages, f"{len(retenues)} offres retenues ({origine})"


def run(p: Profile, cfg: dict, env: dict, vers_test: bool = False) -> None:
    messages, info = build(p, cfg, env)
    print(f"# Aperçu Discord, profil {p.id} : {info}, variante de score « {discord.VARIANTE_SCORE} »")
    for i, m in enumerate(messages, 1):
        print(f"\n# --- message {i}/{len(messages)} ---")
        print(json.dumps(m, ensure_ascii=False, indent=2))
    if not vers_test:
        print("\n# Rien n'a été envoyé (ajouter --vers-test pour le salon de test).")
        return
    webhook = env.get("DISCORD_WEBHOOK_TEST", "")
    if not webhook:
        raise SystemExit("DISCORD_WEBHOOK_TEST vide dans .env : créer le salon #test-bot et son webhook.")
    for m in messages:
        discord.post(webhook, m)
    print(f"\n# {len(messages)} message(s) envoyé(s) sur le salon de test.")
