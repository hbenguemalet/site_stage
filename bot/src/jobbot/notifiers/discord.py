"""Envoi des offres sur Discord via webhook : une carte (« embed ») par offre, plusieurs
cartes par message, triées par score ; un récapitulatif en liste au-delà d'un seuil."""

import re
import time
from datetime import UTC

import httpx

from jobbot.filters import Verdict
from jobbot.models import Offer
from jobbot.profiles import Profile

LIBELLES_CONTRAT = {"cdi": "CDI", "cdd": "CDD", "stage": "Stage", "alternance": "Alternance",
                    "freelance": "Freelance", "interim": "Intérim"}
LIBELLES_SOURCE = {
    "indeed": "Indeed", "hellowork": "HelloWork", "linkedin": "LinkedIn",
    "makesense": "Jobs that make sense", "coordinationsud": "Coordination SUD",
    "lesjeudis": "Les Jeudis", "labonnealternance": "La bonne alternance", "adzuna": "Adzuna",
    "greenhouse": "Page carrières (Greenhouse)", "lever": "Page carrières (Lever)",
    "ashby": "Page carrières (Ashby)", "workable": "Page carrières (Workable)",
    "recruitee": "Page carrières (Recruitee)", "smartrecruiters": "Page carrières (SmartRecruiters)",
}

# Couleur de la carte et pastille selon le score
SCORE_VERT, SCORE_JAUNE = 70, 50
COULEURS = {"vert": 0x2ECC71, "jaune": 0xF1C40F, "gris": 0x95A5A6}
PASTILLES = {"vert": "🟢", "jaune": "🟡", "gris": "⚪"}
# Affichage du score en tête de carte : "pastille" (🟢 72/100) ou "barre" (▰▰▰▰▰▰▰▱▱▱ 72)
VARIANTE_SCORE = "pastille"

# Limites Discord
MAX_EMBEDS, MAX_TOTAL, MAX_TITRE, MAX_DESCRIPTION, MAX_FOOTER = 10, 6000, 256, 4096, 2048
EXTRAIT = 200            # caractères de l'extrait de l'annonce
RECAP_PAR_MESSAGE = 15   # lignes au plus par carte de récapitulatif

LIEUX_DIT = {"titre": "dans le titre", "description": "dans l'annonce", "fiche": "dans l'annonce"}


def niveau(score: int) -> str:
    return "vert" if score >= SCORE_VERT else "jaune" if score >= SCORE_JAUNE else "gris"


def badge(score: int) -> str:
    """Score en tête de carte, selon VARIANTE_SCORE."""
    if VARIANTE_SCORE == "barre":
        plein = round(max(0, min(100, score)) / 10)
        return f"`{'▰' * plein}{'▱' * (10 - plein)}` **{score}**"
    return f"{PASTILLES[niveau(score)]} **{score}**/100"


def source_label(source: str) -> str:
    return LIBELLES_SOURCE.get(source, source[:1].upper() + source[1:])


def md(s: str | None) -> str:
    """Texte venant d'une offre, sans mise en forme Discord involontaire."""
    return re.sub(r"([\\*_~`|>#\[\]])", r"\\\1", " ".join((s or "").split()))


