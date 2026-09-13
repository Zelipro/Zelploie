"""Moteur de planning : génération d'occurrences + résolution d'état (§5.1).

Aucune dépendance à Flet ni au réseau : tout ce module ne lit que la
base locale (storage/local_db.py) et l'horloge système, conformément à
la règle de la spec : "L'app ne doit jamais dépendre du réseau pour
recalculer le temps restant au démarrage."
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from ..models import ActivityOccurrence, EtatCourant, EtatPlanning, JourSemaine, ScheduleBlock
from ..schedule_text_format import parse_schedule_file
from ..storage.local_db import get_occurrence, list_occurrences_in_range, upsert_occurrence
from ..week_rule import resolve_week_variant

# Fichier d'exemple bundlé avec l'app (planning réel de Zeli au format
# texte v2) — utilisé par les tests et comme point de départ que Zeli
# peut copier-coller lors du tout premier lancement. L'app elle-même
# lit toujours depuis schedule_text_format.DEFAULT_SCHEDULE_PATH
# (~/.zelploie/emploi_zeli.txt), pas depuis ce fichier bundlé.
DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "data" / "exemple_emploi_du_temps.txt"

# Fenêtre de notifications à l'avance (§5.2) : 14 jours, régénérée
# régulièrement (à chaque lancement / retour au premier plan).
NOTIFICATION_WINDOW_DAYS = 14


def load_schedule_template(path: Path | str = DEFAULT_TEMPLATE_PATH) -> list[ScheduleBlock]:
    """Charge le gabarit hebdomadaire depuis le fichier texte éditable
    (§4.1, format v2 — voir schedule_text_format.py).

    C'est le SEUL endroit à modifier pour changer l'emploi du temps sans
    recompiler l'app : éditer le fichier texte (voir README). Peut lever
    schedule_text_format.ScheduleFormatError si le fichier ne respecte
    pas le format attendu.
    """
    return parse_schedule_file(path)


def generate_occurrences_for_date(d: date, template: list[ScheduleBlock]) -> list[ActivityOccurrence]:
    """Matérialise les occurrences d'une date donnée à partir du gabarit.

    Pour un créneau à variante (semaine_variante A/B), seule la variante
    correspondant à la semaine réelle de `d` (résolue via week_rule) est
    retenue — l'autre est ignorée pour cette date.
    """
    jour = JourSemaine.depuis_index(d.weekday())
    variante_du_jour = resolve_week_variant(d)

    occurrences = []
    for block in template:
        if block.jour_semaine != jour:
            continue
        if block.semaine_variante is not None and block.semaine_variante != variante_du_jour:
            continue
        debut_dt = datetime.combine(d, block.heure_debut)
        fin_dt = datetime.combine(d, block.heure_fin)
        occurrences.append(
            ActivityOccurrence(
                id=f"{block.id}_{d.isoformat()}",
                date=d,
                debut_datetime=debut_dt,
                fin_datetime=fin_dt,
                nom_activite=block.nom_activite,
                categorie=block.categorie,
                schedule_block_id=block.id,
                salle=block.salle,
            )
        )
    return occurrences


def ensure_occurrences_materialized(
    conn: sqlite3.Connection,
    template: list[ScheduleBlock],
    from_date: date,
    to_date: date,
) -> int:
    """Matérialise (insère si absent) les occurrences pour [from_date, to_date].

    N'écrase jamais une occurrence existante : un créneau déjà acquitté
    (ou en cours de synchronisation) ne doit pas être régénéré à l'identique
    et perdre son état. Renvoie le nombre d'occurrences nouvellement créées.
    """
    created = 0
    d = from_date
    while d <= to_date:
        for occ in generate_occurrences_for_date(d, template):
            if get_occurrence(conn, occ.id) is None:
                upsert_occurrence(conn, occ)
                created += 1
        d += timedelta(days=1)
    return created


def resolve_current_state(
    conn: sqlite3.Connection,
    template: list[ScheduleBlock],
    now: Optional[datetime] = None,
) -> EtatPlanning:
    """Résout l'état à afficher au lancement / retour au premier plan (§5.1).

    Règle "pas de rattrapage" (§3) : si un ou plusieurs créneaux entiers
    ont été sautés (device éteint pendant tout un créneau), on ne
    remonte jamais plus loin que le dernier créneau écoulé ET seulement
    s'il n'a pas été suivi par le démarrage d'un autre créneau depuis.
    """
    now = now or datetime.now()

    # Fenêtre large pour matérialiser : la veille (pour capter le dernier
    # créneau de la nuit précédente si l'app n'a pas tourné) jusqu'à
    # l'horizon de notification à venir.
    ensure_occurrences_materialized(
        conn, template, now.date() - timedelta(days=1), now.date() + timedelta(days=NOTIFICATION_WINDOW_DAYS)
    )

    fenetre = list_occurrences_in_range(
        conn, now - timedelta(days=2), now + timedelta(days=NOTIFICATION_WINDOW_DAYS + 1)
    )

    courant = next((o for o in fenetre if o.debut_datetime <= now < o.fin_datetime), None)
    if courant is not None and not courant.acquitte:
        return EtatPlanning(EtatCourant.EN_COURS, occurrence=courant)

    passes = [o for o in fenetre if o.fin_datetime <= now]
    dernier_ecoule = max(passes, key=lambda o: o.fin_datetime) if passes else None

    if dernier_ecoule is not None and not dernier_ecoule.acquitte:
        demarre_depuis = any(
            dernier_ecoule.fin_datetime < o.debut_datetime <= now for o in fenetre
        )
        if not demarre_depuis:
            return EtatPlanning(EtatCourant.A_ACQUITTER, occurrence=dernier_ecoule)

    a_venir = [o for o in fenetre if o.debut_datetime > now]
    prochaine = min(a_venir, key=lambda o: o.debut_datetime) if a_venir else None
    return EtatPlanning(EtatCourant.LIBRE, prochaine_occurrence=prochaine)


def temps_restant(occurrence: ActivityOccurrence, now: Optional[datetime] = None) -> timedelta:
    """Temps restant avant la fin, recalculé à partir de l'horloge système
    (§5.4) — jamais une simple décrémentation en mémoire, pour ne pas
    dériver ni perdre la synchro après une mise en veille."""
    now = now or datetime.now()
    restant = occurrence.fin_datetime - now
    return restant if restant > timedelta(0) else timedelta(0)
