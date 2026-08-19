"""
Logique DS pour le traitement des schémas de démarches.

Fonctions pour récupérer, analyser et nettoyer les schémas de types de champs
retournés par l'API Démarches Simplifiées.
"""
import os
from datetime import datetime
from typing import Any, Dict, List

import requests

from utils.constants import DEMARCHES_API_URL

API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = DEMARCHES_API_URL


def get_problematic_descriptor_ids_from_schema(demarche_schema):
    """
    Extrait les IDs des descripteurs problématiques (HeaderSection, Explication)
    directement depuis le schéma de la démarche.

    Args:
        demarche_schema: Schéma de la démarche récupéré via get_demarche_schema

    Returns:
        set: Ensemble des IDs problématiques à filtrer
    """
    problematic_ids = set()

    def explore_descriptors(descriptors):
        for descriptor in descriptors:
            if descriptor.get("__typename") in [
                "HeaderSectionChampDescriptor",
                "ExplicationChampDescriptor",
            ] or descriptor.get("type") in ["header_section", "explication"]:
                problematic_ids.add(descriptor.get("id"))

            if (
                descriptor.get("__typename") == "RepetitionChampDescriptor"
                and "champDescriptors" in descriptor
            ):
                explore_descriptors(descriptor["champDescriptors"])

    if demarche_schema.get("activeRevision"):
        if "champDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(demarche_schema["activeRevision"]["champDescriptors"])

        if "annotationDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(
                demarche_schema["activeRevision"]["annotationDescriptors"]
            )

    return problematic_ids


def auto_clean_schema_descriptors(demarche: Dict[str, Any]) -> Dict[str, Any]:
    """
    Nettoie automatiquement les descripteurs en filtrant les champs problématiques.
    """

    def filter_descriptors(descriptors: List[Dict], context: str = "") -> List[Dict]:
        filtered = []
        problematic_count = 0

        for descriptor in descriptors:
            typename = descriptor.get("__typename", "")
            descriptor_type = descriptor.get("type", "")

            if typename in [
                "HeaderSectionChampDescriptor",
                "ExplicationChampDescriptor",
            ] or descriptor_type in ["header_section", "explication"]:
                problematic_count += 1
                continue

            if (
                typename == "RepetitionChampDescriptor"
                and "champDescriptors" in descriptor
            ):
                filtered_sub_descriptors = filter_descriptors(
                    descriptor["champDescriptors"], f"{context}_repetable"
                )
                descriptor["champDescriptors"] = filtered_sub_descriptors

            filtered.append(descriptor)

        if problematic_count > 0:
            print(f"{problematic_count} champs problématiques filtrés ({context})")

        return filtered

    cleaned_demarche = demarche.copy()
    active_revision = cleaned_demarche["activeRevision"]

    if "champDescriptors" in active_revision:
        active_revision["champDescriptors"] = filter_descriptors(
            active_revision["champDescriptors"], "champs"
        )

    if "annotationDescriptors" in active_revision:
        active_revision["annotationDescriptors"] = filter_descriptors(
            active_revision["annotationDescriptors"], "annotations"
        )

    return cleaned_demarche


# ========================================
# RÉCUPÉRATION DU SCHÉMA API DS
# ========================================


def get_demarche_schema(demarche_number):
    """
    Récupère le schéma complet d'une démarche,
    avec tous ses descripteurs de champs,
    sans dépendre des dossiers existants.

    Args:
        demarche_number: Numéro de la démarche

    Returns:
        dict: Structure complète des descripteurs de champs et d'annotations
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré.")

    query = """
    query getDemarcheSchema($demarcheNumber: Int!) {
        demarche(number: $demarcheNumber) {
            id
            number
            title
            activeRevision {
                id
                champDescriptors {
                    ...ChampDescriptorFragment
                    ... on RepetitionChampDescriptor {
                        champDescriptors {
                            ...ChampDescriptorFragment
                        }
                    }
                }
                annotationDescriptors {
                    ...ChampDescriptorFragment
                    ... on RepetitionChampDescriptor {
                        champDescriptors {
                            ...ChampDescriptorFragment
                        }
                    }
                }
            }
        }
    }

    fragment ChampDescriptorFragment on ChampDescriptor {
        __typename
        id
        type
        label
        description
        required
        ... on DropDownListChampDescriptor {
            options
            otherOption
        }
        ... on MultipleDropDownListChampDescriptor {
            options
        }
        ... on LinkedDropDownListChampDescriptor {
            options
        }
        ... on PieceJustificativeChampDescriptor {
            fileTemplate {
                filename
            }
        }
        ... on ExplicationChampDescriptor {
            collapsibleExplanationEnabled
            collapsibleExplanationText
        }
    }
    """

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        API_URL,
        json={"query": query, "variables": {"demarcheNumber": int(demarche_number)}},
        headers=headers,
    )

    response.raise_for_status()

    result = response.json()

    if "errors" in result:
        filtered_errors = []
        for error in result["errors"]:
            error_message = error.get("message", "")
            if (
                "permissions" not in error_message
                and "hidden due to permissions" not in error_message
            ):
                filtered_errors.append(error_message)

        if filtered_errors:
            raise Exception(f"GraphQL errors: {', '.join(filtered_errors)}")

    if not result.get("data") or not result["data"].get("demarche"):
        raise Exception(
            f"Aucune donnée de démarche trouvée pour le numéro {demarche_number}"
        )

    demarche = result["data"]["demarche"]

    if not demarche.get("activeRevision"):
        raise Exception(
            f"Aucune révision active trouvée pour la démarche {demarche_number}"
        )

    return demarche


# ========================================
# FONCTIONS OPTIMISÉES (Version robuste)
# ========================================


def get_demarche_schema_robust(demarche_number: int) -> Dict[str, Any]:
    """
    Version robuste et optimisée de get_demarche_schema.

    Améliorations:
    - Gestion d'erreur plus robuste
    - Filtrage automatique des champs problématiques
    - Métadonnées pour le suivi des changements
    - Performance optimisée

    Args:
        demarche_number: Numéro de la démarche

    Returns:
        dict: Schéma robuste avec métadonnées
    """
    try:
        demarche = get_demarche_schema(demarche_number)

        active_revision = demarche.get("activeRevision")
        if not active_revision:
            raise Exception(
                f"Aucune révision active pour la démarche {demarche_number}"
            )

        problematic_ids = get_problematic_descriptor_ids_from_schema(demarche)

        cleaned_schema = auto_clean_schema_descriptors(demarche)

        cleaned_schema["metadata"] = {
            "revision_id": active_revision.get("id"),
            "date_publication": active_revision.get("datePublication"),
            "retrieved_at": datetime.now().isoformat(),
            "optimized": True,
            "problematic_ids": problematic_ids,
        }

        print("Schéma récupéré:")
        print(
            f"Champs utiles: {len(cleaned_schema['activeRevision']['champDescriptors'])}"
        )
        print(
            f"Annotations: {len(cleaned_schema['activeRevision']['annotationDescriptors'])}"
        )
        print(f"Champs problématiques détectés: {len(problematic_ids)}")

        return cleaned_schema

    except Exception as e:
        raise Exception(f"Erreur lors de la récupération du schéma: {e}")


def get_demarche_schema_enhanced(demarche_number: int, prefer_robust: bool = True):
    """
    Point d'entrée principal pour obtenir le schéma avec choix de version.
    """
    if prefer_robust:
        try:
            return get_demarche_schema_robust(demarche_number)
        except Exception as e:
            print(f"Fallback vers version classique suite à: {e}")
            return get_demarche_schema(demarche_number)
    else:
        return get_demarche_schema(demarche_number)
