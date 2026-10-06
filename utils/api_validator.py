"""
Validation des connexions aux APIs externes (Démarches Simplifiées et Grist)
Fonctions pures sans Flask, utilisables par app.py et les scripts CLI
"""

import requests
from typing import Literal, TypedDict
import logging

from .constants import DEMARCHES_API_URL
from grist.base_url import GristBaseUrlNotAllowedError
from grist.client import GristClient

logger = logging.getLogger(__name__)


class ApiConnectionResult(TypedDict):
    type: Literal["demarches", "grist"]
    success: bool
    message: str


def test_demarches_api(
    api_token: str, demarche_number: str | int
) -> tuple[bool, str, str | None]:
    """
    Teste la connexion à l'API Démarches Simplifiées

    Args:
        api_token: Token d'authentification DS
        demarche_number: Numéro de démarche

    Returns:
        tuple: (success: bool, message: str, title: str | None)
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        if not demarche_number:
            return False, "demarche_number manquant", None

        query = """
        query getDemarche($demarcheNumber: Int!) {
            demarche(number: $demarcheNumber) {
                id
                number
                title
            }
        }
        """
        variables = {"demarcheNumber": int(demarche_number)}
        response = requests.post(
            DEMARCHES_API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=10,
            verify=True,
        )

        result = response.json()

        if response.status_code != 200:
            result.get("errors")
            error_messages = [
                e.get("message", "Erreur inconnue") for e in result["errors"]
            ]
            error_text = "; ".join(error_messages)
            if any("expired" in msg.lower() for msg in error_messages):
                return False, "Token expiré", None
            return (
                False,
                f"Erreur de connexion à l'API: {response.status_code} - {error_text}",
                None,
            )

        if "errors" in result:
            return (
                False,
                f"Erreur API: {
                    '; '.join(
                        [e.get('message', 'Erreur inconnue') for e in result['errors']]
                    )
                }",
                None,
            )

        if "data" not in result or "demarche" not in result["data"]:
            return False, "Réponse API inattendue.", None

        demarche = result["data"]["demarche"]

        if demarche:
            title = demarche.get("title", "Sans titre")
            return True, f"Connexion réussie! Démarche trouvée: {title}", title

        return False, f"Démarche {demarche_number} non trouvée.", None

    except requests.exceptions.Timeout:
        return False, "Timeout: L'API met trop de temps à répondre", None

    except Exception:
        logger.exception(
            "Erreur inattendue lors du test de l'API Démarches Simplifiées"
        )
        return False, "Erreur de connexion à l'API Démarches Simplifiées", None


def test_grist_api(base_url: str, api_key: str, doc_id: str) -> tuple[bool, str]:
    """
    Teste la connexion à l'API Grist

    Args:
        base_url: URL de base de l'API Grist
        api_key: Clé d'API Grist
        doc_id: ID du document Grist

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        client = GristClient(base_url, api_key, doc_id)
        doc_info = client.get_document_info()
        doc_name = (
            doc_info.get("name", doc_id) if isinstance(doc_info, dict) else doc_id
        )

        return True, f"Connexion à Grist réussie! Document: {doc_name}"

    except GristBaseUrlNotAllowedError as error:
        # Instance hors liste blanche : aucune requête n'a été émise. Le message
        # est renvoyé tel quel à l'appelant, qui répond en 200 avec success=false.
        return False, str(error)

    except requests.exceptions.JSONDecodeError:
        # Réponse 200 mais corps illisible : la connectivité est établie.
        return True, f"Connexion à Grist réussie! Document ID: {doc_id}"

    except requests.exceptions.HTTPError as error:
        response = error.response
        if response is None:
            return False, f"Erreur de connexion à Grist: {error}"
        return (
            False,
            f"Erreur de connexion à Grist: {response.status_code} - {response.text}",
        )

    except requests.exceptions.Timeout:
        return False, "Timeout: L'API Grist met trop de temps à répondre"

    except Exception:
        logger.exception("Erreur inattendue lors du test de l'API Grist")
        return False, "Erreur de connexion à l'API Grist"


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
