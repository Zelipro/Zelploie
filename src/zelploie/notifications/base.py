"""Contenu partagé des notifications (§5.2).

Wording proposé par défaut — pas bloquant pour la suite du
développement, mais à ajuster librement : change juste les fonctions
ci-dessous, rien d'autre n'a besoin de changer.
"""

from __future__ import annotations

from ..models import ActivityOccurrence


def start_title(occ: ActivityOccurrence) -> str:
    return occ.nom_activite


def start_body(occ: ActivityOccurrence) -> str:
    return f"Fin prévue à {occ.fin_datetime:%H:%M}"


def end_title(occ: ActivityOccurrence) -> str:
    return f"{occ.nom_activite} — terminé"


def end_body(occ: ActivityOccurrence) -> str:
    return "Clique OK pour continuer."
