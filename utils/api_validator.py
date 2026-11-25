"""
Validation des connexions aux APIs externes (Démarches Simplifiées et Grist)
Fonctions pures sans Flask, utilisables par app.py et les scripts CLI
"""

import requests
import logging

from .constants import DEMARCHES_API_URL
from grist.base_url import GristBaseUrlNotAllowedError
from grist.utils import (
    GristKeyAccessError,
    GristUnavailableError,
    require_owner_access,
)

logger = logging.getLogger(__name__)


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
    Teste la connexion à l'API Grist : seule une clé propriétaire du document
    réussit (règle commune de `grist.utils.require_owner_access`).

    Args:
        base_url: URL de base de l'API Grist
        api_key: Clé d'API Grist
        doc_id: ID du document Grist

    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        doc_info = require_owner_access(base_url, api_key, doc_id)

        return True, f"Connexion à Grist réussie! Document: {doc_info.get('name', doc_id)}"

    except GristBaseUrlNotAllowedError as error:
        # Instance hors liste blanche : aucune requête n'a été émise. Le message
        # est renvoyé tel quel à l'appelant, qui répond en 200 avec success=false.
        return False, str(error)

    except GristUnavailableError as error:
        logger.error(
            f"Test de l'API Grist impossible : {error.__cause__ or error}"
        )
        return False, str(error)

    except GristKeyAccessError as error:
        return False, str(error)
