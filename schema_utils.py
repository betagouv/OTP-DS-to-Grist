"""
Module d'utilitaires pour récupérer et traiter le schéma complet d'une démarche
à partir de l'API Démarches Simplifiées, pour la création correcte de tables Grist.

VERSION AMÉLIORÉE - Compatible avec le code existant
Ajoute des fonctions optimisées tout en gardant les fonctions existantes
CORRECTION : Gestion des doublons de noms de colonnes
NOUVEAU : Tables séparées par bloc répétable
CORRECTION : Format "fields" pour les colonnes dynamiques
"""

# Importer les configurations nécessaires
import os
from typing import Optional

import requests

from utils.constants import DEMARCHES_API_URL
from grist.schema import (
    create_demandeurs_pp_columns,
    create_demandeurs_pm_columns,
)

API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = DEMARCHES_API_URL

# ========================================
# DÉTECTION DU TYPE DE DEMANDEUR
# ========================================


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

    # Requête pour récupérer juste le premier dossier
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
                f"⚠️  Erreur lors de la détection du type de demandeur pour la démarche {demarche_number}"
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
                # PersonneMoraleIncomplete est traité comme PersonneMorale
                if demandeur_type == "PersonneMoraleIncomplete":
                    return "PersonneMorale"
                return demandeur_type

        # Aucun dossier trouvé
        print(
            f"ℹ️  Aucun dossier trouvé pour la démarche {demarche_number}, type par défaut: PersonneMorale"
        )
        return "PersonneMorale"  # Par défaut si aucun dossier

    except Exception as e:
        print(f"❌ Erreur lors de la détection du type: {e}")
        return "PersonneMorale"  # Par défaut en cas d'erreur


# ========================================
# CRÉATION DES COLONNES DEMANDEURS
# ========================================


def create_demandeurs_columns(demarche_number: int):
    """
    Crée les colonnes pour la table demandeurs selon le type détecté

    Args:
        demarche_number: Numéro de la démarche

    Returns:
        tuple: (list colonnes, str type_detecte)
    """
    demandeur_type = detect_demandeur_type(demarche_number)

    print(f"Type de demandeur détecté: {demandeur_type}")

    if demandeur_type == "PersonnePhysique":
        return create_demandeurs_pp_columns(), demandeur_type
    # PersonneMorale ou None (défaut)
    return create_demandeurs_pm_columns(), demandeur_type

