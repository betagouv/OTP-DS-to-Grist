"""Authentification des requêtes par le jeton widget Grist.

Toute route est protégée par défaut : seules les routes déclarées publiques y
échappent. Le jeton widget porte l'identité certifiée par Grist (utilisateur et
document) ; il est vérifié auprès de Grist, puis rapproché de la configuration
visée. Toutes les routes protégées exigent un accès éditeur.
"""

from typing import Any

from flask import Request, Response, g, jsonify
from requests.exceptions import HTTPError

from configuration.config_manager import ConfigManager, ConfigNotFoundError
from grist.base_url import GristBaseUrlNotAllowedError
from grist.client import GristClient
from security.widget_token import (
    BASE_URL_HEADER,
    WidgetTokenInvalidError,
    WidgetTokenUnavailableError,
    decode_widget_token_identity,
    extract_widget_token,
    validate_widget_token,
)
from utils.log import log_error

# Niveaux d'accès de la clé API Grist admis pour enregistrer une configuration :
# la synchronisation écrit dans le document, un accès lecture seule ne suffit pas.
GRIST_KEY_REQUIRED_ACCESS_LEVELS = frozenset({"owners", "editors"})

# Niveau renvoyé quand la clé n'a aucun accès au document (401, 403 ou 404).
GRIST_KEY_NO_ACCESS = "no-access"

# Niveau renvoyé quand Grist n'expose pas le niveau d'accès de la clé :
# indéterminé, la clé est acceptée à titre défensif.
GRIST_KEY_ACCESS_UNSPECIFIED = "unspecified"

# Routes autorisées sans jeton widget. Tout le reste est protégé.
WIDGET_TOKEN_EXEMPT_ENDPOINTS: set[tuple[str, str]] = {
    ("static", "GET"),
    ("index", "GET"),
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
        return _error_response("Jeton widget requis", 401)

    try:
        identity = decode_widget_token_identity(token)
    except WidgetTokenInvalidError:
        return _error_response("Jeton widget invalide", 401)

    data = request.get_json(silent=True) or {}
    otp_config_id = _requested_config_id(request)
    try:
        config = (
            config_manager.load_config_by_id(otp_config_id)
            if otp_config_id is not None
            else None
        )
    except ConfigNotFoundError:
        config = None
    except Exception as e:
        log_error(
            f"Chargement de la configuration {otp_config_id} impossible : {e}"
        )
        return _error_response("Configuration indisponible", 500)

    if config is not None:
        base_url = config.get("grist_base_url")
    else:
        try:
            base_url = _stored_base_url_for_identity(config_manager, identity)
        except Exception as e:
            log_error(
                f"Chargement de la configuration de l'identité impossible : {e}"
            )
            return _error_response("Configuration indisponible", 500)
        if not base_url:
            base_url = (
                request.args.get("grist_base_url")
                or data.get("grist_base_url")
                or data.get("base_url")
                or request.headers.get(BASE_URL_HEADER)
            )

    if not base_url:
        return _error_response("Contexte Grist incomplet", 400)

    try:
        identity = validate_widget_token(
            token, base_url, str(identity.get("docId") or "")
        )
    except GristBaseUrlNotAllowedError as e:
        return _error_response(str(e), 400)
    except WidgetTokenUnavailableError:
        return _error_response("Grist indisponible", 502)
    except WidgetTokenInvalidError:
        return _error_response("Jeton widget invalide", 401)

    g.widget_identity = identity

    if config is not None and not _config_matches_identity(config, identity):
        return _error_response("Forbidden", 403)

    if identity.get("readOnly") is True:
        return _error_response("Accès éditeur requis", 403)

    api_key = data.get("grist_api_key")
    if api_key:
        access_level = _grist_doc_access_level(
            base_url, api_key, str(identity.get("docId") or "")
        )
        if access_level is None:
            return _error_response("Grist indisponible", 502)
        if access_level == GRIST_KEY_NO_ACCESS:
            return _error_response("Clé API sans accès au document Grist", 403)
        if (
            access_level not in GRIST_KEY_REQUIRED_ACCESS_LEVELS
            and access_level != GRIST_KEY_ACCESS_UNSPECIFIED
        ):
            return _error_response(
                "Accès éditeur requis sur le document Grist", 403
            )

    return None


# --- Helpers privés ---


def _is_exempt(request: Request) -> bool:
    """Une route est publique quand son couple (endpoint, méthode) est exempté."""
    if request.endpoint is None:
        return True

    return (request.endpoint, request.method) in WIDGET_TOKEN_EXEMPT_ENDPOINTS


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


def _stored_base_url_for_identity(
    config_manager: ConfigManager, identity: dict[str, Any]
) -> str | None:
    """URL de base Grist de la configuration stockée pour l'identité, si elle existe."""
    user_id = identity.get("userId")
    doc_id = identity.get("docId")
    if not user_id or not doc_id:
        return None

    configs = config_manager.load_config(str(user_id), str(doc_id))
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


def _grist_doc_access_level(base_url: str, api_key: str, doc_id: str) -> str | None:
    """Niveau d'accès de la clé API sur le document ciblé (GET /docs/{docId}).

    Renvoie le niveau retourné par Grist (`owners`, `editors`, `viewers`),
    `GRIST_KEY_NO_ACCESS` quand la clé ne voit pas le document,
    `GRIST_KEY_ACCESS_UNSPECIFIED` quand Grist n'expose pas le niveau, ou
    None quand Grist n'a pas répondu.
    """
    try:
        doc_info = GristClient(base_url, api_key, doc_id).get_document_info()
    except HTTPError as error:
        status_code = (
            error.response.status_code if error.response is not None else None
        )
        if status_code in (401, 403, 404):
            return GRIST_KEY_NO_ACCESS
        log_error(
            f"Consultation du document Grist impossible ({status_code}) : {error}"
        )
        return None
    except Exception as e:
        log_error(f"Vérification de l'accès de la clé API impossible : {e}")
        return None

    access = doc_info.get("access") if isinstance(doc_info, dict) else None
    if not access:
        log_error(
            "Grist n'expose pas le niveau d'accès de la clé : "
            "clé acceptée à titre défensif"
        )
        return GRIST_KEY_ACCESS_UNSPECIFIED

    return str(access)


def _error_response(message: str, status: int) -> tuple[Response, int]:
    return jsonify({"success": False, "message": message}), status
