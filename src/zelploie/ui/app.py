"""Orchestration principale de l'app Flet (§5, §7.5, §7.6).

Distinction importante, volontaire, entre deux mécanismes différents :

- `_cold_resolve()` : résolution "à froid", utilisée UNIQUEMENT au
  lancement et au retour au premier plan (§5.1). C'est le seul moment
  où on a le droit de "sauter" en avant par rapport à l'état affiché
  précédemment — c'est exactement là que s'applique la règle
  "pas de rattrapage" (§3), parce que l'app a pu manquer du temps
  (device éteint, app tuée en arrière-plan, etc.).

- `_live_tick()` : exécuté chaque seconde pendant que l'app tourne déjà
  au premier plan. Il ne fait QUE avancer vers l'état suivant à partir
  de ce qui est actuellement affiché — en particulier, une fois l'écran
  de blocage affiché pour un créneau, il y RESTE tant que OK n'a pas
  été cliqué, même si un créneau suivant a entre-temps commencé dans la
  vraie vie. Sans cette distinction, le simple fait de laisser filer le
  temps sans toucher l'app suffirait à contourner le blocage — ce qui
  contredirait le caractère "quasi contraignant" recherché (§1).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import flet as ft

from ..models import ActivityOccurrence, EtatCourant
from ..notifications import desktop as desktop_notif
from ..planning import occurrence_engine
from ..schedule_text_format import DEFAULT_SCHEDULE_PATH
from ..storage import local_db
from ..sync.supabase_sync import SupabaseConfig, SupabaseConfigError, SupabaseSync
from . import onboarding
from .block_screen import build_block_screen
from .schedule_setup import build_schedule_setup_screen
from .timer_view import build_timer_view

logger = logging.getLogger(__name__)

TICK_SECONDS = 1
RESYNC_ANDROID_NOTIFICATIONS_EVERY_SECONDS = 300


class ZelploieApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.conn = local_db.connect()
        self.device_id = local_db.get_or_create_device_id(self.conn)
        self.template = None  # chargé une fois l'emploi du temps disponible, voir _ensure_schedule_ready

        self.is_android = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.ANDROID_TV)
        self.is_desktop = page.platform in (ft.PagePlatform.WINDOWS, ft.PagePlatform.LINUX, ft.PagePlatform.MACOS)

        self.android_notifs = None
        self.tray = None
        self.sync: SupabaseSync | None = None

        self.root = ft.Container(expand=True)

        # État "sticky" actuellement affiché (voir docstring du module).
        self._mode: EtatCourant | None = None
        self._occurrence: ActivityOccurrence | None = None
        self._prochaine: ActivityOccurrence | None = None

        self._window_forced_fullscreen = False
        self._notified_start_id: str | None = None
        self._notified_end_id: str | None = None
        self._seconds_since_android_resync = 0

    # ------------------------------------------------------------------
    # Démarrage
    # ------------------------------------------------------------------

    async def build(self) -> None:
        self.page.title = "Zelploie"
        self.page.padding = 0
        self.page.window.width = 480
        self.page.window.height = 720
        self.page.add(self.root)

        if self.is_android:
            from ..notifications.android import AndroidNotifications

            self.android_notifs = AndroidNotifications(self.page)
            await self.android_notifs.setup_channels()

        if self.is_desktop:
            from ..tray.desktop_tray import DesktopTray

            self.tray = DesktopTray(self.page)
            self.tray.start()

        await self._connect_sync()

        self.page.on_app_lifecycle_state_change = self._handle_lifecycle_change

        await self._ensure_schedule_ready()

    async def _ensure_schedule_ready(self) -> None:
        """Étape ajoutée en v2 (demande de Zeli) : au tout premier
        lancement — ou après suppression de ~/.zelploie/emploi_zeli.txt —
        demander l'emploi du temps avant de démarrer normalement, plutôt
        que d'embarquer un planning figé dans l'app compilée."""
        if DEFAULT_SCHEDULE_PATH.exists():
            self.template = occurrence_engine.load_schedule_template(DEFAULT_SCHEDULE_PATH)
            await self._proceed_after_schedule_ready()
            return

        exemple_texte = occurrence_engine.DEFAULT_TEMPLATE_PATH.read_text(encoding="utf-8")
        self.root.content = build_schedule_setup_screen(self.page, self._finish_schedule_setup, exemple_texte)
        self.page.update()

    async def _finish_schedule_setup(self) -> None:
        self.template = occurrence_engine.load_schedule_template(DEFAULT_SCHEDULE_PATH)
        await self._proceed_after_schedule_ready()

    async def _proceed_after_schedule_ready(self) -> None:
        if self.is_android and onboarding.onboarding_needed(self.conn):
            self.root.content = onboarding.build_onboarding_screen(
                self.android_notifs, self.conn, self._finish_onboarding
            )
            self.page.update()
        else:
            await self._cold_resolve()

        self.page.run_task(self._run_loop)

    async def _connect_sync(self) -> None:
        try:
            config = SupabaseConfig.from_env()
        except SupabaseConfigError as e:
            logger.warning("Synchronisation Supabase désactivée : %s", e)
            return
        try:
            self.sync = SupabaseSync(config, self.conn, self.device_id, on_remote_change=self._on_remote_change)
            await self.sync.connect()
            await self.sync.pull_recent()
            await self.sync.start_realtime()
        except Exception:
            logger.exception("Échec de connexion à Supabase (non bloquant, l'app reste utilisable en local).")
            self.sync = None

    async def _finish_onboarding(self) -> None:
        await self._cold_resolve()

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            try:
                await self._live_tick()
            except Exception:
                logger.exception("Erreur pendant le tick — on continue à la prochaine itération.")

            self._seconds_since_android_resync += TICK_SECONDS
            if (
                self.is_android
                and self.android_notifs is not None
                and self._seconds_since_android_resync >= RESYNC_ANDROID_NOTIFICATIONS_EVERY_SECONDS
            ):
                self._seconds_since_android_resync = 0
                await self._resync_android_notifications()

    async def _handle_lifecycle_change(self, e: ft.ControlEvent) -> None:
        if e.state in (ft.AppLifecycleState.RESUME, ft.AppLifecycleState.SHOW):
            await self._cold_resolve()

    # ------------------------------------------------------------------
    # Résolution "à froid" (§5.1) — lancement / retour au premier plan
    # ------------------------------------------------------------------

    async def _cold_resolve(self) -> None:
        now = datetime.now()
        etat = occurrence_engine.resolve_current_state(self.conn, self.template, now=now)
        self._mode = etat.etat
        self._occurrence = etat.occurrence
        self._prochaine = etat.prochaine_occurrence
        self._apply_window_state()
        if self._mode == EtatCourant.A_ACQUITTER and self._occurrence:
            self._notify_end_if_needed(self._occurrence)
        elif self._mode == EtatCourant.EN_COURS and self._occurrence:
            self._notify_start_if_needed(self._occurrence)
        self._render(now)

        if self.is_android and self.android_notifs is not None:
            await self._resync_android_notifications()

    # ------------------------------------------------------------------
    # Avancement "à chaud" (tick vivant) — jamais de saut en arrière
    # ------------------------------------------------------------------

    async def _live_tick(self) -> None:
        now = datetime.now()
        occurrence_engine.ensure_occurrences_materialized(
            self.conn, self.template, now.date(), now.date() + timedelta(days=1)
        )

        if self._mode == EtatCourant.EN_COURS and self._occurrence:
            if now >= self._occurrence.fin_datetime:
                frais = local_db.get_occurrence(self.conn, self._occurrence.id)
                if frais is not None and not frais.acquitte:
                    self._mode = EtatCourant.A_ACQUITTER
                    self._occurrence = frais
                    self._apply_window_state()
                    self._notify_end_if_needed(frais)
                else:
                    # Déjà acquitté entre-temps (sync distante) : on peut
                    # se permettre une vraie résolution à froid ici.
                    await self._cold_resolve()
                    return
            self._render(now)
            return

        if self._mode == EtatCourant.A_ACQUITTER and self._occurrence:
            # Sticky : ne bouge que si acquitté (localement ou depuis un
            # autre appareil via Supabase Realtime) — jamais parce que le
            # temps a simplement continué de s'écouler (§1, §3).
            frais = local_db.get_occurrence(self.conn, self._occurrence.id)
            if frais is not None and frais.acquitte:
                await self._cold_resolve()
                return
            self._render(now)
            return

        if self._mode == EtatCourant.LIBRE:
            if self._prochaine is not None and now >= self._prochaine.debut_datetime:
                await self._cold_resolve()
                return
            self._render(now)
            return

        # Aucun état encore résolu (ne devrait arriver qu'avant le tout
        # premier _cold_resolve, ex. pendant l'onboarding).
        return

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------

    def _render(self, now: datetime) -> None:
        if self._mode == EtatCourant.A_ACQUITTER and self._occurrence:
            self.root.content = build_block_screen(self._occurrence, self._make_ok_handler(self._occurrence))
        else:
            from ..models import EtatPlanning

            etat = EtatPlanning(self._mode or EtatCourant.LIBRE, self._occurrence, self._prochaine)
            self.root.content = build_timer_view(etat, now=now)
        self.page.update()

    def _apply_window_state(self) -> None:
        if not self.is_desktop:
            return
        if self._mode == EtatCourant.A_ACQUITTER and not self._window_forced_fullscreen:
            self.page.window.full_screen = True
            self.page.window.always_on_top = True
            self.page.window.frameless = True
            self.page.window.title_bar_hidden = True
            self.page.window.prevent_close = True
            self.page.window.skip_task_bar = False
            self.page.window.visible = True
            self.page.window.focused = True
            self._window_forced_fullscreen = True
        elif self._mode != EtatCourant.A_ACQUITTER and self._window_forced_fullscreen:
            self.page.window.full_screen = False
            self.page.window.always_on_top = False
            self.page.window.frameless = False
            self.page.window.title_bar_hidden = False
            self._window_forced_fullscreen = False

    # ------------------------------------------------------------------
    # Notifications déclenchées en direct (desktop uniquement — Android
    # passe par des alarmes pré-programmées, voir notifications/android.py)
    # ------------------------------------------------------------------

    def _notify_start_if_needed(self, occ: ActivityOccurrence) -> None:
        if self.is_desktop and self._notified_start_id != occ.id:
            desktop_notif.notify_start(occ)
            self._notified_start_id = occ.id

    def _notify_end_if_needed(self, occ: ActivityOccurrence) -> None:
        if self.is_desktop and self._notified_end_id != occ.id:
            desktop_notif.notify_end(occ)
            self._notified_end_id = occ.id

    # ------------------------------------------------------------------
    # Synchronisation multi-appareils
    # ------------------------------------------------------------------

    def _on_remote_change(self, occ: ActivityOccurrence) -> None:
        """Callback synchrone de supabase_sync (§6). Si l'occurrence
        affichée vient d'être acquittée depuis un autre appareil, on
        ferme l'écran de blocage local sans que Zeli ait à recliquer OK."""
        if self._occurrence is not None and self._occurrence.id == occ.id and occ.acquitte:
            self.page.run_task(self._cold_resolve)

    async def _resync_android_notifications(self) -> None:
        from ..notifications.android import ANDROID_NOTIFICATION_HORIZON_DAYS

        now = datetime.now()
        occs = local_db.list_occurrences_in_range(
            self.conn, now, now + timedelta(days=ANDROID_NOTIFICATION_HORIZON_DAYS)
        )
        await self.android_notifs.sync_scheduled_notifications(occs)

    # ------------------------------------------------------------------
    # Clic OK (§5.3)
    # ------------------------------------------------------------------

    def _make_ok_handler(self, occ: ActivityOccurrence):
        async def handler(e: ft.ControlEvent) -> None:
            local_db.mark_acquitte(self.conn, occ.id, self.device_id)
            updated = local_db.get_occurrence(self.conn, occ.id)

            if self.sync is not None and updated is not None:
                try:
                    await self.sync.push_occurrence(updated)
                except Exception:
                    logger.exception(
                        "Échec de la synchronisation Supabase après clic OK "
                        "(non bloquant : l'acquittement local est déjà enregistré)."
                    )

            if self.is_android and self.android_notifs is not None and updated is not None:
                await self.android_notifs.cancel_for_occurrence(updated)

            await self._cold_resolve()

        return handler


async def main(page: ft.Page) -> None:
    app = ZelploieApp(page)
    await app.build()
