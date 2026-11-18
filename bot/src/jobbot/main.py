"""Point d'entrée : collecte (une fois) → pour chaque profil : filtre → dédoublonnage → notification."""

import argparse
import logging
from collections import Counter

from jobbot.config import ROOT, load, require
from jobbot.filters import CityResolver, evaluate
from jobbot.health import Health, publish
from jobbot.notifiers import discord
from jobbot.profiles import Profile
from jobbot.profiles import load as load_profiles
from jobbot.storage import Store, canonical_url, fingerprint

log = logging.getLogger("jobbot")


def build_sources(cfg: dict, env: dict) -> list:
    sources = []
    if cfg["sources"].get("email_alerts"):
        require(env, "IMAP_HOST", "IMAP_USER", "IMAP_PASSWORD", "IMAP_FOLDER")
        from jobbot.sources.email_alerts import EmailAlerts
        days = (cfg.get("email_alerts") or {}).get("jours", 3)
        sources.append(EmailAlerts(env["IMAP_HOST"], env["IMAP_USER"], env["IMAP_PASSWORD"],
                                   env["IMAP_FOLDER"], days))
    if cfg["sources"].get("labonnealternance"):
        if not env.get("LBA_API_KEY"):
            log.error("sources.labonnealternance activée mais LBA_API_KEY vide dans .env : source ignorée")
        else:
            from jobbot.sources.labonnealternance import LaBonneAlternance
            lba = cfg.get("labonnealternance") or {}
            sources.append(LaBonneAlternance(env["LBA_API_KEY"], cfg["villes"], lba.get("romes") or [],
                                             lba.get("rayon_km", 30)))
    if cfg["sources"].get("carrieres"):
        from jobbot.sources.careers import Careers
        car = cfg.get("carrieres") or {}
        sources.append(Careers(car.get("entreprises") or [], ROOT / "data" / "carrieres.stamp",
                               car.get("intervalle_minutes", 60)))
    return sources


def collect(cfg: dict, env: dict, partial: bool = False) -> tuple[list, list, dict]:
    """Offres de toutes les sources, les sources (pour leurs remarques : expéditeurs inconnus,
    statistiques) et les sources en échec (nom → message). `partial` (--dry-run, --seed,
    --profil) : on interroge tout, sans marquer le passage des sources espacées (carrières)."""
    offers, sources, failures = [], build_sources(cfg, env), {}
    for src in sources:
        if partial and hasattr(src, "stamp"):
            src.stamp = None
        try:
            got = src.fetch()
            log.info("%s : %d offres récupérées", src.name, len(got))
            offers += got
        except Exception as e:
            log.exception("Source %s en échec, on continue avec les autres", src.name)
            failures[src.name] = f"source {src.name} en échec : {type(e).__name__}"
    return offers, sources, failures


def print_unknown_senders(sources: list) -> None:
    """--dry-run : signale les sites qui envoient des mails mais n'ont pas encore de parser."""
    unknown = sum((Counter(getattr(s, "unknown_senders", None) or {}) for s in sources), Counter())
    if not unknown:
        return
    print("\n===== Expéditeurs sans parser (mails ignorés) =====")
    for domain, n in unknown.most_common():
        print(f"  {domain} : {n} mail(s)")


def select(p: Profile, offers: list, store: Store):
    """Offres nouvelles et pertinentes pour le profil, + rejetées (offre, raison)."""
    new, rejected, seen_now = [], [], set()
    for o in offers:
        # même offre reçue par 2 sites / 2 mails : même id, même empreinte ou même lien canonique
        keys = {(o.source, o.source_id), fingerprint(o), ("url", canonical_url(o) or id(o))}
        if keys & seen_now:
            continue
        seen_now |= keys
        v = evaluate(p, o)
        if not v.ok:
            rejected.append((o, v.raison))
            continue
        if not store.is_new(p.id, o):
            continue
        new.append((o, v))
    new.sort(key=lambda ov: ov[1].score, reverse=True)  # les plus pertinentes d'abord
    return new, rejected


