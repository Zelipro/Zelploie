"""Onboarding Android 14+ : autorisation des notifications plein écran (§7.3).

Android 14+ révoque par défaut cette permission pour toute app qui
n'est pas catégorisée "appel"/"réveil" — ce n'est pas un bug, c'est une
étape de configuration à faire accepter une fois par Zeli. Cet écran ne
s'affiche qu'une fois (mémorisé dans device_meta), au tout premier
lancement sur chaque appareil Android.
"""

from __future__ import annotations

import flet as ft

from ..notifications.android import AndroidNotifications
from ..storage import local_db

ONBOARDING_DONE_KEY = "android_onboarding_done"


def onboarding_needed(conn) -> bool:
    return local_db.get_meta(conn, ONBOARDING_DONE_KEY) != "1"


def build_onboarding_screen(
    android_notifs: AndroidNotifications, conn, on_done
) -> ft.Control:
    status_text = ft.Text("", size=14, color=ft.Colors.GREY)

    async def handle_activate(e: ft.ControlEvent) -> None:
        status_text.value = "Demande des permissions en cours..."
        status_text.update()
        result = await android_notifs.request_all_permissions()
        local_db.set_meta(conn, ONBOARDING_DONE_KEY, "1")
        manquantes = [k for k, v in result.items() if not v]
        if manquantes:
            status_text.value = (
                "Permissions manquantes : " + ", ".join(manquantes) + ". "
                "Tu peux les accorder plus tard depuis les réglages Android "
                "(Applications > Zelploie > Notifications)."
            )
            status_text.update()
        await on_done()

    async def handle_skip(e: ft.ControlEvent) -> None:
        local_db.set_meta(conn, ONBOARDING_DONE_KEY, "1")
        await on_done()

    return ft.Container(
        expand=True,
        padding=32,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=20,
            controls=[
                ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE, size=56, color=ft.Colors.BLUE),
                ft.Text(
                    "Autoriser les notifications plein écran",
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Zelploie doit pouvoir réveiller l'écran et afficher "
                    "l'écran de blocage OK à la fin de chaque créneau, "
                    "même téléphone verrouillé. Android 14+ désactive cette "
                    "permission par défaut — il faut l'autoriser une fois ici.",
                    size=14,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.ElevatedButton(
                    "Activer les notifications plein écran",
                    on_click=handle_activate,
                    width=320,
                    height=50,
                ),
                ft.TextButton("Plus tard", on_click=handle_skip),
                status_text,
            ],
        ),
    )
