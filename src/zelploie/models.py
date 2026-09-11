"""Modèles de données partagés (§4 de la spec).

Ces classes ne dépendent volontairement d'aucune bibliothèque tierce
(ni Flet, ni Supabase) : elles doivent rester importables et testables
en isolation totale, y compris sur une machine sans Flet installé.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Optional


class JourSemaine(str, Enum):
    LUNDI = "lundi"
    MARDI = "mardi"
    MERCREDI = "mercredi"
    JEUDI = "jeudi"
    VENDREDI = "vendredi"
    SAMEDI = "samedi"
    DIMANCHE = "dimanche"

    @property
    def index(self) -> int:
        """Index compatible avec date.weekday() : lundi=0 ... dimanche=6."""
        return _JOUR_INDEX[self]

    @staticmethod
    def depuis_index(index: int) -> "JourSemaine":
        return _INDEX_JOUR[index % 7]


_JOUR_INDEX = {
    JourSemaine.LUNDI: 0,
    JourSemaine.MARDI: 1,
    JourSemaine.MERCREDI: 2,
    JourSemaine.JEUDI: 3,
    JourSemaine.VENDREDI: 4,
    JourSemaine.SAMEDI: 5,
    JourSemaine.DIMANCHE: 6,
}
_INDEX_JOUR = {v: k for k, v in _JOUR_INDEX.items()}


class BlockCategory(str, Enum):
    """Catégories reprises de la légende couleur du planning PDF de Zeli."""

    COURS_TP = "cours_tp"                  # bleu : cours + TP officiels (UE)
    TRAVAIL_PERSONNEL = "travail_personnel"  # vert
    LOISIR = "loisir"                      # jaune : famille, musique, détente
    PRIERE = "priere"                      # rouge : prière / dévotion
    NEUTRE = "neutre"                      # blanc : repas, pauses, trajets


class SemaineVariante(str, Enum):
    A = "A"
    B = "B"


@dataclass
class ScheduleBlock:
    """Une ligne du gabarit hebdomadaire récurrent (schedule_template, §4.1).

    Un même (jour_semaine, heure_debut) peut apparaître deux fois dans le
    template complet uniquement si `semaine_variante` diffère (créneaux
    "OU" qui alternent selon que la semaine ISO est A ou B — voir
    week_rule.py). Dans tous les autres cas, (jour_semaine, heure_debut)
    est unique.
    """

    id: str
    jour_semaine: JourSemaine
    heure_debut: time
    heure_fin: time
    nom_activite: str
    categorie: BlockCategory
    salle: Optional[str] = None
    # None = s'applique toutes les semaines. "A" ou "B" = uniquement les
    # semaines de ce type (résolu par week_rule.resolve_week_variant).
    semaine_variante: Optional[SemaineVariante] = None

    def duree_minutes(self) -> int:
        debut = self.heure_debut.hour * 60 + self.heure_debut.minute
        fin = self.heure_fin.hour * 60 + self.heure_fin.minute
        return fin - debut


@dataclass
class ActivityOccurrence:
    """Une occurrence concrète datée (activity_occurrence, §4.2)."""

    id: str
    date: date
    debut_datetime: datetime
    fin_datetime: datetime
    nom_activite: str
    categorie: BlockCategory
    schedule_block_id: str
    salle: Optional[str] = None
    acquitte: bool = False
    acquitte_le: Optional[datetime] = None
    acquitte_par_device: Optional[str] = None
    # Horodatage de dernière écriture locale, utilisé pour le
    # last-write-wins décrit en §4.2 lors de la fusion avec Supabase.
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "debut_datetime": self.debut_datetime.isoformat(),
            "fin_datetime": self.fin_datetime.isoformat(),
            "nom_activite": self.nom_activite,
            "categorie": self.categorie.value,
            "schedule_block_id": self.schedule_block_id,
            "salle": self.salle,
            "acquitte": self.acquitte,
            "acquitte_le": self.acquitte_le.isoformat() if self.acquitte_le else None,
            "acquitte_par_device": self.acquitte_par_device,
            "updated_at": self.updated_at.isoformat(),
        }

    @staticmethod
    def from_dict(d: dict) -> "ActivityOccurrence":
        return ActivityOccurrence(
            id=d["id"],
            date=date.fromisoformat(d["date"]),
            debut_datetime=datetime.fromisoformat(d["debut_datetime"]),
            fin_datetime=datetime.fromisoformat(d["fin_datetime"]),
            nom_activite=d["nom_activite"],
            categorie=BlockCategory(d["categorie"]),
            schedule_block_id=d["schedule_block_id"],
            salle=d.get("salle"),
            acquitte=bool(d.get("acquitte", False)),
            acquitte_le=datetime.fromisoformat(d["acquitte_le"]) if d.get("acquitte_le") else None,
            acquitte_par_device=d.get("acquitte_par_device"),
            updated_at=datetime.fromisoformat(d["updated_at"]) if d.get("updated_at") else datetime.now(),
        )


class EtatCourant(str, Enum):
    """Les 3 cas de §5.1."""

    EN_COURS = "en_cours"          # dans un créneau, pas encore acquitté
    A_ACQUITTER = "a_acquitter"    # créneau terminé, écran de blocage à afficher
    LIBRE = "libre"                # en dehors de tout créneau


@dataclass
class EtatPlanning:
    """Résultat de la résolution d'état au lancement / retour au premier plan (§5.1)."""

    etat: EtatCourant
    occurrence: Optional[ActivityOccurrence] = None
    prochaine_occurrence: Optional[ActivityOccurrence] = None