def select_all(p: Profile, offers: list) -> list:
    """Toutes les offres pertinentes du moment (nouvelles ou non), pour la page web."""
    out, seen_now = [], set()
    for o in offers:
        keys = {(o.source, o.source_id), fingerprint(o), ("url", canonical_url(o) or id(o))}
        if keys & seen_now:
            continue
        seen_now |= keys
        v = evaluate(p, o)
        if v.ok:
            out.append((o, v))
    return out


def notify(p: Profile, new: list, webhook: str, cfg: dict, store: Store) -> tuple[int, int]:
    """Envoie les offres du profil : quelques cartes par message (≤ 10, triées par score), ou un
    récapitulatif en liste au-delà du seuil. Une offre n'est enregistrée comme vue que si son
    message est bien parti. Rend (envoyées, échecs)."""
    ncfg = cfg["notifications"]
    seuil = p.recap_a_partir_de or ncfg.get("recap_a_partir_de", 8)
    use_discord = ncfg.get("discord")
    if len(new) >= seuil:
        log.info("[%s] %d offres ≥ %d : récapitulatif", p.id, len(new), seuil)
        messages = discord.build_recap(new[:ncfg.get("max_par_recap", 60)], p)
    else:
        messages = discord.build_messages(new[:ncfg.get("max_par_execution", 30)], p)
    sent = failed = 0
    for i, (payload, chunk) in enumerate(messages):
        try:
            if use_discord:
                discord.post(webhook, payload)
            for o, _ in chunk:
                store.save(p.id, o, notified=True)  # enregistrée seulement si l'envoi a réussi
            sent += len(chunk)
        except Exception:
            failed += len(chunk)
            log.exception("[%s] message %d/%d non envoyé (%d offres)", p.id, i + 1, len(messages), len(chunk))
    if len(new) > sent + failed:
        log.warning("[%s] %d offres en attente : la suite au prochain passage", p.id, len(new) - sent - failed)
    return sent, failed


def run(seed: bool = False, dry_run: bool = False, profil: str | None = None,
        db_path: str = "data/jobs.db") -> int:
    cfg, env = load()
    profiles = load_profiles(ROOT / "profiles.yaml", set(cfg["villes"]))
    if profil:
        profiles = [p for p in profiles if p.id == profil]
        if not profiles:
            raise SystemExit(f"Profil inconnu : {profil}")
    profiles = [p for p in profiles if p.actif]
    store, cities = Store(db_path), CityResolver(cfg["villes"])
    # Santé suivie seulement sur les passages complets (pas --dry-run, --seed ni --profil)
    health = Health(store.db) if not (dry_run or seed or profil) else None
    problems: dict[str, str] = {}

    offers, sources, failures = collect(cfg, env, partial=bool(dry_run or seed or profil))
    if dry_run:
        print_unknown_senders(sources)
    if health:
        for src in sources:
            health.record_senders(getattr(src, "sender_stats", None) or {})
        sante = cfg.get("sante") or {}
        problems.update(health.sender_problems(sante.get("expediteurs") or [],
                                               sante.get("silence_max_heures", 48)))
        problems.update({f"source:{k}": v for k, v in failures.items()})
    for o in offers:
        o.city_key = cities.city_of(o)

    total = 0
    for p in profiles:
        new, rejected = select(p, offers, store)
        log.info("[%s] %d nouvelles offres pertinentes", p.id, len(new))

        if dry_run:
            print(f"\n===== {p.nom} ({p.id}) : {len(new)} retenue(s) =====")
            for o, v in new:
                print(f"[{v.score:>3}] {'⭐ ' if v.etoile else ''}[{o.city_key}] {o.title} — "
                      f"{o.company or '?'} — {o.location} — {v.contrat or '?'} — {o.url}\n"
                      f"    trouvé : {discord.found_in(v, o)}  [{', '.join(v.matched_on)}]\n"
                      f"    score : {', '.join(v.score_detail)}")
            if profil:  # vue détaillée d'un seul profil : on montre aussi les rejets
                print(f"----- rejetées : {len(rejected)} -----")
                for o, raison in rejected:
                    print(f"  ✗ {o.title[:70]} — {o.location} → {raison}")
            total += len(new)
            continue

        scfg = cfg.get("site") or {}
        if scfg.get("profil") == p.id and not dry_run:
            from jobbot import site
            n = site.update(p.id, select_all(p, offers), scfg, ROOT)
            log.info("[%s] page web : %d offres publiées", p.id, n)

        if seed:
            for o, _ in new:
                store.save(p.id, o, notified=False)
            log.info("[%s] amorçage : %d offres enregistrées sans notification (total profil : %d)",
                     p.id, len(new), store.count(p.id))
            total += len(new)
            continue

        webhook = env.get(p.webhook, "")
        if cfg["notifications"].get("discord") and not webhook:
            log.error("[%s] variable %s vide dans .env : profil ignoré", p.id, p.webhook)
            problems[f"webhook:{p.id}"] = f"profil {p.id} : variable {p.webhook} vide dans .env"
            continue
        sent, failed = notify(p, new, webhook, cfg, store)
        log.info("[%s] %d offres envoyées", p.id, sent)
        if failed:
            problems[f"discord:{p.id}"] = f"profil {p.id} : {failed} offre(s) non envoyée(s) sur Discord"
        total += sent
    if health:
        publish(health.update(problems), env.get("DISCORD_LOGS_WEBHOOK_URL", ""))
    return total


