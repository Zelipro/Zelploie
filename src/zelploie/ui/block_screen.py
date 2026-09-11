"""Écran de blocage plein écran (§5.3).

Sur desktop, c'est appelant (ui/app.py) qui bascule la fenêtre en plein
écran/toujours au premier plan/sans bordure via `page.window` avant
d'afficher ce contenu — ce module ne fait que construire le contenu
visuel, identique sur toutes les plateformes.
"""

from __future__ import annotations

from typing import Awaitable, Callable

import flet as ft

from ..models import ActivityOccurrence

OnOkHandler = Callable[[ft.ControlEvent], Awaitable[None]]


def build_block_screen(occ: ActivityOccurrence, on_ok: OnOkHandler) -> ft.Control:
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.RED_900,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=28,
            controls=[
                ft.Icon(ft.Icons.LOCK_CLOCK, size=72, color=ft.Colors.WHITE),
                ft.Text(
                    occ.nom_activite,
                    size=32,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Terminé — clique OK pour continuer.",
                    size=18,
                    color=ft.Colors.WHITE70,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.ElevatedButton(
                    "OK",
                    on_click=on_ok,
                    width=220,
                    height=64,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.WHITE,
                        color=ft.Colors.RED_900,
                        text_style=ft.TextStyle(size=22, weight=ft.FontWeight.BOLD),
                    ),
                ),
            ],
        ),
    )
