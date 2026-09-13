"""Écran de saisie / import de l'emploi du temps (v2, demande de Zeli).

Au tout premier lancement (ou après suppression du fichier
~/.zelploie/emploi_zeli.txt), l'app affiche cet écran au lieu de
démarrer directement. Zeli peut soit coller le texte (typiquement
généré par une IA à partir de sa description libre — voir
docs/prompt_ia_emploi_du_temps.md), soit importer un fichier .txt déjà
préparé. Rien n'est deviné : toute erreur de format est listée
explicitement, ligne par ligne, sans rien enregistrer tant que ça ne
parse pas.
"""

from __future__ import annotations

from typing import Awaitable, Callable

import flet as ft

from ..schedule_text_format import (
    DEFAULT_SCHEDULE_PATH,
    ScheduleFormatError,
    save_schedule_text,
)

OnScheduleReady = Callable[[], Awaitable[None]]


def build_schedule_setup_screen(
    page: ft.Page, on_ready: OnScheduleReady, exemple_texte: str
) -> ft.Control:
    text_field = ft.TextField(
        label="Colle ici ton emploi du temps",
        multiline=True,
        min_lines=10,
        max_lines=16,
        expand=True,
        text_size=13,
    )
    erreurs_view = ft.Column(spacing=2, scroll=ft.ScrollMode.AUTO, height=140, visible=False)
    status_text = ft.Text("", size=13)

    file_picker = ft.FilePicker()
    page.add(file_picker)

    def afficher_erreurs(erreurs: list[str]) -> None:
        erreurs_view.controls = [
            ft.Text(f"• {e}", size=12, color=ft.Colors.RED_700) for e in erreurs
        ]
        erreurs_view.visible = True
        erreurs_view.update()

    async def handle_valider(e: ft.ControlEvent) -> None:
        status_text.value = ""
        erreurs_view.visible = False
        if not (text_field.value or "").strip():
            status_text.value = "Le champ est vide."
            status_text.update()
            return
        try:
            save_schedule_text(text_field.value, path=DEFAULT_SCHEDULE_PATH)
        except ScheduleFormatError as err:
            afficher_erreurs(err.errors)
            return
        await on_ready()

    async def handle_charger_fichier(e: ft.ControlEvent) -> None:
        fichiers = await file_picker.pick_files(
            dialog_title="Choisir le fichier de l'emploi du temps",
            allowed_extensions=["txt"],
            with_data=True,
        )
        if not fichiers:
            return
        picked = fichiers[0]
        if picked.bytes is not None:
            text_field.value = picked.bytes.decode("utf-8", errors="replace")
        elif picked.path:
            text_field.value = open(picked.path, encoding="utf-8").read()
        text_field.update()

    def handle_exemple(e: ft.ControlEvent) -> None:
        text_field.value = exemple_texte
        text_field.update()

    return ft.Container(
        expand=True,
        padding=24,
        content=ft.Column(
            expand=True,
            spacing=14,
            controls=[
                ft.Text("Configurer ton emploi du temps", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Colle ton planning au format : Jour | Début | Fin | Activité "
                    "(colonnes Catégorie / Salle / Variante optionnelles). "
                    "Utilise l'IA avec le prompt fourni si ta description est libre.",
                    size=13,
                    color=ft.Colors.GREY,
                ),
                text_field,
                erreurs_view,
                ft.Row(
                    controls=[
                        ft.ElevatedButton("Valider", on_click=handle_valider),
                        ft.OutlinedButton("Importer un fichier .txt", on_click=handle_charger_fichier),
                        ft.TextButton("Voir un exemple", on_click=handle_exemple),
                    ]
                ),
                status_text,
            ],
        ),
    )
