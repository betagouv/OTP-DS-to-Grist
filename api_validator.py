"""
Validation des connexions aux APIs externes (Démarches Simplifiées et Grist)
Fonctions pures, sans dépendance Flask, utilisables par app.py et les scripts CLI
"""

import requests
from constants import DEMARCHES_API_URL
import logging

logger = logging.getLogger(__name__)


def test_demarches_api(api_token, demarche_number):
    """
    Teste la connexion à l'API Démarches Simplifiées
    
    Args:
        api_token: Token d'authentification DS
        demarche_number: Numéro de démarche
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

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
            json={
                "query": query,
                "variables": variables
            },
            headers=headers,
            timeout=10,
            verify=True
        )

        result = response.json()

        if response.status_code != 200:
            result.get('errors')
            error_messages = [e.get('message', 'Erreur inconnue') for e in result['errors']]
            error_text = '; '.join(error_messages)
            if any("expired" in msg.lower() for msg in error_messages):
                return False, "Token expiré"
            return False, f"Erreur de connexion à l'API: {response.status_code} - {error_text}"

        if "errors" in result:
            return False, f"Erreur API: {'; '.join(
                [
                    e.get(
                        'message',
                        'Erreur inconnue'
                    ) for e in result['errors']
                ]
            )}"

        if "data" not in result or "demarche" not in result["data"]:
            return False, "Réponse API inattendue."

        demarche = result["data"]["demarche"]

        if demarche:
            return True, f"Connexion réussie! Démarche trouvée: {demarche.get('title', 'Sans titre')}"

        return False, f"Démarche {demarche_number} non trouvée."

    except requests.exceptions.Timeout:
        return False, "Timeout: L'API met trop de temps à répondre"

    except Exception:
        logger.exception("Erreur inattendue lors du test de l'API Démarches Simplifiées")
        return False, "Erreur de connexion à l'API Démarches Simplifiées"


def test_grist_api(base_url, api_key, doc_id):
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
        headers = {"Authorization": f"Bearer {api_key}"}
        if not base_url.endswith('/api'):
            base_url = f"{base_url}/api" if base_url else "https://grist.numerique.gouv.fr/api"
        url = f"{base_url}/docs/{doc_id}"

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            try:
                doc_info = response.json()
                doc_name = doc_info.get('name', doc_id)
                return True, f"Connexion à Grist réussie! Document: {doc_name}"
            except Exception:
                return True, f"Connexion à Grist réussie! Document ID: {doc_id}"
        else:
            return False, f"Erreur de connexion à Grist: {response.status_code} - {response.text}"
    except requests.exceptions.Timeout:
        return False, "Timeout: L'API Grist met trop de temps à répondre"

    except Exception:
        logger.exception("Erreur inattendue lors du test de l'API Grist")
        return False, "Erreur de connexion à l'API Grist"


def verify_api_connections(
    ds_token,
    demarche_number,
    grist_base_url,
    grist_api_key,
    grist_doc_id
):
    """
    Teste les connexions aux deux APIs (DS et Grist)
    
    Args:
        ds_token: Token API Démarches Simplifiées
        demarche_number: Numéro de démarche DS
        grist_base_url: URL de base Grist
        grist_api_key: Clé API Grist
        grist_doc_id: ID du document Grist
    
    Returns:
        tuple: (success_global: bool, results: list[dict])
               results contient les résultats individuels de chaque test
    """
    results = []
    
    # Test Démarches Simplifiées
    ds_success, ds_message = test_demarches_api(
        ds_token,
        demarche_number
    )
    results.append({
        "type": "demarches",
        "success": ds_success,
        "message": ds_message
    })
    
    # Test Grist
    grist_success, grist_message = test_grist_api(
        grist_base_url,
        grist_api_key,
        grist_doc_id
    )

    results.append({
        "type": "grist",
        "success": grist_success,
        "message": grist_message
    })
    
    # Déterminer le succès global
    all_success = all(r["success"] for r in results)
    
    return all_success, results
