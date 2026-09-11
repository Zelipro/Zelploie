"""Icône de barre système desktop (Windows/Linux), §7.6.

Flet n'a pas de contrôle "tray icon" intégré (vérifié sur flet==0.86.5 :
aucun `ft.Tray*`). On utilise `pystray` en parallèle de la boucle
asyncio de Flet, via `run_detached()` — conçu précisément pour
s'intégrer à la mainloop d'une autre bibliothèque plutôt que de bloquer
le thread principal (contrairement à `Icon.run()`).

⚠️ À vérifier sur un vrai poste Windows/Ubuntu avec écran : cet
environnement de développement est headless (pas de serveur
d'affichage), donc ce module n'a pas pu être testé visuellement ici
(pystray échoue même à s'importer sans display X11/Windows réel). Les
callbacks du menu s'exécutent sur le thread interne de pystray ; si des
soucis de thread-safety apparaissent en conditions réelles avec les
appels `page.update()`, le recours standard est de repasser par
`page.run_task(...)` depuis le callback pour revenir sur la boucle
asyncio de Flet.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import flet as ft

logger = logging.getLogger(__name__)


def _make_icon_image():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=(30, 136, 229, 255))
    return img


class DesktopTray:
    """Réduit la fenêtre dans la barre système au lieu de fermer l'app
    (§7.6, option (a) recommandée et confirmée par Zeli)."""

    def __init__(self, page: "ft.Page"):
        self.page = page
        self._icon = None

    def start(self) -> None:
        try:
            import pystray
        except Exception:
            logger.exception("pystray indisponible : le tray desktop est désactivé pour cette session.")
            return

        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir Zelploie", self._show_window, default=True),
            pystray.MenuItem("Quitter", self._quit),
        )
        self._icon = pystray.Icon("zelploie", _make_icon_image(), "Zelploie", menu)
        self._icon.run_detached()

        # Fermer la fenêtre (croix) minimise vers le tray au lieu de
        # quitter le process — l'app doit continuer à tourner pour que
        # le minuteur et les notifications restent fiables (§7.6).
        self.page.window.prevent_close = True
        self.page.window.on_event = self._on_window_event

    def _on_window_event(self, e) -> None:
        if getattr(e, "type", None) is not None and str(e.type).lower().endswith("close"):
            self.page.window.visible = False
            self.page.window.skip_task_bar = True
            self.page.update()

    def _show_window(self, icon=None, item=None) -> None:
        self.page.window.visible = True
        self.page.window.skip_task_bar = False
        self.page.window.minimized = False
        self.page.window.focused = True
        self.page.update()

    def _quit(self, icon=None, item=None) -> None:
        if self._icon is not None:
            self._icon.stop()
        self.page.window.prevent_close = False
        self.page.window.destroy()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
