"""Résolution de la semaine A/B pour les créneaux TP alternés.

Contexte (voir échange avec Zeli) : deux créneaux du planning
("EL47 TP1 gr.A / IF40 TP1 gr.B" le lundi 13h-16h, et
"SY45 TP1 gr.A / EL48 TP2 gr.B" le jeudi 10h15-13h15) alternent selon
que la semaine calendaire est une "semaine A" ou une "semaine B". Zeli
suit systématiquement la variante qui correspond au type de semaine en
cours (pas de groupe personnel fixe à gérer séparément).

Référence confirmée par Zeli : la semaine du 7 septembre 2026 est une
semaine A. Cette semaine est la semaine ISO n°37 (impaire) — vérifié
avec date(2026, 9, 7).isocalendar().

Règle appliquée ici : alternance stricte par parité de la semaine ISO
(impaire = A, paire = B), en continu sans réinitialisation.

⚠️ POINT NON CONFIRMÉ PAR ZELI : on ne sait pas si cette alternance
continue sans interruption à travers les vacances de Noël jusqu'au
semestre de printemps (~février 2027), ou si elle redémarre à "A" au
début du semestre 2. Si Zeli confirme un redémarrage, il suffit
d'ajouter une deuxième référence dans `_REFERENCES` ci-dessous — le
reste du moteur n'a pas à changer.
"""

from __future__ import annotations

from datetime import date

from .models import SemaineVariante

# Liste de (date_de_reference, variante_a_cette_date). La résolution
# utilise la référence la plus récente qui soit <= à la date demandée,
# puis applique la parité ISO en continu à partir de là. Une seule
# entrée aujourd'hui ; en ajouter une nouvelle si Zeli confirme un
# redémarrage de la parité à une date donnée (ex. début du semestre
# de printemps).
_REFERENCES: list[tuple[date, SemaineVariante]] = [
    (date(2026, 9, 7), SemaineVariante.A),
]


def resolve_week_variant(d: date) -> SemaineVariante:
    """Renvoie la variante de semaine (A ou B) applicable à la date `d`."""
    ref_date, ref_variante = _reference_pour(d)

    # Nombre de semaines ISO écoulées entre la référence et `d`. On
    # reste en semaines "civiles" continues : le nombre de jours
    # écoulés divisé par 7 donne directement le nombre de semaines,
    # ISO ou pas (une semaine ISO fait toujours 7 jours, seul le
    # numéro affiché en fin/début d'année boucle).
    delta_jours = (d - ref_date).days
    delta_semaines = delta_jours // 7

    if delta_semaines % 2 == 0:
        return ref_variante
    return SemaineVariante.B if ref_variante == SemaineVariante.A else SemaineVariante.A


def _reference_pour(d: date) -> tuple[date, SemaineVariante]:
    candidates = [r for r in _REFERENCES if r[0] <= d]
    if not candidates:
        # Date antérieure à toute référence connue : on extrapole quand
        # même à partir de la plus ancienne référence disponible.
        return _REFERENCES[0]
    return max(candidates, key=lambda r: r[0])
