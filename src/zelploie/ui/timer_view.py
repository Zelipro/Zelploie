"""Vue principale : minuteur en direct (§5.4) et état "libre" (§5.1 cas 3)."""

from __future__ import annotations

from datetime import datetime, timedelta

import flet as ft

from ..models import BlockCategory, EtatCourant, EtatPlanning

_CATEGORY_COLORS = {
    BlockCategory.COURS_TP: ft.Colors.BLUE,
    BlockCategory.TRAVAIL_PERSONNEL: ft.Colors.GREEN,
    BlockCategory.LOISIR: ft.Colors.AMBER,
    BlockCategory.PRIERE: ft.Colors.RED,
    BlockCategory.NEUTRE: ft.Colors.GREY,
}


def _format_duration(d: timedelta) -> str:
    total_seconds = int(d.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def build_timer_view(etat: EtatPlanning, now: datetime | None = None) -> ft.Control:
    """Construit le contenu de la vue principale selon l'état résolu.

    N'est jamais appelé pour EtatCourant.A_ACQUITTER : ce cas est géré
    par block_screen.py (écran de blocage plein écran séparé).
    """
    now = now or datetime.now()

    if etat.etat == EtatCourant.EN_COURS:
        occ = etat.occurrence
        restant = max(occ.fin_datetime - now, timedelta(0))
        couleur = _CATEGORY_COLORS.get(occ.categorie, ft.Colors.GREY)
        return ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            spacing=20,
            controls=[
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=16, vertical=6),
                    border_radius=20,
                    bgcolor=couleur,
                    content=ft.Text(
                        occ.categorie.value.replace("_", " ").upper(),
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                ),
                ft.Text(occ.nom_activite, size=28, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                ft.Text(
                    _format_duration(restant),
                    size=64,
                    weight=ft.FontWeight.BOLD,
                    color=couleur,
                ),
                ft.Text(f"Fin prévue à {occ.fin_datetime:%H:%M}", size=14, color=ft.Colors.GREY),
            ],
        )

    # LIBRE
    prochaine = etat.prochaine_occurrence
    if prochaine is None:
        return ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            controls=[ft.Text("Libre", size=32, weight=ft.FontWeight.BOLD)],
        )

    attente = max(prochaine.debut_datetime - now, timedelta(0))
    return ft.Column(
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
        spacing=16,
        controls=[
            ft.Text("Libre", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY),
            ft.Text("Prochaine activité :", size=14, color=ft.Colors.GREY),
            ft.Text(prochaine.nom_activite, size=24, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Text(f"dans {_format_duration(attente)} (à {prochaine.debut_datetime:%H:%M})", size=16),
        ],
    )
