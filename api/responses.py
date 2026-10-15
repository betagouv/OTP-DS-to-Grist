"""Réponses HTTP standardisées de la couche API."""

from flask import Response, jsonify


def error_response(message: str, status: int) -> tuple[Response, int]:
    """Réponse JSON d'erreur standardisée."""
    return jsonify({"success": False, "message": message}), status


def config_not_found_response(otp_config_id: int | str) -> tuple[Response, int]:
    """404 référençant la configuration demandée."""
    return error_response(f"Configuration non trouvée (id={otp_config_id})", 404)
