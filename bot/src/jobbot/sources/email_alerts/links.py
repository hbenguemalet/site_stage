"""Liens publiés sur Discord : sans paramètres de suivi et sans jamais l'adresse de la boîte.

Les sites glissent souvent l'adresse du destinataire dans leurs liens : en clair, encodée
dans l'URL (%40), en base64 (HelloWork), ou sous une autre forme. Gmail ignore les points
de la partie locale, et Indeed connaît la boîte sans points : on compare donc sans points.
"""

import base64
import binascii
import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

# Paramètres de suivi retirés des URL (comparaison en minuscules)
TRACKING = re.compile(
    r"^(utm_.*|mc_[ce]id|fbclid|gclid|dclid|msclkid|xtor|at_.*|trk.*|tracking.*|ref|refid"
    r"|from|src|source|campaign|cmp|email|e|mail|recipient|uid|user_?id|token|hash|sig)$",
    re.IGNORECASE,
)
B64_TOKEN = re.compile(r"[A-Za-z0-9+/_-]{16,}={0,2}")


def _flat(s: str) -> str:
    """Minuscules, %-décodé (plusieurs niveaux), sans points : forme de comparaison."""
    for _ in range(3):
        s = unquote(s)
    return s.lower().replace(".", "")


def _b64_decodings(url: str):
    """Textes cachés en base64 dans l'URL. Le segment peut être collé à un préfixe
    (« clic/… ») : on essaie les 4 alignements, et les deux alphabets (standard et URL)."""
    for tok in B64_TOKEN.findall(unquote(url)):
        for start in range(4):
            part = tok[start:].rstrip("=")
            part += "=" * (-len(part) % 4)
            for decode in (base64.urlsafe_b64decode, base64.b64decode):
                try:
                    yield decode(part).decode("utf-8", "ignore")
                except (binascii.Error, ValueError):
                    pass


def contains_mailbox(url: str, mailbox: str) -> bool:
    """Vrai si l'URL contient l'adresse de la boîte (ou sa partie locale), sous une forme
    quelconque : en clair, avec ou sans points, %-encodée, ou en base64."""
    if not mailbox:
        return False
    local = _flat(mailbox.split("@", 1)[0])
    if len(local) < 6:  # partie locale trop courte : risque de faux positifs, on compare l'adresse
        local = _flat(mailbox)
    if local in _flat(url):
        return True
    return any(local in _flat(txt) for txt in _b64_decodings(url))


def strip_tracking(url: str) -> str:
    """Retire les paramètres de suivi et le fragment, garde les autres paramètres."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not TRACKING.match(k)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def safe_url(url: str, mailbox: str) -> str | None:
    """URL publiable, ou None si elle trahit l'adresse de la boîte même après nettoyage."""
    if not url.startswith(("https://", "http://")):
        return None
    cleaned = strip_tracking(url)
    return None if contains_mailbox(cleaned, mailbox) else cleaned
