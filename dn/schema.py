"""
Logique pure DS pour le traitement des schémas de démarches.

Fonctions pures (aucune dépendance API) pour analyser et nettoyer
les schémas de types de champs retournés par l'API Démarches Simplifiées.
"""
from typing import Any, Dict, List


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
