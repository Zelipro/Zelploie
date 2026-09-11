"""Notifications desktop (Windows/Linux), §7.6.

Contrairement à Android, l'app desktop est censée tourner en continu
(barre système + démarrage auto — voir tray/desktop_tray.py). Il n'y a
donc pas besoin de programmer les notifications à l'avance auprès de
l'OS : c'est la boucle de vérification vivante de l'app (ui/app.py) qui
détecte les transitions d'état et déclenche l'appel ci-dessous au bon
moment, à partir de l'horloge système.

`plyer` fait le pont vers le toast Windows natif / libnotify sur Linux.
"""

from __future__ import annotations

import logging

from ..models import ActivityOccurrence
from . import base

logger = logging.getLogger(__name__)


def notify_start(occ: ActivityOccurrence) -> None:
    _notify(base.start_title(occ), base.start_body(occ))


def notify_end(occ: ActivityOccurrence) -> None:
    _notify(base.end_title(occ), base.end_body(occ))


def _notify(title: str, message: str) -> None:
    try:
        from plyer import notification

        notification.notify(title=title, message=message, app_name="Zelploie", timeout=10)
    except Exception:
        # Une notification OS manquée ne doit jamais faire planter l'app :
        # l'écran de blocage / le minuteur restent la source de vérité
        # visible à l'écran. On journalise pour diagnostic seulement.
        logger.exception("Échec de la notification desktop (non bloquant)")
