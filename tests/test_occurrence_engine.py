from datetime import date, datetime, timedelta

import pytest

from zelploie.models import EtatCourant
from zelploie.planning.occurrence_engine import (
    ensure_occurrences_materialized,
    generate_occurrences_for_date,
    load_schedule_template,
    resolve_current_state,
    temps_restant,
)
from zelploie.storage import local_db


@pytest.fixture(scope="module")
def template():
    return load_schedule_template()


@pytest.fixture()
def conn(tmp_path):
    return local_db.connect(tmp_path / "test.db")


def test_template_loads_all_days(template):
    jours = {b.jour_semaine.value for b in template}
    assert jours == {"lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"}
    assert len(template) == 122


def test_monday_week_a_uses_group_a_variant(template):
    # 7 septembre 2026 (lundi) = semaine A (reference confirmee par Zeli).
    occs = generate_occurrences_for_date(date(2026, 9, 7), template)
    noms = {o.nom_activite for o in occs}
    assert "EL47 TP1 (groupe A)" in noms
    assert "IF40 TP1 (groupe B)" not in noms
    # 21 lignes de gabarit pour lundi, dont 1 paire A/B qui se resout a 1 seule -> 20.
    assert len(occs) == 20


def test_monday_week_b_uses_group_b_variant(template):
    # Semaine suivante (14 septembre 2026, lundi) = semaine B.
    occs = generate_occurrences_for_date(date(2026, 9, 14), template)
    noms = {o.nom_activite for o in occs}
    assert "IF40 TP1 (groupe B)" in noms
    assert "EL47 TP1 (groupe A)" not in noms
    assert len(occs) == 20


def test_thursday_week_a_uses_group_a_variant(template):
    # 10 septembre 2026 (jeudi) tombe dans la meme semaine ISO que le
    # lundi 7 (semaine A).
    occs = generate_occurrences_for_date(date(2026, 9, 10), template)
    noms = {o.nom_activite for o in occs}
    assert "SY45 TP1 (groupe A)" in noms
    assert "EL48 TP2 (groupe B)" not in noms
    assert len(occs) == 17


def test_thursday_week_b_uses_group_b_variant(template):
    occs = generate_occurrences_for_date(date(2026, 9, 17), template)
    noms = {o.nom_activite for o in occs}
    assert "EL48 TP2 (groupe B)" in noms
    assert "SY45 TP1 (groupe A)" not in noms


def test_occurrences_cover_full_day_without_gap_or_overlap(template):
    occs = sorted(generate_occurrences_for_date(date(2026, 9, 7), template), key=lambda o: o.debut_datetime)
    for a, b in zip(occs, occs[1:]):
        assert a.fin_datetime == b.debut_datetime, (a.nom_activite, b.nom_activite)


def test_resolve_state_en_cours(conn, template):
    # Lundi 7 sept 2026, 11h00 -> en plein milieu de "SY45 CM1" (10:15-12:15).
    now = datetime(2026, 9, 7, 11, 0)
    etat = resolve_current_state(conn, template, now=now)
    assert etat.etat == EtatCourant.EN_COURS
    assert etat.occurrence.nom_activite == "SY45 CM1"
    assert temps_restant(etat.occurrence, now=now) == timedelta(hours=1, minutes=15)


def test_resolve_state_reveil_en_milieu_de_creneau_apres_extinction(conn, template):
    """Cas README §1.4 : extinction pendant EL48 (12h-13h... ici SY45 CM1
    10:15-12:15), rallumage a 11h50 -> doit afficher directement le bon
    etat (SY45 CM1, ~25 min restantes), sans passer par les creneaux
    precedents non acquittes."""
    now = datetime(2026, 9, 7, 11, 50)
    etat = resolve_current_state(conn, template, now=now)
    assert etat.etat == EtatCourant.EN_COURS
    assert etat.occurrence.nom_activite == "SY45 CM1"
    assert temps_restant(etat.occurrence, now=now) == timedelta(minutes=25)


def test_resolve_state_a_acquitter_juste_apres_fin_sans_creneau_suivant(conn, template):
    # Lundi 21h30-22h00 "Preparation au sommeil" termine a 22h00, non
    # acquitte. A 23h00 (avant le prochain creneau mardi 4h00), on doit
    # obtenir l'ecran de blocage OK pour CE creneau precis.
    now = datetime(2026, 9, 7, 23, 0)
    etat = resolve_current_state(conn, template, now=now)
    assert etat.etat == EtatCourant.A_ACQUITTER
    assert etat.occurrence.nom_activite == "Preparation au sommeil"
    assert etat.occurrence.date == date(2026, 9, 7)


def test_resolve_state_libre_si_dernier_creneau_deja_acquitte(conn, template):
    ensure_occurrences_materialized(conn, template, date(2026, 9, 7), date(2026, 9, 8))
    last_id = "lun-21_2026-09-07"  # "Preparation au sommeil" du lundi
    assert local_db.get_occurrence(conn, last_id) is not None
    local_db.mark_acquitte(conn, last_id, device_id="test-device")

    now = datetime(2026, 9, 7, 23, 0)
    etat = resolve_current_state(conn, template, now=now)
    assert etat.etat == EtatCourant.LIBRE
    assert etat.prochaine_occurrence is not None
    assert etat.prochaine_occurrence.nom_activite == "Sport rapide (6 min)"
    assert etat.prochaine_occurrence.date == date(2026, 9, 8)


def test_pas_de_rattrapage_sur_plusieurs_jours_sautes(conn, template):
    """Simule un appareil reste eteint du lundi soir au mercredi soir tard :
    aucun des creneaux de lundi/mardi n'est jamais acquitte, mais au
    rallumage mercredi 23h00 (dans le trou nocturne), l'app doit
    proposer l'OK du DERNIER creneau ecoule (mercredi 21h30-22h00),
    jamais remonter a lundi ou mardi (regle "pas de rattrapage", §3)."""
    # Simule un premier lancement le lundi (qui materialise la journee),
    # comme cela arriverait reellement avant l'extinction prolongee.
    resolve_current_state(conn, template, now=datetime(2026, 9, 7, 9, 0))

    now = datetime(2026, 9, 9, 23, 0)  # mercredi 9 sept 2026, 23h00
    etat = resolve_current_state(conn, template, now=now)
    assert etat.etat == EtatCourant.A_ACQUITTER
    assert etat.occurrence.date == date(2026, 9, 9)
    assert etat.occurrence.nom_activite == "Preparation au sommeil"

    # Les creneaux de lundi et mardi restent non acquittes en base (pas
    # de rattrapage automatique, mais pas de perte de donnees non plus).
    lundi_dernier = local_db.get_occurrence(conn, "lun-21_2026-09-07")
    assert lundi_dernier is not None
    assert lundi_dernier.acquitte is False
