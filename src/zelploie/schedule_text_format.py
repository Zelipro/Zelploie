"""Format texte "littéral" de l'emploi du temps (v2).

Objectif (demande explicite de Zeli) : pouvoir fournir/modifier son
emploi du temps en éditant un simple fichier texte, sans jamais
recompiler l'app — et pouvoir "réinitialiser" en supprimant juste ce
fichier.

Le format est volontairement simple à taper à la main OU à générer par
une IA à partir d'une description libre (voir docs/prompt_ia_emploi_du_temps.md,
le prompt fourni à Zeli pour cette conversion) : une ligne par créneau,
champs séparés par `|`. Ce module ne fait AUCUNE interprétation floue —
tout ce qui ne colle pas exactement au format attendu est remonté comme
une erreur explicite avec numéro de ligne, jamais deviné silencieusement.

Format d'une ligne :
    Jour | HeureDebut | HeureFin | Activité [| Catégorie [| Salle [| Variante]]]

- Jour : lundi/mardi/mercredi/jeudi/vendredi/samedi/dimanche (accents et
  casse ignorés).
- HeureDebut/HeureFin : HH:MM (24h), HeureFin strictement après HeureDebut.
- Activité : texte libre, ne doit pas être vide.
- Catégorie (optionnelle, défaut "neutre") : cours_tp / travail_personnel /
  loisir / priere / neutre.
- Salle (optionnelle) : texte libre ou vide.
- Variante (optionnelle) : A ou B, pour les 2 créneaux qui alternent
  selon la semaine — voir week_rule.py. Deux lignes avec le même
  (jour, début, fin) mais des variantes A et B différentes sont
  autorisées (et attendues) ; toute autre collision est une erreur.

Les lignes vides, celles commençant par `#`, une éventuelle ligne
d'en-tête ("Jour | ..."), et une éventuelle ligne de séparation
(uniquement des `-`, `|` et espaces) sont ignorées.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from .models import BlockCategory, JourSemaine, ScheduleBlock, SemaineVariante

DEFAULT_SCHEDULE_PATH = Path.home() / ".zelploie" / "emploi_zeli.txt"

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

_JOUR_NORMALISES = {
    "lundi": JourSemaine.LUNDI,
    "mardi": JourSemaine.MARDI,
    "mercredi": JourSemaine.MERCREDI,
    "jeudi": JourSemaine.JEUDI,
    "vendredi": JourSemaine.VENDREDI,
    "samedi": JourSemaine.SAMEDI,
    "dimanche": JourSemaine.DIMANCHE,
}

_CATEGORIES_VALIDES = {c.value: c for c in BlockCategory}

_SEPARATOR_LINE_RE = re.compile(r"^[\s|\-]+$")


class ScheduleFormatError(ValueError):
    """Levée avec la liste complète des erreurs (une par ligne fautive),
    pour que l'utilisateur (ou l'IA qui a généré le fichier) puisse tout
    corriger en une seule passe plutôt qu'un aller-retour par erreur."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def _normaliser_jour(brut: str) -> str:
    sans_accents = "".join(
        c for c in unicodedata.normalize("NFD", brut) if unicodedata.category(c) != "Mn"
    )
    return sans_accents.strip().lower()


def _est_ligne_ignorable(ligne: str) -> bool:
    if not ligne.strip():
        return True
    if ligne.strip().startswith("#"):
        return True
    if _SEPARATOR_LINE_RE.match(ligne):
        return True
    premiere_colonne = ligne.split("|", 1)[0].strip().lower()
    if premiere_colonne in ("jour", "day"):
        return True
    return False


@dataclass
class _LigneParsee:
    numero: int
    jour: JourSemaine
    heure_debut: time
    heure_fin: time
    nom_activite: str
    categorie: BlockCategory
    salle: str | None
    semaine_variante: SemaineVariante | None