def cut(s: str, n: int) -> str:
    """Coupe à n caractères au plus, sur une fin de mot, avec « … »."""
    if len(s) <= n:
        return s
    s = s[:n - 1]
    return (s.rsplit(" ", 1)[0] if " " in s[n // 2:] else s).rstrip(" ,;:.\\") + "…"


def alert_label(alert: str) -> str:
    """« data OR sql (Paris (75)) » → « data OR sql » (la ville est déjà sur la carte)."""
    return re.sub(r"\s*\((?:[^()]|\([^()]*\))*\)\s*$", "", alert).strip() or alert


def found_in(v: Verdict, o: Offer | None = None) -> str:
    """Pourquoi l'offre est là, lisible : « *Développeur* dans le titre · *SQL* dans l'annonce »."""
    groups: dict[str, list[str]] = {}
    parts = []
    texts = v.matched_text if len(v.matched_text) == len(v.matched_on) else [""] * len(v.matched_on)
    for m, text in zip(v.matched_on, texts, strict=True):
        kind, _, what = m.partition(":")
        if kind == "alerte":
            site = f" {source_label(o.source)}" if o else " du site"
            parts.append(f"d'après l'alerte{site} “{md(alert_label(text or what))}”")
            continue
        words = groups.setdefault(LIEUX_DIT.get(kind, kind), [])
        word = text or what
        if word.lower() not in {w.lower() for w in words}:
            words.append(word)
    parts = [f"{', '.join(f'*{md(w)}*' for w in words)} {lieu}" for lieu, words in groups.items()] + parts
    return " · ".join(parts)


def recap_mark(v: Verdict) -> str:
    """Petit repère dans le récapitulatif quand le titre ne contient pas le mot-clé."""
    kinds = {m.partition(":")[0] for m in v.matched_on}
    return "📄 " if "fiche" in kinds else "🔔 " if "alerte" in kinds else ""


def contrat_of(o: Offer, v: Verdict) -> str | None:
    return LIBELLES_CONTRAT.get(v.contrat or "") or o.contract


def lieu(o: Offer) -> str:
    """Lieu court : « Ville de Paris, Île-de-France, France » (LinkedIn) → « Paris »."""
    parts = [x.strip() for x in (o.location or "").split(",") if x.strip()]
    if len(parts) > 1 and parts[-1].lower() == "france":
        # sans le pays ni l'adresse (« 4 Pl. Jussieu ») ; LinkedIn : la ville, sans la région
        parts = [x for x in parts[:-1] if not re.match(r"\d{1,4}\b", x)][:1] or parts[:1]
    court = re.sub(r"^ville de ", "", ", ".join(parts), flags=re.IGNORECASE)
    return court or (o.city_key or "").capitalize()


def infos(o: Offer, v: Verdict) -> str:
    """🏢 Entreprise · 📍 Lieu · 📄 Contrat · 💰 Salaire (ce qui manque est sauté)."""
    items = [("🏢", o.company, 60), ("📍", lieu(o), 60), ("📄", contrat_of(o, v), 30), ("💰", o.salary, 60)]
    return " · ".join(f"{icone} {cut(md(val), n)}" for icone, val, n in items if val and val.strip())


def build_embed(o: Offer, v: Verdict) -> dict:
    lines = [badge(v.score)]
    if info := infos(o, v):
        lines.append(info)
    if o.description.strip():
        lines.append(f"> {cut(md(o.description), EXTRAIT)}")
    if v.matched_on:
        lines.append(f"-# 🔎 {found_in(v, o)}")
    embed = {
        "title": cut(f"{'⭐ ' if v.etoile else ''}{' '.join(o.title.split())}", MAX_TITRE),
        "url": o.url,
        "color": COULEURS[niveau(v.score)],
        "description": cut("\n".join(lines), MAX_DESCRIPTION),
        "footer": {"text": cut(source_label(o.source), MAX_FOOTER)},
    }
    if o.published_at:
        d = o.published_at
        embed["timestamp"] = (d if d.tzinfo else d.astimezone()).astimezone(UTC).isoformat()
    return embed


def embed_size(e: dict) -> int:
    """Caractères comptés par Discord dans la limite de 6000 par message."""
    return (len(e.get("title", "")) + len(e.get("description", "")) + len(e.get("footer", {}).get("text", ""))
            + len(e.get("author", {}).get("name", ""))
            + sum(len(f["name"]) + len(f["value"]) for f in e.get("fields", [])))


def sender(p: Profile) -> dict:
    """Nom (et avatar, s'il est réglé) affichés comme expéditeur du message."""
    out = {"username": f"Offres · {p.nom}"[:80]}
    if p.avatar:
        out["avatar_url"] = p.avatar
    return out


def pack(embeds: list[tuple[dict, list]]) -> list[tuple[list[dict], list]]:
    """Regroupe les cartes en messages de ≤ 10 cartes et ≤ 6000 caractères."""
    out: list[tuple[list[dict], list]] = []
    size = 0
    for e, items in embeds:
        n = embed_size(e)
        if not out or len(out[-1][0]) >= MAX_EMBEDS or size + n > MAX_TOTAL:
            out.append(([], []))
            size = 0
        out[-1][0].append(e)
        out[-1][1].extend(items)
        size += n
    return out


def build_messages(items: list[tuple[Offer, Verdict]], p: Profile) -> list[tuple[dict, list]]:
    """Messages webhook (une carte par offre, triées par score) et les offres de chacun."""
    items = sorted(items, key=lambda ov: ov[1].score, reverse=True)
    return [({**sender(p), "embeds": embeds}, chunk)
            for embeds, chunk in pack([(build_embed(o, v), [(o, v)]) for o, v in items])]


def build_payload(o: Offer, p: Profile, v: Verdict) -> dict:
    """Message d'une seule offre."""
    return build_messages([(o, v)], p)[0][0]


def recap_line(o: Offer, v: Verdict) -> str:
    titre = cut(md(o.title.replace("[", "(").replace("]", ")")), 120)
    details = [cut(md(o.company), 50), cut(md(lieu(o)), 40),
               md(contrat_of(o, v)), source_label(o.source)]
    return (f"{PASTILLES[niveau(v.score)]} **{v.score}** · {'⭐ ' if v.etoile else ''}{recap_mark(v)}"
            f"[{titre}]({o.url})\n-# {' · '.join(d for d in details if d)}")


def build_recap(items: list[tuple[Offer, Verdict]], p: Profile) -> list[tuple[dict, list]]:
    """Récapitulatif en liste (offres triées par score), découpé en cartes de
    ≤ RECAP_PAR_MESSAGE lignes et ≤ 4096 caractères ; une carte par message."""
    items = sorted(items, key=lambda ov: ov[1].score, reverse=True)
    chunks: list[list[tuple[str, tuple]]] = []
    for ov in items:
        line = recap_line(*ov)
        size = sum(len(x) + 1 for x, _ in chunks[-1]) if chunks else 0
        if not chunks or len(chunks[-1]) >= RECAP_PAR_MESSAGE or size + len(line) > MAX_DESCRIPTION:
            chunks.append([])
        chunks[-1].append((line, ov))
    out = []
    for i, chunk in enumerate(chunks):
        part = f" ({i + 1}/{len(chunks)})" if len(chunks) > 1 else ""
        best = chunk[0][1][1].score
        embed = {
            "title": f"📋 {len(items)} nouvelles offres{part}",
            "description": "\n".join(line for line, _ in chunk),
            "color": COULEURS[niveau(best)],
            "footer": {"text": "Triées par pertinence"},
        }
        out.append(({**sender(p), "embeds": [embed]}, [ov for _, ov in chunk]))
    return out


def post(webhook_url: str, payload: dict, client: httpx.Client | None = None) -> None:
    """POST d'un message, en respectant la limite de débit de Discord."""
    client = client or httpx.Client(timeout=15)
    for _ in range(5):
        r = client.post(webhook_url, json=payload)
        if r.status_code == 429:  # limite de débit Discord
            time.sleep(float(r.json().get("retry_after", 2)))
            continue
        r.raise_for_status()
        time.sleep(1)  # reste sous ~30 messages/min
        return
    raise RuntimeError("Discord : trop de refus (429)")
