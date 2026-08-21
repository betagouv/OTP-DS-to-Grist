"""
Détection du type de demandeur et création des colonnes Grist associées.

Détermine si la démarche concerne une PersonnePhysique ou une PersonneMorale
en interrogeant l'API Démarches Simplifiées, puis retourne les colonnes
Grist correspondantes pour la table demandeurs.
"""

import os
from typing import Optional

import requests

from grist.schema import (
    create_demandeurs_pp_columns,
    create_demandeurs_pm_columns,
)
from utils.constants import DEMARCHES_API_URL

API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = DEMARCHES_API_URL


def detect_demandeur_type(demarche_number: int) -> Optional[str]:
    """
    Détecte le type de demandeur (PersonnePhysique ou PersonneMorale)
    en analysant le premier dossier de la démarche.

    Args:
        demarche_number: Numéro de la démarche

    Returns:
        "PersonnePhysique" | "PersonneMorale" | None (si aucun dossier)
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré")

    query = """
    query getFirstDossier($demarcheNumber: Int!) {
        demarche(number: $demarcheNumber) {
            id
            dossiers(first: 1) {
                nodes {
                    id
                    demandeur {
                        __typename
                    }
                }
            }
        }
    }
    """

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            API_URL,
            json={
                "query": query,
                "variables": {"demarcheNumber": int(demarche_number)},
            },
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            print(
                f"Erreur lors de la détection du type de demandeur pour la démarche {demarche_number}"
            )
            return None

        dossiers = (
            result.get("data", {})
            .get("demarche", {})
            .get("dossiers", {})
            .get("nodes", [])
        )

        if dossiers and len(dossiers) > 0:
            demandeur = dossiers[0].get("demandeur", {})
            demandeur_type = demandeur.get("__typename")

            if demandeur_type in [
                "PersonnePhysique",
                "PersonneMorale",
                "PersonneMoraleIncomplete",
            ]:
                if demandeur_type == "PersonneMoraleIncomplete":
                    return "PersonneMorale"
                return demandeur_type

        print(
            f"Aucun dossier trouvé pour la démarche {demarche_number}, type par défaut: PersonneMorale"
        )
        return "PersonneMorale"

    except Exception as e:
        print(f"Erreur lors de la détection du type: {e}")
        return "PersonneMorale"


def create_demandeurs_columns(demarche_number: int):
    """
    Crée les colonnes pour la table demandeurs selon le type détecté.

    Args:
        demarche_number: Numéro de la démarche

    Returns:
        tuple: (list colonnes, str type_detecte)
    """
    demandeur_type = detect_demandeur_type(demarche_number)

    print(f"Type de demandeur détecté: {demandeur_type}")

    if demandeur_type == "PersonnePhysique":
        return create_demandeurs_pp_columns(), demandeur_type

    return create_demandeurs_pm_columns(), demandeur_type
