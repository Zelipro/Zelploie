"""Synchronisation Supabase (§6).

Important : ce module ne fait JAMAIS partie du chemin critique de
lecture au démarrage (voir planning/occurrence_engine.py, qui ne lit
que la base locale). Il pousse/reçoit en tâche de fond les mêmes
occurrences, pour que le clic OK sur un appareil ferme aussi l'écran de
blocage des autres.

⚠️ Choix technique vérifié (pas une supposition) : dans la version de
`supabase-py` utilisée ici (2.31.0, dépendance `realtime`), le canal
Realtime du client SYNCHRONE (`SyncRealtimeChannel`) est un stub non
implémenté (aucune méthode). Seul le client ASYNCHRONE
(`create_async_client` / `AsyncClient`) a un canal Realtime
fonctionnel. Ce module utilise donc systématiquement l'API async, ce
qui s'intègre naturellement à Flet (déjà basé sur asyncio — on lance ce
module via `page.run_task(...)`).

Configuration : URL et clé anon lues depuis des variables
d'environnement, jamais codées en dur ni commitées (voir README
"Configuration Supabase").
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Awaitable, Callable, Optional

from supabase import AsyncClient, acreate_client

from ..models import ActivityOccurrence
from ..storage import local_db

TABLE_NAME = "activity_occurrence"

# Fenêtre glissante de synchro (§4.2) : on ne s'abonne / ne retélécharge
# que les occurrences des N derniers jours, pas tout l'historique.
SYNC_WINDOW_DAYS = 7


class SupabaseConfigError(RuntimeError):
    pass


@dataclass
class SupabaseConfig:
    url: str
    anon_key: str

    @staticmethod
    def from_env() -> "SupabaseConfig":
        url = os.environ.get("ZELPLOIE_SUPABASE_URL")
        key = os.environ.get("ZELPLOIE_SUPABASE_ANON_KEY")
        if not url or not key:
            raise SupabaseConfigError(
                "ZELPLOIE_SUPABASE_URL et ZELPLOIE_SUPABASE_ANON_KEY doivent être "
                "définies (voir README section 'Configuration Supabase'). "
                "La synchronisation multi-appareils est désactivée sans ça, "
                "mais l'app reste utilisable en local (§3 : le réseau n'est "
                "jamais requis pour le fonctionnement de base)."
            )
        return SupabaseConfig(url=url, anon_key=key)


class SupabaseSync:
    """Un abonnement Realtime + push/pull, propre à ce process d'app."""

    def __init__(
        self,
        config: SupabaseConfig,
        conn,
        device_id: str,
        on_remote_change: Optional[Callable[[ActivityOccurrence], None]] = None,
    ):
        """
        conn : connexion sqlite3 locale (storage/local_db.py).
        device_id : identifiant stable de cet appareil (local_db.get_or_create_device_id).
        on_remote_change : callback synchrone appelé après qu'une mise à
            jour distante a été fusionnée en local (via last-write-wins) —
            typiquement utilisé par l'UI pour rafraîchir/fermer un écran
            de blocage si l'occurrence affichée vient d'être acquittée
            depuis un autre appareil.
        """
        self._config = config
        self._conn = conn
        self._device_id = device_id
        self._on_remote_change = on_remote_change
        self._client: Optional[AsyncClient] = None
        self._channel = None

    async def connect(self) -> None:
        self._client = await acreate_client(self._config.url, self._config.anon_key)

    async def pull_recent(self, since: Optional[date] = None) -> int:
        """Récupère l'état déjà présent côté serveur pour la fenêtre
        récente et le fusionne en local (last-write-wins). À appeler une
        fois au démarrage, avant de compter uniquement sur le flux
        Realtime, pour rattraper ce qui a changé pendant que cet
        appareil était hors-ligne."""
        assert self._client is not None, "appeler connect() d'abord"
        since = since or (date.today() - timedelta(days=SYNC_WINDOW_DAYS))
        response = (
            await self._client.table(TABLE_NAME)
            .select("*")
            .gte("date", since.isoformat())
            .execute()
        )
        merged = 0
        for row in response.data:
            occ = ActivityOccurrence.from_dict(row)
            if local_db.upsert_occurrence_if_newer(self._conn, occ):
                merged += 1
                if self._on_remote_change:
                    self._on_remote_change(occ)
        return merged

    async def start_realtime(self, since: Optional[date] = None) -> None:
        """S'abonne aux changements de la table, filtrés sur la fenêtre
        glissante (§4.2), et fusionne chaque événement en local."""
        assert self._client is not None, "appeler connect() d'abord"
        since = since or (date.today() - timedelta(days=SYNC_WINDOW_DAYS))

        from realtime import RealtimePostgresChangesListenEvent

        channel = self._client.channel(f"activity_occurrence_sync_{self._device_id}")
        channel.on_postgres_changes(
            RealtimePostgresChangesListenEvent.All,
            schema="public",
            table=TABLE_NAME,
            filter=f"date=gte.{since.isoformat()}",
            callback=self._handle_postgres_change,
        )
        await channel.subscribe()
        self._channel = channel

    def _handle_postgres_change(self, payload: dict) -> None:
        record = payload.get("data", {}).get("record")
        if not record:
            return  # DELETE (pas utilisé par cette app) ou payload incomplet
        occ = ActivityOccurrence.from_dict(record)
        if local_db.upsert_occurrence_if_newer(self._conn, occ):
            if self._on_remote_change:
                self._on_remote_change(occ)

    async def push_occurrence(self, occ: ActivityOccurrence) -> None:
        """Pousse l'état local (typiquement après un clic OK, §5.3) vers
        Supabase. Le trigger `updated_at` côté client (models.py) sert de
        départage last-write-wins pour les autres appareils."""
        assert self._client is not None, "appeler connect() d'abord"
        await self._client.table(TABLE_NAME).upsert(occ.to_dict()).execute()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.remove_all_channels()
