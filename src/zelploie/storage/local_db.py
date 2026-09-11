"""Stockage local SQLite (§4.2, §6).

Règle fondamentale de la spec : le calcul du temps restant / de l'état
courant ne doit JAMAIS dépendre du réseau. Ce module est donc la seule
source de vérité consultée au démarrage — Supabase ne fait que pousser
et recevoir des mises à jour de la même donnée en arrière-plan
(sync/supabase_sync.py), il ne fait pas partie du chemin critique de
lecture au lancement.

Aucune dépendance tierce : uniquement la bibliothèque standard.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from ..models import ActivityOccurrence, BlockCategory

DEFAULT_DB_PATH = Path.home() / ".zelploie" / "zelploie_local.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity_occurrence (
    id                   TEXT PRIMARY KEY,
    date                 TEXT NOT NULL,
    debut_datetime       TEXT NOT NULL,
    fin_datetime         TEXT NOT NULL,
    nom_activite         TEXT NOT NULL,
    categorie            TEXT NOT NULL,
    schedule_block_id    TEXT NOT NULL,
    salle                TEXT,
    acquitte             INTEGER NOT NULL DEFAULT 0,
    acquitte_le          TEXT,
    acquitte_par_device  TEXT,
    updated_at           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_occurrence_debut ON activity_occurrence(debut_datetime);
CREATE INDEX IF NOT EXISTS idx_occurrence_date ON activity_occurrence(date);

CREATE TABLE IF NOT EXISTS device_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Ouvre (et initialise si besoin) la base locale."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def get_or_create_device_id(conn: sqlite3.Connection) -> str:
    """Identifiant stable de cet appareil (§6), généré une seule fois."""
    row = conn.execute(
        "SELECT value FROM device_meta WHERE key = 'device_id'"
    ).fetchone()
    if row is not None:
        return row["value"]
    device_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO device_meta (key, value) VALUES ('device_id', ?)", (device_id,)
    )
    conn.commit()
    return device_id


def get_meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM device_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO device_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def _row_to_occurrence(row: sqlite3.Row) -> ActivityOccurrence:
    return ActivityOccurrence(
        id=row["id"],
        date=date.fromisoformat(row["date"]),
        debut_datetime=datetime.fromisoformat(row["debut_datetime"]),
        fin_datetime=datetime.fromisoformat(row["fin_datetime"]),
        nom_activite=row["nom_activite"],
        categorie=BlockCategory(row["categorie"]),
        schedule_block_id=row["schedule_block_id"],
        salle=row["salle"],
        acquitte=bool(row["acquitte"]),
        acquitte_le=datetime.fromisoformat(row["acquitte_le"]) if row["acquitte_le"] else None,
        acquitte_par_device=row["acquitte_par_device"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def upsert_occurrence(conn: sqlite3.Connection, occ: ActivityOccurrence) -> None:
    """Insère ou remplace une occurrence (utilisé par le moteur de
    planning ET par la synchronisation Supabase entrante)."""
    conn.execute(
        """
        INSERT INTO activity_occurrence (
            id, date, debut_datetime, fin_datetime, nom_activite, categorie,
            schedule_block_id, salle, acquitte, acquitte_le, acquitte_par_device, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            date=excluded.date,
            debut_datetime=excluded.debut_datetime,
            fin_datetime=excluded.fin_datetime,
            nom_activite=excluded.nom_activite,
            categorie=excluded.categorie,
            schedule_block_id=excluded.schedule_block_id,
            salle=excluded.salle,
            acquitte=excluded.acquitte,
            acquitte_le=excluded.acquitte_le,
            acquitte_par_device=excluded.acquitte_par_device,
            updated_at=excluded.updated_at
        """,
        (
            occ.id,
            occ.date.isoformat(),
            occ.debut_datetime.isoformat(),
            occ.fin_datetime.isoformat(),
            occ.nom_activite,
            occ.categorie.value,
            occ.schedule_block_id,
            occ.salle,
            int(occ.acquitte),
            occ.acquitte_le.isoformat() if occ.acquitte_le else None,
            occ.acquitte_par_device,
            occ.updated_at.isoformat(),
        ),
    )
    conn.commit()


def upsert_occurrence_if_newer(conn: sqlite3.Connection, occ: ActivityOccurrence) -> bool:
    """Applique la règle 'dernier écrit gagne' (§4.2) : n'écrase la ligne
    locale que si `occ.updated_at` est strictement plus récent (ou si la
    ligne n'existe pas encore). Utilisé pour les mises à jour reçues de
    Supabase, afin qu'un événement en retard n'écrase pas un clic OK plus
    récent fait localement. Renvoie True si l'écriture a eu lieu."""
    row = conn.execute(
        "SELECT updated_at FROM activity_occurrence WHERE id = ?", (occ.id,)
    ).fetchone()
    if row is not None and datetime.fromisoformat(row["updated_at"]) >= occ.updated_at:
        return False
    upsert_occurrence(conn, occ)
    return True


def get_occurrence(conn: sqlite3.Connection, occurrence_id: str) -> Optional[ActivityOccurrence]:
    row = conn.execute(
        "SELECT * FROM activity_occurrence WHERE id = ?", (occurrence_id,)
    ).fetchone()
    return _row_to_occurrence(row) if row else None


def list_occurrences_in_range(
    conn: sqlite3.Connection, start: datetime, end: datetime
) -> list[ActivityOccurrence]:
    rows = conn.execute(
        """
        SELECT * FROM activity_occurrence
        WHERE debut_datetime < ? AND fin_datetime > ?
        ORDER BY debut_datetime ASC
        """,
        (end.isoformat(), start.isoformat()),
    ).fetchall()
    return [_row_to_occurrence(r) for r in rows]


def mark_acquitte(
    conn: sqlite3.Connection, occurrence_id: str, device_id: str, when: Optional[datetime] = None
) -> Optional[ActivityOccurrence]:
    """Marque une occurrence comme acquittée (clic OK, §5.3). Renvoie
    l'occurrence mise à jour, ou None si elle n'existe pas localement."""
    occ = get_occurrence(conn, occurrence_id)
    if occ is None:
        return None
    occ.acquitte = True
    occ.acquitte_le = when or datetime.now()
    occ.acquitte_par_device = device_id
    occ.updated_at = datetime.now()
    upsert_occurrence(conn, occ)
    return occ
