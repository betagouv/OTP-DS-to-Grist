"""
Vérifications faites avant une synchronisation : les deux APIs (Démarche
Numérique et Grist) doivent répondre avec les accès configurés.
"""

from typing import Literal, TypedDict

from utils.api_validator import test_demarches_api, test_grist_api


class ApiConnectionResult(TypedDict):
    type: Literal["demarches", "grist"]
    success: bool
    message: str


def verify_api_connections(
    ds_token: str,
    demarche_number: str | int,
    grist_base_url: str,
    grist_api_key: str,
    grist_doc_id: str,
) -> tuple[bool, list[ApiConnectionResult]]:
    """
    Teste les connexions aux deux APIs (DS et Grist)

    Args:
        ds_token: Token API Démarches Simplifiées
        demarche_number: Numéro de démarche DS
        grist_base_url: URL de base Grist
        grist_api_key: Clé API Grist
        grist_doc_id: ID du document Grist

    Returns:
        tuple: (success_global: bool, results: list[ApiConnectionResult])
               results contient les résultats individuels de chaque test
    """
    results = []

    # Test Démarches Simplifiées
    ds_success, ds_message, _ds_title = test_demarches_api(ds_token, demarche_number)
    results.append({"type": "demarches", "success": ds_success, "message": ds_message})

    # Test Grist
    grist_success, grist_message = test_grist_api(
        grist_base_url, grist_api_key, grist_doc_id
    )

    results.append(
        {"type": "grist", "success": grist_success, "message": grist_message}
    )

    # Déterminer le succès global
    all_success = all(r["success"] for r in results)

    return all_success, results
