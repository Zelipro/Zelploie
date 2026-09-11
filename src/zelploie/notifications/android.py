"""Notifications Android via `flet-android-notifications` (§7.1-7.3).

Vérifié sur le vrai package installé (flet-android-notifications
0.10.1, dépend de flet>=0.82.0) :

- L'intent plein écran EST géré nativement par ce package via le
  paramètre `full_screen_intent=True` de `schedule_notification()` —
  contrairement à ce qu'indiquait la veille technique initiale (§7.2).
  Il reste nécessaire de déclarer la permission
  `android.permission.USE_FULL_SCREEN_INTENT` dans pyproject.toml (déjà
  fait) et, sur Android 14+, de l'autoriser explicitement via
  `request_full_screen_intent_permission()` (§7.3) — voir onboarding.py.
- Le patch obligatoire après chaque `flet build apk` propre est un vrai
  script installé avec le package : la commande
  `flet-android-notifications-patch` (voir README "Build Android").
  Il injecte les BroadcastReceivers de `flutter_local_notifications`
  dans AndroidManifest.xml (dont le receiver de redémarrage — sans lui,
  les notifications programmées ne survivent pas à un reboot, §7.1) et
  active le core library desugaring + multidex dans build.gradle.kts.
- Le montage du service sur la page se fait par `page.add(service)`
  (les contrôles `Service` de Flet s'enregistrent eux-mêmes via leur
  hook `init()` dès qu'ils sont montés dans l'arbre de contrôles ; il
  n'y a pas de liste `page.overlay`/`page.services` publique dans cette
  version de Flet — vérifié sur flet==0.86.5).
"""

from __future__ import annotations

import zlib
from typing import TYPE_CHECKING

from flet_android_notifications import FletAndroidNotifications

from ..models import ActivityOccurrence
from . import base

if TYPE_CHECKING:
    import flet as ft

CHANNEL_START = "zelploie_debut"
CHANNEL_END = "zelploie_fin"

# Horizon de PROGRAMMATION Android, volontairement plus court que les 14
# jours de matérialisation locale (occurrence_engine.NOTIFICATION_WINDOW_DAYS).
# Raison technique (pas une préférence produit) : sync_scheduled_notifications
# fait un cancel_all() + reschedule complet à chaque appel pour rester simple
# et ne jamais dériver. Sur 14 jours, ça representerait ~20 blocs/jour x 2
# notifs x 14j ≈ 560 alarmes recreees a chaque ouverture de l'app — lent, et
# de toute façon peu utile : Android (Doze/App Standby) peut retarder des
# alarmes exactes programmées aussi loin dans le futur. 2 jours (~80 alarmes),
# resynchronise a chaque lancement/retour au premier plan, est largement
# suffisant en pratique et reste facile a elargir si besoin.
ANDROID_NOTIFICATION_HORIZON_DAYS = 2


def _notification_id(occ: ActivityOccurrence, suffix: int) -> int:
    """ID entier stable et unique dérivé de l'id textuel de l'occurrence.

    Masqué sur 30 bits puis *2+suffix : garanti < 2^31-1 (int Android).
    """
    base_id = zlib.crc32(occ.id.encode()) & 0x3FFFFFFF
    return base_id * 2 + suffix


class AndroidNotifications:
    def __init__(self, page: "ft.Page"):
        self.page = page
        self.service = FletAndroidNotifications()
        page.add(self.service)

    async def setup_channels(self) -> None:
        await self.service.create_notification_channel(
            CHANNEL_START,
            "Début d'activité",
            channel_description="Notification au début de chaque créneau du planning",
            importance="high",
        )
        await self.service.create_notification_channel(
            CHANNEL_END,
            "Fin d'activité (blocage)",
            channel_description="Écran de blocage obligatoire à la fin d'un créneau",
            importance="max",
        )

    # --- Permissions (§7.1, §7.3) ---------------------------------------

    async def request_all_permissions(self) -> dict[str, bool]:
        """À appeler depuis l'écran d'onboarding au premier lancement."""
        granted_notif = await self.service.request_permissions()
        can_exact = await self.service.can_schedule_exact_notifications()
        if not can_exact:
            can_exact = await self.service.request_exact_alarm_permission()
        granted_full_screen = await self.service.request_full_screen_intent_permission()
        return {
            "notifications": granted_notif,
            "exact_alarm": can_exact,
            "full_screen_intent": granted_full_screen,
        }

    async def all_permissions_granted(self) -> bool:
        return (
            await self.service.are_notifications_enabled()
            and await self.service.can_schedule_exact_notifications()
        )

    # --- Programmation (§5.2, §5.3) --------------------------------------

    async def schedule_start(self, occ: ActivityOccurrence) -> None:
        await self.service.schedule_notification(
            notification_id=_notification_id(occ, 0),
            title=base.start_title(occ),
            body=base.start_body(occ),
            scheduled_time=occ.debut_datetime,
            channel_id=CHANNEL_START,
            channel_name="Début d'activité",
            importance="high",
            schedule_mode="exact_allow_while_idle",
            payload=occ.id,
        )

    async def schedule_end(self, occ: ActivityOccurrence) -> None:
        """Notification de fin en intent plein écran (§5.3) : réveille
        l'écran et ouvre directement l'app sur l'écran de blocage OK,
        même verrouillé."""
        await self.service.schedule_notification(
            notification_id=_notification_id(occ, 1),
            title=base.end_title(occ),
            body=base.end_body(occ),
            scheduled_time=occ.fin_datetime,
            channel_id=CHANNEL_END,
            channel_name="Fin d'activité (blocage)",
            importance="max",
            schedule_mode="exact_allow_while_idle",
            full_screen_intent=True,
            ongoing=True,
            auto_cancel=False,
            category="alarm",
            visibility="public",
            payload=occ.id,
        )

    async def cancel_for_occurrence(self, occ: ActivityOccurrence) -> None:
        await self.service.cancel(_notification_id(occ, 0))
        await self.service.cancel(_notification_id(occ, 1))

    async def sync_scheduled_notifications(self, occurrences: list[ActivityOccurrence]) -> None:
        """Reprogramme les notifications pour la fenêtre glissante
        donnée (§5.2). Annule d'abord tout pour éviter les doublons
        obsolètes si le gabarit a changé entre deux lancements."""
        await self.service.cancel_all()
        for occ in occurrences:
            if occ.acquitte:
                continue
            await self.schedule_start(occ)
            await self.schedule_end(occ)
