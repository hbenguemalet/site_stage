from pathlib import Path

from jobbot.filters import evaluate
from jobbot.models import Offer
from jobbot.profiles import load

RACINE = Path(__file__).resolve().parents[1]


def profil():
    return load(RACINE / "profiles.yaml", {"lille", "paris", "europe"})[0]


def offre(title, city="paris", loc="Paris", contract="stage", desc=""):
    return Offer("greenhouse", "1", title, "ACME", loc, "https://x/1", desc, contract=contract, city_key=city)


def test_stages_design_acceptes():
    for t in ("Stage Designer graphique", "Stage assistant(e) direction artistique", "Stagiaire styliste textile",
              "Stage médiation culturelle - musée", "Stage Product Designer (UX/UI)", "Design intern - Berlin"):
        assert evaluate(profil(), offre(t)).ok, t


def test_hors_sujet_rejete():
    for t in ("Stage Développeur Full Stack", "Stage Data Engineer", "Stage comptabilité", "Stage Sales Development Representative"):
        assert not evaluate(profil(), offre(t)).ok, t


def test_contrat_alternance_ou_cdi_rejete():
    assert not evaluate(profil(), offre("Designer graphique", contract="cdi")).ok
    assert not evaluate(profil(), offre("Alternance Designer graphique", contract="alternance")).ok


def test_europe_acceptee():
    assert evaluate(profil(), offre("Stage Graphic Designer", city="europe", loc="Berlin, Germany")).ok
