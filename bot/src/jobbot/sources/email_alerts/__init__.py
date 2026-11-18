"""Source : alertes e-mail reçues dans la boîte dédiée (lecture IMAP).

On relit les mails des N derniers jours à chaque passage, sans modifier la boîte
(pas de marquage « lu ») : le dédoublonnage est fait par la base SQLite. Ainsi
--dry-run ne touche à rien, et une offre dont l'envoi a échoué (ou qui dépasse
max_par_execution) est reprise au passage suivant.
"""

import logging
import re
from collections import Counter
from collections.abc import Callable
from datetime import date, timedelta
from typing import NamedTuple

from imap_tools import AND, MailBox

from jobbot.models import Offer
from jobbot.sources.email_alerts import (
    coordinationsud,
    hellowork,
    indeed,
    lesjeudis,
    linkedin,
    makesense,
)
from jobbot.sources.email_alerts.canonical import canonical
from jobbot.sources.email_alerts.links import safe_url

log = logging.getLogger(__name__)

# Mails de service d'un site d'alertes (confirmation, bienvenue…) : sans offre, et c'est normal.
# Ils prouvent que l'expéditeur est vivant, mais ne comptent pas pour « 0 offre = format changé ».
SERVICE_SUBJECT = re.compile(
    r"est maintenant active|a bien été (créée|enregistrée)|confirm|bienvenue|welcome|"
    r"v[ée]rifie[rz]? votre|activez|mot de passe|password|d[ée]sinscri|unsubscribe",
    re.IGNORECASE,
)


# Nom de l'alerte (la recherche enregistrée sur le site), lu dans le sujet du mail
ALERT_NAME = [
    re.compile(r"\d+ offres? d'emploi (?:suppl[ée]mentaires? )?(?P<a>.+)$", re.IGNORECASE),       # Indeed
    re.compile(r"^Votre alerte (?P<a>.+?) : \d+ nouvelles? offres?", re.IGNORECASE),               # HelloWork
    re.compile(r"votre alerte Emploi pour (?P<a>.+?)(?: a été créée)?$", re.IGNORECASE),           # LinkedIn
    re.compile(r"correspondent à votre alerte \((?P<a>.+?)\)", re.IGNORECASE),                     # makesense
]


def alert_name(subject: str) -> str:
    """« data OR sql (Paris (75)) » pour un mail Indeed, etc. ; "" si le format est inconnu."""
    s = " ".join((subject or "").split())
    return next((m.group("a").strip() for rx in ALERT_NAME if (m := rx.search(s))), "")


class Route(NamedTuple):
    """Quel parser pour quel expéditeur.
    - local : si renseigné, seuls les mails de cette adresse sont des alertes ; les autres mails
      du site (notifications LinkedIn…) sont ignorés en silence, sans compter dans la santé ;
    - subject : si renseigné, un mail sans offre dont le sujet ne correspond pas est un mail
      de service / pub (« Plus que quelques minutes… »), pas un parser cassé."""

    domain: str
    parser: Callable[[str], list[Offer]]
    local: str | None = None
    subject: re.Pattern | None = None


ROUTES = [
    Route("jobalert.indeed.com", indeed.parse),
    Route("hellowork.com", hellowork.parse),
    Route("linkedin.com", linkedin.parse, local="jobalerts-noreply"),
    Route("makesense.org", makesense.parse),
    Route("coordinationsud.org", coordinationsud.parse, subject=re.compile(r"alerte emploi", re.IGNORECASE)),
    Route("lesjeudis.com", lesjeudis.parse, subject=re.compile(r"offres pour votre alerte", re.IGNORECASE)),
]


def route_for(sender: str) -> Route | None:
    domain = sender_domain(sender)
    return next((r for r in ROUTES if domain == r.domain or domain.endswith("." + r.domain)), None)


def is_alert_sender(sender: str, r: Route) -> bool:
    return r.local is None or sender.rsplit("@", 1)[0].lower().strip("<> ") == r.local


def parser_for(sender: str):
    r = route_for(sender)
    return r.parser if r and is_alert_sender(sender, r) else None


def sender_domain(sender: str) -> str:
    return sender.rsplit("@", 1)[-1].lower().strip("<> ")


def publishable(offers: list[Offer], mailbox: str) -> tuple[list[Offer], int]:
    """Nettoie les URL (suivi retiré, forme canonique si le site est reconnu) et écarte
    les offres dont le lien trahit la boîte."""
    kept, dropped = [], 0
    for o in offers:
        url = safe_url(o.url, mailbox)
        if url is None:
            dropped += 1
            continue
        c = canonical(url)
        o.url = c.url if c else url
        kept.append(o)
    return kept, dropped


class EmailAlerts:
    name = "email"

    def __init__(self, host: str, user: str, password: str, folder: str, days: int = 3):
        self.host, self.user, self.password, self.folder = host, user, password, folder
        self.days = days
        # Expéditeurs sans parser vus au dernier passage : domaine → nombre de mails
        self.unknown_senders: Counter[str] = Counter()
        # Pour la santé : domaine → {"last": date du mail le plus récent, "last_offers": offres
        # extraites de ce mail (None si pas de parser)}
        self.sender_stats: dict[str, dict] = {}

    def fetch(self) -> list[Offer]:
        since = date.today() - timedelta(days=self.days)
        offers = []
        self.unknown_senders, self.sender_stats = Counter(), {}
        with MailBox(self.host).login(self.user, self.password, initial_folder=self.folder) as mb:
            for msg in mb.fetch(AND(date_gte=since), mark_seen=False, bulk=True):
                offers += self.parse_message(msg)
        if self.unknown_senders:
            log.info("Expéditeurs sans parser (ignorés) : %s",
                     ", ".join(f"{d} ×{n}" for d, n in self.unknown_senders.most_common()))
        return offers

    def _stat(self, msg, offers: int | None) -> None:
        """Statistiques pour la santé. `offers` None : mail qui ne dit rien sur le parser
        (pas de parser, ou mail de service) → seul « dernier mail reçu » est mis à jour."""
        st = self.sender_stats.setdefault(sender_domain(msg.from_), {"last": msg.date})
        st["last"] = max(st["last"], msg.date)
        if offers is not None and msg.date >= st.get("_alert_date", msg.date):
            st["_alert_date"], st["last_offers"] = msg.date, offers

    def parse_message(self, msg) -> list[Offer]:
        r = route_for(msg.from_)
        if r is None:
            self.unknown_senders[sender_domain(msg.from_)] += 1
            self._stat(msg, None)
            return []
        if not is_alert_sender(msg.from_, r):  # autre mail d'un site connu (notifications…)
            return []
        try:
            got = r.parser(msg.html or "")
        except Exception:
            log.exception("Mail illisible : %s", msg.subject)
            self._stat(msg, 0)
            return []
        got, dropped = publishable(got, self.user)
        if dropped:
            log.warning("%s : %d offre(s) écartée(s), lien contenant l'adresse de la boîte",
                        sender_domain(msg.from_), dropped)
        subject = msg.subject or ""
        service = SERVICE_SUBJECT.search(subject) or (r.subject and not r.subject.search(subject))
        self._stat(msg, None if not got and service else len(got))
        alert = alert_name(subject)
        for o in got:
            o.published_at = msg.date
            o.alert = alert
        log.info("%s : %d offres", sender_domain(msg.from_), len(got))
        return got
