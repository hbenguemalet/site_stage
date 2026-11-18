"""Outils partagés par les parsers d'alertes e-mail."""

import hashlib

from jobbot.filters import norm


def stable_id(*parts: str | None) -> str:
    """Identifiant stable quand le mail ne fournit qu'un lien de suivi (différent à chaque envoi)."""
    key = "|".join(norm(p).strip() for p in parts)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def card_lines(link, min_lines: int, max_up: int = 8) -> list[str]:
    """Textes de la « carte » d'offre : on remonte depuis le lien du titre jusqu'au
    premier conteneur qui contient au moins `min_lines` textes."""
    node = link
    for _ in range(max_up):
        node = node.parent
        if node is None:
            break
        lines = list(node.stripped_strings)
        if len(lines) >= min_lines:
            return lines
    return []
