"""
Suivi en direct des synchronisations, par websocket.

Le serveur émet les événements task_update (via le notify_callback de
SyncManager) ; une page rouverte demande l'état complet par le message
sync_state.
"""

import logging
from typing import Any

from flask import Flask
from flask_socketio import SocketIO

from sync.sync_manager import SyncManager

logger = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", async_mode="gevent")


def init_live_tracking(app: Flask, sync_manager: SyncManager) -> None:
    """Branche le websocket sur l'application et déclare ses événements."""
    socketio.init_app(app)

    @socketio.on("connect")
    def handle_connect():
        """Gestion de la connexion WebSocket"""
        logger.info("Client connecté")

    @socketio.on("disconnect")
    def handle_disconnect():
        """Gestion de la déconnexion WebSocket"""
        logger.info("Client déconnecté")

    @socketio.on("sync_state")
    def handle_sync_state(data: dict[str, str] | None) -> list[dict[str, Any]]:
        """
        État complet des synchros d'un utilisateur sur un document, renvoyé en
        accusé de réception : une page rouverte reprend ainsi l'affichage d'une
        synchro en cours. Non authentifié, comme les événements task_update.
        """
        data = data or {}

        return sync_manager.sync_state(
            str(data.get("grist_user_id") or ""), str(data.get("grist_doc_id") or "")
        )
