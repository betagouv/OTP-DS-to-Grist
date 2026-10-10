"""Authentification des requêtes par le jeton widget Grist.

Toute route est protégée par défaut : seules les routes déclarées publiques y
échappent. Le jeton widget porte l'identité certifiée par Grist (utilisateur et
document) ; il est vérifié auprès de Grist, puis rapproché de la configuration
visée. Toutes les routes protégées exigent un accès éditeur.
"""

import logging
from typing import Any

from flask import Request, Response, g, jsonify

from configuration.config_manager import ConfigManager
from grist.base_url import GristBaseUrlNotAllowedError
from grist.client import GristClient
from security.widget_token import (
    WidgetTokenInvalidError,
    WidgetTokenUnavailableError,
    decode_widget_token_identity,
    extract_widget_token,
    validate_widget_token,
)

logger = logging.getLogger(__name__)

# Routes autorisées sans jeton widget. Tout le reste est protégé.
WIDGET_TOKEN_EXEMPT_ENDPOINTS: set[tuple[str, str]] = {
    ("static", "GET"),
    ("index", "GET"),
    ("execution", "GET"),
    ("wip", "GET"),
}


def authorize_request(
    request: Request, config_manager: ConfigManager
) -> tuple[Response, int] | None:
    """Contrôle le jeton widget et l'accès à la configuration visée."""
    if _is_exempt(request):
        return None

    token = extract_widget_token(request.headers)
    if token is None:
        return _error("Jeton widget requis", 401)

    try:
        identity = decode_widget_token_identity(token)
    except WidgetTokenInvalidError:
        return _error("Jeton widget invalide", 401)

    data = request.get_json(silent=True) or {}
    otp_config_id = _requested_config_id(request)
    config = (
        _load_config_by_id(config_manager, otp_config_id)
        if otp_config_id is not None
        else None
    )
    if config is not None:
        base_url = config.get("grist_base_url")
    else:
        base_url = _stored_base_url_for_identity(config_manager, identity)
        if not base_url:
            base_url = (
                request.args.get("grist_base_url")
                or data.get("grist_base_url")
                or data.get("base_url")
            )

    if not base_url:
        if _is_new_user_config_request(request, identity):
            g.widget_identity = identity
            return None

        return _error("Contexte Grist incomplet", 400)

    try:
        identity = validate_widget_token(
            token, base_url, str(identity.get("docId") or "")
        )
    except GristBaseUrlNotAllowedError as e:
        return _error(str(e), 400)
    except WidgetTokenUnavailableError:
        return _error("Grist indisponible", 502)
    except WidgetTokenInvalidError:
        return _error("Jeton widget invalide", 401)

    g.widget_identity = identity

    if config is not None and not _config_matches_identity(config, identity):
        return _error("Forbidden", 403)

    if identity.get("readOnly") is True:
        return _error("Accès éditeur requis", 403)

    api_key = data.get("grist_api_key")
    if api_key:
        owner_id = _grist_key_owner_id(base_url, api_key)
        if owner_id is None:
            return _error("Grist indisponible", 502)
        if str(owner_id) != str(identity.get("userId")):
            return _error("Clé API d'un autre utilisateur", 403)

    return None


# --- Helpers privés ---


def _is_exempt(request: Request) -> bool:
    """Une route est publique quand son couple (endpoint, méthode) est exempté."""
    if request.endpoint is None:
        return True

    return (request.endpoint, request.method) in WIDGET_TOKEN_EXEMPT_ENDPOINTS


def _is_new_user_config_request(request: Request, identity: dict[str, Any]) -> bool:
    """Livre la configuration vide d'un nouvel utilisateur, sans données stockées."""
    if (request.endpoint, request.method) != ("api_config", "GET"):
        return False

    return bool(identity.get("userId")) and bool(identity.get("docId"))


def _requested_config_id(request: Request) -> int | None:
    """Identifiant de configuration porté par la route, les arguments ou le corps."""
    view_args = request.view_args or {}
    if view_args.get("otp_config_id") is not None:
        return view_args["otp_config_id"]

    raw_id = request.args.get("otp_config_id")
    if raw_id is None:
        data = request.get_json(silent=True) or {}
        raw_id = data.get("otp_config_id")

    try:
        return int(raw_id)
    except (TypeError, ValueError):
        return None


def _load_config_by_id(
    config_manager: ConfigManager, otp_config_id: int
) -> dict[str, Any] | None:
    try:
        return config_manager.load_config_by_id(otp_config_id)
    except Exception:
        return None


def _stored_base_url_for_identity(
    config_manager: ConfigManager, identity: dict[str, Any]
) -> str | None:
    """URL de base Grist de la configuration stockée pour l'identité, si elle existe."""
    user_id = identity.get("userId")
    doc_id = identity.get("docId")
    if not user_id or not doc_id:
        return None

    try:
        configs = config_manager.load_config(str(user_id), str(doc_id))
    except Exception:
        return None

    config = next(
        (config for config in configs if config.get("otp_config_id") is not None),
        None,
    )

    return config.get("grist_base_url") if config else None


def _config_matches_identity(
    config: dict[str, Any], identity: dict[str, Any]
) -> bool:
    return str(
        config.get("grist_user_id")
    ) == str(identity.get("userId")) and str(
        config.get("grist_doc_id")
    ) == str(identity.get("docId"))


def _grist_key_owner_id(base_url: str, api_key: str) -> int | str | None:
    """Propriétaire de la clé API Grist, ou None si Grist n'a pas répondu."""
    try:
        profile = GristClient(base_url, api_key).get_profile()
    except Exception as e:
        logger.error("Vérification de la clé API Grist impossible : %s", e)
        return None

    return profile.get("id")


def _error(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"success": False, "message": message}), status
