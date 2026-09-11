from datetime import date, datetime, timedelta

import pytest

from zelploie.models import ActivityOccurrence, BlockCategory
from zelploie.storage import local_db


@pytest.fixture()
def conn(tmp_path):
    return local_db.connect(tmp_path / "test.db")


def _make_occurrence(occ_id="occ-1", debut=None, fin=None) -> ActivityOccurrence:
    debut = debut or datetime(2026, 9, 7, 8, 0)
    fin = fin or datetime(2026, 9, 7, 10, 0)
    return ActivityOccurrence(
        id=occ_id,
        date=debut.date(),
        debut_datetime=debut,
        fin_datetime=fin,
        nom_activite="EL48 CM1",
        categorie=BlockCategory.COURS_TP,
        schedule_block_id="lun-07",
        salle="I102",
    )


def test_device_id_is_stable_across_calls(conn):
    first = local_db.get_or_create_device_id(conn)
    second = local_db.get_or_create_device_id(conn)
    assert first == second
    assert len(first) > 0


def test_upsert_and_get_occurrence(conn):
    occ = _make_occurrence()
    local_db.upsert_occurrence(conn, occ)
    fetched = local_db.get_occurrence(conn, "occ-1")
    assert fetched is not None
    assert fetched.nom_activite == "EL48 CM1"
    assert fetched.acquitte is False


def test_mark_acquitte(conn):
    occ = _make_occurrence()
    local_db.upsert_occurrence(conn, occ)
    updated = local_db.mark_acquitte(conn, "occ-1", device_id="device-abc")
    assert updated.acquitte is True
    assert updated.acquitte_par_device == "device-abc"
    assert updated.acquitte_le is not None

    refetched = local_db.get_occurrence(conn, "occ-1")
    assert refetched.acquitte is True


def test_mark_acquitte_unknown_id_returns_none(conn):
    assert local_db.mark_acquitte(conn, "does-not-exist", device_id="d1") is None


def test_list_occurrences_in_range(conn):
    occ1 = _make_occurrence("occ-1", datetime(2026, 9, 7, 8, 0), datetime(2026, 9, 7, 10, 0))
    occ2 = _make_occurrence("occ-2", datetime(2026, 9, 7, 10, 0), datetime(2026, 9, 7, 12, 0))
    occ3 = _make_occurrence("occ-3", datetime(2026, 9, 8, 8, 0), datetime(2026, 9, 8, 10, 0))
    for o in (occ1, occ2, occ3):
        local_db.upsert_occurrence(conn, o)

    result = local_db.list_occurrences_in_range(
        conn, datetime(2026, 9, 7, 0, 0), datetime(2026, 9, 7, 23, 59)
    )
    ids = {o.id for o in result}
    assert ids == {"occ-1", "occ-2"}


def test_last_write_wins_ignores_older_update(conn):
    occ = _make_occurrence()
    occ.updated_at = datetime(2026, 9, 7, 9, 0)
    local_db.upsert_occurrence(conn, occ)

    older_update = _make_occurrence()
    older_update.acquitte = True
    older_update.updated_at = datetime(2026, 9, 7, 8, 30)  # plus ancien
    applied = local_db.upsert_occurrence_if_newer(conn, older_update)

    assert applied is False
    assert local_db.get_occurrence(conn, "occ-1").acquitte is False


def test_last_write_wins_applies_newer_update(conn):
    occ = _make_occurrence()
    occ.updated_at = datetime(2026, 9, 7, 9, 0)
    local_db.upsert_occurrence(conn, occ)

    newer_update = _make_occurrence()
    newer_update.acquitte = True
    newer_update.acquitte_par_device = "autre-appareil"
    newer_update.updated_at = datetime(2026, 9, 7, 9, 30)  # plus recent
    applied = local_db.upsert_occurrence_if_newer(conn, newer_update)

    assert applied is True
    fetched = local_db.get_occurrence(conn, "occ-1")
    assert fetched.acquitte is True
    assert fetched.acquitte_par_device == "autre-appareil"