def main() -> None:
    ap = argparse.ArgumentParser(description="Bot offres d'emploi multi-profils (Discord)")
    ap.add_argument("--seed", action="store_true", help="remplit la base sans notifier (1er lancement)")
    ap.add_argument("--dry-run", action="store_true", help="affiche les offres sans notifier ni enregistrer")
    ap.add_argument("--profil", help="ne traiter qu'un profil (avec --dry-run : montre aussi les rejets)")
    ap.add_argument("--apercu-discord", action="store_true",
                    help="affiche le JSON des messages Discord d'un profil (--profil), sans rien envoyer")
    ap.add_argument("--vers-test", action="store_true",
                    help="avec --apercu-discord : envoie l'aperçu sur le salon de test (DISCORD_WEBHOOK_TEST)")
    ap.add_argument("--variante", choices=["pastille", "barre"],
                    help="avec --apercu-discord : affichage du score à essayer")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx journalise chaque URL appelée en INFO : celle du webhook Discord est un secret
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if a.apercu_discord:
        apercu_discord(a.profil, a.vers_test, a.variante)
        return
    if a.vers_test or a.variante:
        ap.error("--vers-test et --variante vont avec --apercu-discord")
    try:
        run(seed=a.seed, dry_run=a.dry_run, profil=a.profil)
    except Exception as e:
        if not (a.seed or a.dry_run or a.profil):
            report_crash(e)
        raise


def apercu_discord(profil: str | None, vers_test: bool, variante: str | None) -> None:
    from jobbot import apercu

    cfg, env = load()
    profiles = {p.id: p for p in load_profiles(ROOT / "profiles.yaml", set(cfg["villes"]))}
    if profil not in profiles:
        raise SystemExit(f"--apercu-discord demande --profil parmi : {', '.join(profiles)}")
    if variante:
        discord.VARIANTE_SCORE = variante
    apercu.run(profiles[profil], cfg, env, vers_test)


def report_crash(e: Exception, db_path: str = "data/jobs.db") -> None:
    """Le bot a planté : alerte dans #bot-logs (une fois ; « rétabli » au prochain passage réussi)."""
    try:
        _, env = load()
        msgs = Health(Store(db_path).db).add("plantage", f"le bot a planté : {type(e).__name__}: {e}"[:300])
        publish(msgs, env.get("DISCORD_LOGS_WEBHOOK_URL", ""))
    except Exception:
        log.exception("Impossible de signaler le plantage")


if __name__ == "__main__":
    main()
