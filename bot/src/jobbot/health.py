"""Santé du bot : alertes dans #bot-logs, une seule fois par problème, puis « rétabli ».

Problèmes suivis (clé → message) :
- muet:<domaine>    un expéditeur attendu n'a rien envoyé depuis N heures (alerte expirée,
                    site en panne, mails classés ailleurs…) ;
- zero:<domaine>    le dernier mail d'un site qui a un parser donne 0 offre (format changé ?) ;
- source:<nom>      une source a planté (IMAP injoignable, API en erreur…) ;
- webhook:<profil>  variable du salon Discord vide dans .env ;
- discord:<profil>  des envois Discord ont échoué ;
- plantage          le bot entier a planté.

L'état est dans SQLite : à chaque passage complet, on compare les problèmes du moment aux
problèmes ouverts. Nouveau → « ⚠️ », disparu → « ✅ rétabli ». Pas de spam entre les deux.
"""

import logging
import sqlite3
from datetime import UTC, datetime

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS senders (
    domain       TEXT PRIMARY KEY,
    last_mail    TEXT,               -- date (UTC, ISO) du mail le plus récent vu
    last_offers  INTEGER,            -- offres extraites de ce mail (NULL : pas de parser)
    first_seen   TEXT NOT NULL       -- 1er passage où le domaine est suivi (référence si jamais vu)
);
CREATE TABLE IF NOT EXISTS problems (
    key      TEXT PRIMARY KEY,
    message  TEXT NOT NULL,
    since    TEXT NOT NULL
);
"""


def _iso(d: datetime) -> str:
    return (d if d.tzinfo else d.replace(tzinfo=UTC)).astimezone(UTC).isoformat(timespec="seconds")


def domain_matches(domain: str, expected: str) -> bool:
    return domain == expected or domain.endswith("." + expected)


class Health:
    def __init__(self, db: sqlite3.Connection, now: datetime | None = None):
        self.db, self.now = db, now or datetime.now(UTC)
        self.db.executescript(SCHEMA)

    # --- expéditeurs ---------------------------------------------------------------
    def record_senders(self, stats: dict[str, dict]) -> None:
        """stats : domaine → {"last": datetime du mail le plus récent, "last_offers": offres du
        dernier mail d'alerte}. Sans "last_offers" (pas de parser, mails de service seulement),
        on garde la valeur connue."""
        with self.db:
            for domain, st in stats.items():
                last = _iso(st["last"])
                row = self.db.execute("SELECT last_mail FROM senders WHERE domain=?", (domain,)).fetchone()
                offers = st.get("last_offers")
                if row is None:
                    self.db.execute("INSERT INTO senders VALUES (?,?,?,?)",
                                    (domain, last, offers, _iso(self.now)))
                elif row[0] is None or last >= row[0]:
                    self.db.execute("UPDATE senders SET last_mail=?, last_offers=COALESCE(?, last_offers)"
                                    " WHERE domain=?", (last, offers, domain))

    def sender_problems(self, expected: list[str], max_hours: int) -> dict[str, str]:
        problems = {}
        rows = self.db.execute("SELECT domain, last_mail, last_offers, first_seen FROM senders").fetchall()
        for exp in expected:
            mine = [r for r in rows if domain_matches(r[0], exp)]
            if not mine:  # jamais vu : on commence à compter à partir de maintenant
                with self.db:
                    self.db.execute("INSERT OR IGNORE INTO senders (domain, first_seen) VALUES (?,?)",
                                    (exp, _iso(self.now)))
                continue
            ref = max(r[1] or r[3] for r in mine)
            hours = (self.now - datetime.fromisoformat(ref)).total_seconds() / 3600
            if hours > max_hours:
                quand = "jamais reçu de mail" if all(r[1] is None for r in mine) else "aucun mail"
                problems[f"muet:{exp}"] = (f"{exp} : {quand} depuis {hours:.0f} h "
                                           "(alerte expirée ou en pause ? site en panne ?)")
        for domain, last, offers, _ in rows:
            if last and offers == 0:
                problems[f"zero:{domain}"] = (f"{domain} : le dernier mail ne donne aucune offre "
                                              "(le format du mail a sans doute changé : parser à revoir)")
        return problems

    # --- problèmes -----------------------------------------------------------------
    def open_problems(self) -> dict[str, str]:
        return dict(self.db.execute("SELECT key, message FROM problems"))

    def update(self, current: dict[str, str]) -> list[str]:
        """Remplace l'état par `current` (tous les problèmes d'un passage complet).
        Rend les messages à publier : nouveaux problèmes et problèmes rétablis."""
        before, out = self.open_problems(), []
        with self.db:
            for key, msg in current.items():
                if key not in before:
                    self.db.execute("INSERT INTO problems VALUES (?,?,?)", (key, msg, _iso(self.now)))
                    out.append(f"⚠️ **Problème** : {msg}")
            for key, msg in before.items():
                if key not in current:
                    self.db.execute("DELETE FROM problems WHERE key=?", (key,))
                    out.append(f"✅ **Rétabli** : {msg}")
        return out

    def add(self, key: str, msg: str) -> list[str]:
        """Ouvre un problème sans toucher aux autres (ex. plantage en cours de passage)."""
        if key in self.open_problems():
            return []
        with self.db:
            self.db.execute("INSERT INTO problems VALUES (?,?,?)", (key, msg, _iso(self.now)))
        return [f"⚠️ **Problème** : {msg}"]


def publish(messages: list[str], webhook: str) -> None:
    """Envoie les messages dans #bot-logs ; sans webhook, ils restent dans le journal."""
    if not messages:
        return
    for m in messages:
        log.warning("Santé : %s", m)
    if not webhook:
        log.warning("DISCORD_LOGS_WEBHOOK_URL vide : alertes de santé seulement dans le journal")
        return
    from jobbot.notifiers import discord
    try:
        discord.post(webhook, {"username": "jobbot · santé", "content": "\n".join(messages)[:2000]})
    except Exception:
        log.exception("Envoi dans #bot-logs impossible")