def parse_schedule_text(texte: str) -> list[ScheduleBlock]:
    """Parse le format texte en liste de ScheduleBlock.

    Lève ScheduleFormatError (avec TOUTES les erreurs trouvées) si quoi
    que ce soit ne colle pas au format — jamais de correction silencieuse.
    """
    erreurs: list[str] = []
    lignes_ok: list[_LigneParsee] = []

    for numero, ligne_brute in enumerate(texte.splitlines(), start=1):
        if _est_ligne_ignorable(ligne_brute):
            continue

        champs = [c.strip() for c in ligne_brute.split("|")]
        if len(champs) < 4:
            erreurs.append(
                f"Ligne {numero} : au moins 4 champs attendus "
                f"(Jour | Début | Fin | Activité), {len(champs)} trouvé(s) : {ligne_brute!r}"
            )
            continue

        jour_brut, debut_brut, fin_brut, activite = champs[0], champs[1], champs[2], champs[3]
        categorie_brute = champs[4] if len(champs) > 4 else ""
        salle_brute = champs[5] if len(champs) > 5 else ""
        variante_brute = champs[6] if len(champs) > 6 else ""

        ligne_erreurs = []

        jour = _JOUR_NORMALISES.get(_normaliser_jour(jour_brut))
        if jour is None:
            ligne_erreurs.append(f"jour invalide {jour_brut!r} (attendu : lundi..dimanche)")

        match_debut = _TIME_RE.match(debut_brut)
        if not match_debut:
            ligne_erreurs.append(f"heure de début invalide {debut_brut!r} (attendu HH:MM)")

        match_fin = _TIME_RE.match(fin_brut)
        if not match_fin:
            ligne_erreurs.append(f"heure de fin invalide {fin_brut!r} (attendu HH:MM)")

        if match_debut and match_fin:
            heure_debut = time(int(match_debut.group(1)), int(match_debut.group(2)))
            heure_fin = time(int(match_fin.group(1)), int(match_fin.group(2)))
            if heure_fin <= heure_debut:
                ligne_erreurs.append(
                    f"l'heure de fin ({fin_brut}) doit être strictement après l'heure de début ({debut_brut})"
                )
        else:
            heure_debut = heure_fin = None

        if not activite:
            ligne_erreurs.append("le nom de l'activité est vide")

        categorie = BlockCategory.NEUTRE
        if categorie_brute:
            categorie = _CATEGORIES_VALIDES.get(categorie_brute.strip().lower())
            if categorie is None:
                ligne_erreurs.append(
                    f"catégorie invalide {categorie_brute!r} "
                    f"(attendu : {', '.join(_CATEGORIES_VALIDES)})"
                )
                categorie = BlockCategory.NEUTRE

        variante = None
        if variante_brute:
            v = variante_brute.strip().upper()
            if v not in ("A", "B"):
                ligne_erreurs.append(f"variante invalide {variante_brute!r} (attendu : A ou B)")
            else:
                variante = SemaineVariante(v)

        if ligne_erreurs:
            erreurs.append(f"Ligne {numero} ({ligne_brute!r}) : " + " ; ".join(ligne_erreurs))
            continue

        lignes_ok.append(
            _LigneParsee(
                numero=numero,
                jour=jour,
                heure_debut=heure_debut,
                heure_fin=heure_fin,
                nom_activite=activite,
                categorie=categorie,
                salle=salle_brute or None,
                semaine_variante=variante,
            )
        )

    if not erreurs and not lignes_ok:
        erreurs.append("Aucun créneau trouvé dans le texte fourni.")

    if not erreurs:
        erreurs.extend(_detecter_chevauchements(lignes_ok))

    if erreurs:
        raise ScheduleFormatError(erreurs)

    return [
        ScheduleBlock(
            id=_generer_id(l),
            jour_semaine=l.jour,
            heure_debut=l.heure_debut,
            heure_fin=l.heure_fin,
            nom_activite=l.nom_activite,
            categorie=l.categorie,
            salle=l.salle,
            semaine_variante=l.semaine_variante,
        )
        for l in lignes_ok
    ]


def _generer_id(l: _LigneParsee) -> str:
    base = f"{l.jour.value}-{l.heure_debut:%H%M}-{l.heure_fin:%H%M}"
    return f"{base}-{l.semaine_variante.value}" if l.semaine_variante else base


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _detecter_chevauchements(lignes: list[_LigneParsee]) -> list[str]:
    erreurs = []
    par_jour: dict[JourSemaine, list[_LigneParsee]] = {}
    for l in lignes:
        par_jour.setdefault(l.jour, []).append(l)

    for jour, groupe in par_jour.items():
        groupe_trie = sorted(groupe, key=lambda l: (_minutes(l.heure_debut), _minutes(l.heure_fin)))
        for a, b in zip(groupe_trie, groupe_trie[1:]):
            meme_creneau = a.heure_debut == b.heure_debut and a.heure_fin == b.heure_fin
            variantes_ok = (
                meme_creneau
                and a.semaine_variante is not None
                and b.semaine_variante is not None
                and a.semaine_variante != b.semaine_variante
            )
            if variantes_ok:
                continue
            if _minutes(b.heure_debut) < _minutes(a.heure_fin):
                erreurs.append(
                    f"Chevauchement le {jour.value} entre les lignes {a.numero} "
                    f"({a.heure_debut:%H:%M}-{a.heure_fin:%H:%M} {a.nom_activite!r}) et "
                    f"{b.numero} ({b.heure_debut:%H:%M}-{b.heure_fin:%H:%M} {b.nom_activite!r}) "
                    "— si c'est volontaire (créneau à variante A/B), les 2 lignes doivent avoir "
                    "exactement le même début/fin et des variantes A et B différentes."
                )
    return erreurs


def parse_schedule_file(path: Path | str = DEFAULT_SCHEDULE_PATH) -> list[ScheduleBlock]:
    return parse_schedule_text(Path(path).read_text(encoding="utf-8"))


def serialize_schedule(blocks: list[ScheduleBlock]) -> str:
    """Sérialise une liste de ScheduleBlock dans le format texte —
    utilisé pour générer le fichier d'exemple et pour toute
    réexportation future du planning courant."""
    ordre_jours = list(JourSemaine)
    lignes = ["Jour | Début | Fin | Activité | Catégorie | Salle | Variante"]
    for jour in ordre_jours:
        blocs_du_jour = sorted(
            (b for b in blocks if b.jour_semaine == jour),
            key=lambda b: (b.heure_debut, b.heure_fin, b.semaine_variante.value if b.semaine_variante else ""),
        )
        for b in blocs_du_jour:
            lignes.append(
                " | ".join(
                    [
                        jour.value,
                        b.heure_debut.strftime("%H:%M"),
                        b.heure_fin.strftime("%H:%M"),
                        b.nom_activite,
                        b.categorie.value,
                        b.salle or "",
                        b.semaine_variante.value if b.semaine_variante else "",
                    ]
                )
            )
    return "\n".join(lignes) + "\n"


def save_schedule_text(texte: str, path: Path | str = DEFAULT_SCHEDULE_PATH) -> None:
    """Valide puis écrit le texte dans le fichier (§ demande de Zeli :
    supprimer ce fichier = repartir de zéro). Lève ScheduleFormatError
    sans rien écrire si le texte ne parse pas."""
    parse_schedule_text(texte)  # valide avant d'écrire quoi que ce soit
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(texte, encoding="utf-8")
