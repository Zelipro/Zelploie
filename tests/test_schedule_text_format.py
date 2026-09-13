import pytest

from zelploie.models import BlockCategory, JourSemaine, SemaineVariante
from zelploie.schedule_text_format import (
    ScheduleFormatError,
    parse_schedule_text,
    save_schedule_text,
    serialize_schedule,
)


def test_parse_minimal_valid_line():
    texte = "lundi | 08:00 | 10:00 | EL48 CM1"
    blocks = parse_schedule_text(texte)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.jour_semaine == JourSemaine.LUNDI
    assert b.heure_debut.isoformat() == "08:00:00"
    assert b.heure_fin.isoformat() == "10:00:00"
    assert b.nom_activite == "EL48 CM1"
    assert b.categorie == BlockCategory.NEUTRE  # defaut si omise
    assert b.salle is None
    assert b.semaine_variante is None


def test_parse_full_line_with_all_optional_fields():
    texte = "jeudi | 10:15 | 13:15 | SY45 TP1 (groupe A) | cours_tp | B139y | A"
    blocks = parse_schedule_text(texte)
    b = blocks[0]
    assert b.categorie == BlockCategory.COURS_TP
    assert b.salle == "B139y"
    assert b.semaine_variante == SemaineVariante.A


def test_header_and_separator_and_comments_and_blank_lines_ignored():
    texte = """
    # Mon planning
    Jour | Début | Fin | Activité
    -----|-------|-----|----------
    lundi | 08:00 | 10:00 | EL48 CM1

    mardi | 08:00 | 10:00 | EL48 TD1
    """
    blocks = parse_schedule_text(texte)
    assert len(blocks) == 2


def test_jour_accents_et_casse_insensibles():
    texte = "MERCREDI | 08:00 | 10:00 | Test"
    blocks = parse_schedule_text(texte)
    assert blocks[0].jour_semaine == JourSemaine.MERCREDI


def test_invalid_day_reports_error_with_line_number():
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text("lundu | 08:00 | 10:00 | EL48 CM1")
    assert "Ligne 1" in exc_info.value.errors[0]
    assert "jour invalide" in exc_info.value.errors[0]


def test_invalid_time_format_reports_error():
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text("lundi | 8h00 | 10:00 | EL48 CM1")
    assert "heure de début invalide" in exc_info.value.errors[0]


def test_end_before_start_is_an_error():
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text("lundi | 10:00 | 08:00 | EL48 CM1")
    assert "après l'heure de début" in exc_info.value.errors[0]


def test_empty_activity_is_an_error():
    with pytest.raises(ScheduleFormatError):
        parse_schedule_text("lundi | 08:00 | 10:00 | ")


def test_invalid_category_is_an_error():
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text("lundi | 08:00 | 10:00 | EL48 CM1 | pas_une_categorie")
    assert "catégorie invalide" in exc_info.value.errors[0]


def test_invalid_variant_is_an_error():
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text("lundi | 08:00 | 10:00 | EL48 CM1 | cours_tp | I102 | C")
    assert "variante invalide" in exc_info.value.errors[0]


def test_too_few_fields_is_an_error():
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text("lundi | 08:00 | EL48 CM1")
    assert "au moins 4 champs" in exc_info.value.errors[0]


def test_all_errors_reported_together_not_just_first():
    texte = "lundu | 08:00 | 10:00 | EL48 CM1\nmardi | 25:00 | 10:00 | X"
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text(texte)
    assert len(exc_info.value.errors) == 2


def test_overlap_same_day_is_an_error():
    texte = "lundi | 08:00 | 10:00 | A\nlundi | 09:00 | 11:00 | B"
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text(texte)
    assert "Chevauchement" in exc_info.value.errors[0]


def test_variant_pair_same_slot_is_not_an_overlap_error():
    texte = (
        "lundi | 13:00 | 16:00 | EL47 TP1 (groupe A) | cours_tp | B005 | A\n"
        "lundi | 13:00 | 16:00 | IF40 TP1 (groupe B) | cours_tp | B123 | B"
    )
    blocks = parse_schedule_text(texte)
    assert len(blocks) == 2


def test_duplicate_slot_without_distinct_variants_is_an_error():
    texte = "lundi | 13:00 | 16:00 | A\nlundi | 13:00 | 16:00 | B"
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text(texte)
    assert "Chevauchement" in exc_info.value.errors[0]


def test_empty_text_is_an_error():
    with pytest.raises(ScheduleFormatError) as exc_info:
        parse_schedule_text("   \n  # rien ici\n")
    assert "Aucun créneau" in exc_info.value.errors[0]


def test_serialize_then_parse_round_trip():
    texte = "lundi | 08:00 | 10:00 | EL48 CM1 | cours_tp | I102 | \n"
    blocks = parse_schedule_text(texte)
    reserialized = serialize_schedule(blocks)
    reparsed = parse_schedule_text(reserialized)
    assert len(reparsed) == len(blocks) == 1
    assert reparsed[0].nom_activite == "EL48 CM1"
    assert reparsed[0].salle == "I102"


def test_save_schedule_text_writes_file_only_if_valid(tmp_path):
    path = tmp_path / "emploi_zeli.txt"
    save_schedule_text("lundi | 08:00 | 10:00 | EL48 CM1", path=path)
    assert path.read_text(encoding="utf-8") == "lundi | 08:00 | 10:00 | EL48 CM1"


def test_save_schedule_text_does_not_write_if_invalid(tmp_path):
    path = tmp_path / "emploi_zeli.txt"
    with pytest.raises(ScheduleFormatError):
        save_schedule_text("n'importe quoi sans le bon format", path=path)
    assert not path.exists()
