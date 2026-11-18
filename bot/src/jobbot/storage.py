"""Mémoire du bot (SQLite) : quelles offres ont déjà été vues / notifiées, par profil."""

import hashlib
import re
import sqlite3
from pathlib import Path

from jobbot.filters import norm
from jobbot.models import Offer
from jobbot.sources.email_alerts.canonical import canonical

# Profil auquel sont rattachées les offres d'avant le multi-profils (base v0)
PROFIL_HISTORIQUE = "stage-design"

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    profile      TEXT NOT NULL,
    source       TEXT NOT NULL,
    source_id    TEXT NOT NULL,
    fingerprint  TEXT NOT NULL,
    title        TEXT,
    company      TEXT,
    city         TEXT,
    url          TEXT,
    first_seen   TEXT DEFAULT (datetime('now')),
    notified     INTEGER DEFAULT 0,
    PRIMARY KEY (profile, source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_profile_fp ON offers(profile, fingerprint);
CREATE INDEX IF NOT EXISTS idx_profile_url ON offers(profile, url);
"""


def _clean(s: str | None) -> str:
    s = norm(s)
    s = re.sub(r"\(.*?\)", " ", s)  # (H/F), (F/H/X)…
    s = re.sub(r"\b[hf]\s*/\s*[hf](\s*/\s*[xn])?\b", " ", s)  # H/F sans parenthèses
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())


def canonical_url(o: Offer) -> str | None:
    """Lien canonique si le site est reconnu (sinon None : un lien générique ne dédoublonne pas)."""
    c = canonical(o.url or "")
    return c.url if c else None


def fingerprint(o: Offer) -> str:
    """Même titre + même entreprise + même ville = même offre, quelle que soit la source."""
    key = f"{_clean(o.title)}|{_clean(o.company)}|{o.city_key}"
    return hashlib.sha1(key.encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path = "data/jobs.db"):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self._migrate()

    def _migrate(self) -> None:
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        cols = [r[1] for r in self.db.execute("PRAGMA table_info(offers)")]
        if version == 0 and cols and "profile" not in cols:
            # v0 → v1 : la table n'avait pas de profil. Les offres déjà vues appartiennent
            # au profil historique (Data/SQL), pour qu'il ne les reçoive pas une 2e fois.
            with self.db:
                self.db.execute("ALTER TABLE offers RENAME TO offers_v0")
                self.db.executescript(SCHEMA)
                self.db.execute(
                    "INSERT INTO offers (profile, source, source_id, fingerprint, title, company,"
                    " city, url, first_seen, notified) SELECT ?, source, source_id, fingerprint,"
                    " title, company, city, url, first_seen, notified FROM offers_v0",
                    (PROFIL_HISTORIQUE,),
                )
                self.db.execute("DROP TABLE offers_v0")
                self.db.execute("DROP INDEX IF EXISTS idx_fp")
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA user_version = 1")
        self.db.commit()

    def is_new(self, profile: str, o: Offer) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM offers WHERE profile=? AND ((source=? AND source_id=?) OR fingerprint=?"
            " OR url=?) LIMIT 1",
            (profile, o.source, o.source_id, fingerprint(o), canonical_url(o)),
        ).fetchone()
        return row is None

    def save(self, profile: str, o: Offer, notified: bool) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO offers"
            "(profile, source, source_id, fingerprint, title, company, city, url, notified) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (profile, o.source, o.source_id, fingerprint(o), o.title, o.company, o.city_key,
             o.url, int(notified)),
        )
        self.db.commit()

    def count(self, profile: str | None = None) -> int:
        if profile is None:
            return self.db.execute("SELECT COUNT(*) FROM offers").fetchone()[0]
        return self.db.execute("SELECT COUNT(*) FROM offers WHERE profile=?", (profile,)).fetchone()[0]

    def purge(self, days: int = 90) -> None:
        self.db.execute("DELETE FROM offers WHERE first_seen < datetime('now', ?)", (f"-{days} days",))
        self.db.commit()
