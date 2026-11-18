import json
from datetime import UTC, datetime

from jobbot import site
from jobbot.filters import Verdict
from jobbot.models import Offer

NOW = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)


def offre(url="https://x/1", desc="", title="Stage Designer graphique (H/F)"):
    return Offer("indeed", url[-1], title, "ACME", "Lille (59)", url, desc)


def test_infos_lues_dans_annonce():
    o = offre(desc="Début : septembre 2027. Rythme 3j/2j. Durée du contrat : 24 mois.")
    assert site.infos(o) == ["Début : septembre 2027", "Rythme : 3 j / 2 j", "Durée : 24 mois"]


def test_infos_non_precisees():
    assert all("non précis" in i for i in site.infos(offre()))


def test_update_ecrit_offres_js_et_accumule(tmp_path):
    scfg = {"profil": "p", "dossier": "web", "score_proche": 60}
    site.update("p", [(offre(), Verdict(True, score=75))], scfg, tmp_path, NOW)
    n = site.update("p", [(offre("https://x/2", title="Alternance Compta"), Verdict(True, score=45))], scfg, tmp_path, NOW)
    assert n == 2
    js = (tmp_path / "web" / "offres.js").read_text("utf-8")
    data = json.loads(js[js.index("{"):js.rindex("}") + 1])
    assert [e["url"] for e in data["meilleures"]] == ["https://x/1"]
    assert [e["url"] for e in data["autres"]] == ["https://x/2"]
    assert data["meilleures"][0]["etoile"] is True


def test_purge_des_vieilles_offres(tmp_path):
    scfg = {"dossier": "web", "conserver_jours": 10}
    site.update("p", [(offre(), Verdict(True, score=75))], scfg, tmp_path, NOW)
    later = datetime(2027, 1, 1, tzinfo=UTC)
    assert site.update("p", [], scfg, tmp_path, later) == 0


def test_push_git_quand_active(tmp_path, monkeypatch):
    appels = []

    def faux_run(cmd, **kw):
        appels.append(cmd[3:])
        return type("R", (), {"returncode": 1})()  # diff --cached non vide → il y a quelque chose à pousser

    monkeypatch.setattr(site.subprocess, "run", faux_run)
    scfg = {"dossier": "web", "git_push": True}
    site.update("p", [(offre(), Verdict(True, score=75))], scfg, tmp_path, NOW)
    verbes = [a[0] if a[0] != "-c" else a[4] for a in appels]
    assert verbes == ["add", "diff", "commit", "pull", "push"]
    appels.clear()
    site.update("p", [], scfg, tmp_path, datetime(2026, 11, 19, tzinfo=UTC))  # rien de neuf
    assert appels == []


def test_push_en_erreur_ne_leve_pas(tmp_path, monkeypatch):
    def casse(*a, **k):
        raise OSError("git absent")

    monkeypatch.setattr(site.subprocess, "run", casse)
    assert site.publier(tmp_path, "x") is False


def test_offre_toujours_presente_rafraichie_et_texte_garde(tmp_path):
    scfg = {"dossier": "web", "depot_candidature": "moi/depot"}
    o = offre(desc="Illustrator et InDesign " * 20)
    site.update("p", [(o, Verdict(True, score=75))], scfg, tmp_path, NOW)
    later = datetime(2026, 11, 20, tzinfo=UTC)
    site.update("p", [(offre(), Verdict(True, score=75))], scfg, tmp_path, later)  # revue sans texte
    store = json.loads((tmp_path / "data" / "site_p.json").read_text("utf-8"))
    e = store["https://x/1"]
    assert e["vu"].startswith("2026-11-20") and e["premiere"].startswith("2026-11-18") and "Illustrator" in e["texte"]
    js = (tmp_path / "web" / "offres.js").read_text("utf-8")
    assert '"texte"' not in js and '"candidature": "moi/depot"' in js
