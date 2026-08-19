"""
Logique DS pour le traitement des schémas de démarches.

Fonctions pour récupérer, analyser et nettoyer les schémas de types de champs
retournés par l'API Démarches Simplifiées.
"""
import os
from datetime import datetime
from typing import Any, Dict, List

import requests

from common.formatter import label_to_column_id
from utils.constants import DEMARCHES_API_URL
from utils.log import log

API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = DEMARCHES_API_URL


def create_columns_from_schema(demarche_schema, demarche_number=None):
    """
    Crée les définitions de colonnes à partir du schéma de la démarche,
    en filtrant les champs problématiques (HeaderSection, Explication)

    CORRIGÉ :
    - Les PieceJustificativeChamp sont traités AVANT le filtrage
    - Gestion des doublons de noms de colonnes avec suffixes numériques
    - Tables séparées par bloc répétable
    - FORMAT FIELDS pour les colonnes dynamiques

    FONCTION EXISTANTE - GARDÉE POUR COMPATIBILITÉ

    Args:
        demarche_schema: Schéma de la démarche récupéré via get_demarche_schema

    Returns:
        tuple: (dict définitions des colonnes, set IDs problématiques)
    """
    #  NOUVEAU : Logging optionnel
    if demarche_number:
        log(f"Création des colonnes pour la démarche {demarche_number}")

    #  RÉCUPÉRER LES IDs DEPUIS LES MÉTADONNÉES SI DISPONIBLES
    if (
        "metadata" in demarche_schema
        and "problematic_ids" in demarche_schema["metadata"]
    ):
        problematic_ids = demarche_schema["metadata"]["problematic_ids"]
        log(
            f"Identificateurs de {len(problematic_ids)} descripteurs problématiques (depuis métadonnées)"
        )
    else:
        # Fallback : essayer de les extraire du schéma (déjà nettoyé = 0)
        problematic_ids = get_problematic_descriptor_ids_from_schema(demarche_schema)
        log(
            f"Identificateurs de {len(problematic_ids)} descripteurs problématiques à filtrer"
        )

    # Fonction pour déterminer le type de colonne Grist
    def determine_column_type(champ_type, typename=None):
        """Détermine le type de colonne Grist basé sur le type de champ DS"""
        type_mapping = {
            "text": "Text",
            "textarea": "Text",
            "email": "Text",
            "phone": "Text",
            "number": "Numeric",
            "integer_number": "Int",
            "decimal_number": "Numeric",
            "date": "Date",
            "datetime": "DateTime",
            "yes_no": "Bool",
            "checkbox": "Bool",
            "drop_down_list": "Text",
            "multiple_drop_down_list": "Text",
            "linked_drop_down_list": "Text",
            "piece_justificative": "Text",
            "iban": "Text",
            "siret": "Text",
            "rna": "Text",
            "titre_identite": "Text",
            "address": "Text",
            "commune": "Text",
            "departement": "Text",
            "region": "Text",
            "pays": "Text",
            "carte": "Text",
            "repetition": "Text",
        }
        return type_mapping.get(champ_type, "Text")

    # Colonnes fixes pour la table des dossiers
    dossier_columns = [
        {"id": "dossier_id", "type": "Text"},
        {"id": "dossier_number", "type": "Int"},
        {"id": "state", "type": "Text"},
        {"id": "date_depot", "type": "DateTime"},
        {"id": "date_derniere_modification", "type": "DateTime"},
        {"id": "date_expiration", "type": "DateTime"},
        {"id": "date_traitement", "type": "DateTime"},
        {"id": "date_suppression", "type": "DateTime"},
        {"id": "date_derniere_correction_en_attente", "type": "DateTime"},
        {"id": "date_derniere_modification_champs", "type": "DateTime"},
        {"id": "date_derniere_modification_annotations", "type": "DateTime"},
        {"id": "motivation", "type": "Text"},
        {"id": "label_names", "type": "Text"},
        {"id": "labels_json", "type": "Text"},
        {"id": "suivi_par", "type": "Text"},
        {"id": "date_accuse_lecture", "type": "DateTime"},
        {"id": "correction_instructeur", "type": "Text"},
    ]

    # Colonnes de base pour la table des champs
    champ_columns = [
        {"id": "dossier_number", "type": "Int"},
        {"id": "champ_id", "type": "Text"},
    ]

    # Colonnes de base pour la table des annotations
    annotation_columns = [
        {"id": "dossier_number", "type": "Int"},
    ]

    # Variables pour suivre la présence de blocs répétables et champs carto
    has_repetable_blocks = False
    repetable_blocks = {}  # Dict au lieu d'une seule liste
    has_carto_fields = False
    descriptor_to_column_id = {}  # {descriptor_id: colonne_id_suffixée stable}

    # Traiter les descripteurs de champs
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get(
        "champDescriptors"
    ):
        for descriptor in demarche_schema["activeRevision"]["champDescriptors"]:
            champ_type = descriptor.get("type")
            champ_label = descriptor.get("label")

            # CORRECTION MAJEURE : Traiter les PieceJustificativeChamp AVANT le filtrage
            if descriptor.get("__typename") == "PieceJustificativeChampDescriptor":
                normalized_label = label_to_column_id(champ_label)

                # Détecter si c'est un champ RIB
                if "rib" in champ_label.lower() or "iban" in champ_label.lower():
                    rib_suffixes = ["titulaire", "iban", "bic", "nom_de_la_banque"]
                    for suffix in rib_suffixes:
                        rib_col_id = f"{normalized_label}_{suffix}"
                        if not any(col["id"] == rib_col_id for col in champ_columns):
                            # ✅ FORMAT AVEC FIELDS
                            champ_columns.append(
                                {
                                    "id": rib_col_id,
                                    "fields": {
                                        "type": "Text",
                                        "label": f"{champ_label} - {suffix}",
                                    },
                                }
                            )

                # Ajouter aussi la colonne principale pour le nom du fichier
                #  GESTION DES DOUBLONS
                base_label = normalized_label
                counter = 1
                while any(col["id"] == normalized_label for col in champ_columns):
                    normalized_label = f"{base_label}_{counter}"
                    counter += 1

                # ✅ FORMAT AVEC FIELDS
                champ_columns.append(
                    {
                        "id": normalized_label,
                        "fields": {"type": "Text", "label": champ_label},
                    }
                )

            # Maintenant filtrer les types problématiques
            if (
                descriptor["__typename"]
                in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"]
                or descriptor.get("type") in ["header_section", "explication"]
                or descriptor.get("id") in problematic_ids
            ):
                continue

            # Traitement spécial pour les blocs répétables
            if (
                descriptor.get("__typename") == "RepetitionChampDescriptor"
                and "champDescriptors" in descriptor
            ):
                has_repetable_blocks = True

                #  NOUVEAU : Créer une entrée par bloc
                block_label = descriptor.get("label")
                normalized_block_label = label_to_column_id(block_label)

                # Colonnes de base pour ce bloc
                block_columns = [
                    {"id": "dossier_number", "type": "Int"},
                    {"id": "block_id", "type": "Text"},
                    {"id": "block_row_index", "type": "Int"},
                    {"id": "block_row_id", "type": "Text"},
                ]

                block_has_carto = False  # Pour suivre si CE bloc a des champs carto

                # Traiter les sous-champs du bloc répétable
                for inner_descriptor in descriptor["champDescriptors"]:
                    inner_type = inner_descriptor.get("type")
                    inner_label = inner_descriptor.get("label")

                    # Détecter les champs cartographiques
                    if inner_type == "carte":
                        has_carto_fields = True
                        block_has_carto = True

                    # Ajouter le champ normalisé à la table des blocs répétables
                    normalized_label = label_to_column_id(inner_label)
                    column_type = determine_column_type(
                        inner_type, inner_descriptor.get("__typename")
                    )

                    #  GESTION DES DOUBLONS pour ce bloc (utiliser block_columns)
                    base_label = normalized_label
                    counter = 1
                    while any(col["id"] == normalized_label for col in block_columns):
                        normalized_label = f"{base_label}_{counter}"
                        counter += 1

                    block_columns.append({"id": normalized_label, "type": column_type})

                # Ajouter les colonnes géographiques si nécessaire pour CE bloc
                if block_has_carto:
                    geo_columns = [
                        {"id": "geo_id", "type": "Text"},
                        {"id": "geo_source", "type": "Text"},
                        {"id": "geo_description", "type": "Text"},
                        {"id": "geo_type", "type": "Text"},
                        {"id": "geo_coordinates", "type": "Text"},
                        {"id": "geo_wkt", "type": "Text"},
                        {"id": "geo_commune", "type": "Text"},
                        {"id": "geo_numero", "type": "Text"},
                        {"id": "geo_section", "type": "Text"},
                        {"id": "geo_prefixe", "type": "Text"},
                        {"id": "geo_surface", "type": "Numeric"},
                    ]

                    for geo_col in geo_columns:
                        if not any(col["id"] == geo_col["id"] for col in block_columns):
                            block_columns.append(geo_col)

                #  STOCKER dans le dict avec le label normalisé comme clé
                repetable_blocks[normalized_block_label] = {
                    "original_label": block_label,
                    "columns": block_columns,
                }

            # Détecter les champs cartographiques au niveau principal
            elif champ_type == "carte":
                has_carto_fields = True

            # Ajouter le champ normalisé à la table des champs
            # MAIS PAS pour les PieceJustificativeChamp car déjà traités ci-dessus
            # NI pour les RepetitionChamp (données stockées dans leur table dédiée)
            if descriptor.get("__typename") not in [
                "PieceJustificativeChampDescriptor",
                "RepetitionChampDescriptor",
            ]:
                normalized_label = label_to_column_id(champ_label)
                column_type = determine_column_type(
                    champ_type, descriptor.get("__typename")
                )

                #  GESTION DES DOUBLONS
                base_label = normalized_label
                counter = 1
                while any(col["id"] == normalized_label for col in champ_columns):
                    normalized_label = f"{base_label}_{counter}"
                    counter += 1

                # ✅ FORMAT AVEC FIELDS
                descriptor_to_column_id[descriptor.get("id")] = normalized_label
                champ_columns.append(
                    {
                        "id": normalized_label,
                        "fields": {"type": column_type, "label": champ_label},
                    }
                )

            # ✨ Colonnes Commune
            if descriptor.get("__typename") == "CommuneChampDescriptor":
                normalized_label = label_to_column_id(champ_label)
                commune_suffixes = [
                    "nom",
                    "code_postal",
                    "departement",
                    "code_insee",
                    "code_departement",
                ]
                for suffix in commune_suffixes:
                    commune_col_id = f"{normalized_label}_{suffix}"

                    #  GESTION DES DOUBLONS pour colonnes communes
                    base_col = commune_col_id
                    counter = 1
                    while any(col["id"] == commune_col_id for col in champ_columns):
                        commune_col_id = f"{base_col}_{counter}"
                        counter += 1

                    # ✅ FORMAT AVEC FIELDS
                    champ_columns.append(
                        {
                            "id": commune_col_id,
                            "fields": {
                                "type": "Text",
                                "label": f"{champ_label} - {suffix}",
                            },
                        }
                    )

            # ✨ Colonnes Pays (nom et code)
            if descriptor.get("__typename") == "PaysChampDescriptor":
                normalized_label = label_to_column_id(champ_label)
                pays_suffixes = ["nom", "code"]
                for suffix in pays_suffixes:
                    pays_col_id = f"{normalized_label}_{suffix}"

                    # Gestion des doublons
                    base_col = pays_col_id
                    counter = 1
                    while any(col["id"] == pays_col_id for col in champ_columns):
                        pays_col_id = f"{base_col}_{counter}"
                        counter += 1

                    # ✅ FORMAT AVEC FIELDS
                    champ_columns.append(
                        {
                            "id": pays_col_id,
                            "fields": {
                                "type": "Text",
                                "label": f"{champ_label} - {suffix}",
                            },
                        }
                    )

            # ✨ Colonnes Région (nom et code)
            if descriptor.get("__typename") == "RegionChampDescriptor":
                normalized_label = label_to_column_id(champ_label)
                region_suffixes = ["nom", "code"]
                for suffix in region_suffixes:
                    region_col_id = f"{normalized_label}_{suffix}"

                    # Gestion des doublons
                    base_col = region_col_id
                    counter = 1
                    while any(col["id"] == region_col_id for col in champ_columns):
                        region_col_id = f"{base_col}_{counter}"
                        counter += 1

                    # ✅ FORMAT AVEC FIELDS
                    champ_columns.append(
                        {
                            "id": region_col_id,
                            "fields": {
                                "type": "Text",
                                "label": f"{champ_label} - {suffix}",
                            },
                        }
                    )

            # ✨ Colonnes Département (nom et code)
            if descriptor.get("__typename") == "DepartementChampDescriptor":
                normalized_label = label_to_column_id(champ_label)
                dept_suffixes = ["nom", "code"]
                for suffix in dept_suffixes:
                    dept_col_id = f"{normalized_label}_{suffix}"

                    # Gestion des doublons
                    base_col = dept_col_id
                    counter = 1
                    while any(col["id"] == dept_col_id for col in champ_columns):
                        dept_col_id = f"{base_col}_{counter}"
                        counter += 1

                    # ✅ FORMAT AVEC FIELDS
                    champ_columns.append(
                        {
                            "id": dept_col_id,
                            "fields": {
                                "type": "Text",
                                "label": f"{champ_label} - {suffix}",
                            },
                        }
                    )

    # Traiter les descripteurs d'annotations
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get(
        "annotationDescriptors"
    ):
        for descriptor in demarche_schema["activeRevision"]["annotationDescriptors"]:
            # Ignorer les types problématiques
            if (
                descriptor["__typename"]
                in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"]
                or descriptor.get("type") in ["header_section", "explication"]
                or descriptor.get("id") in problematic_ids
            ):
                continue

            champ_type = descriptor.get("type")
            champ_label = descriptor.get("label")

            # ✅ NOUVEAU : Traitement des blocs répétables dans les annotations
            if (
                descriptor.get("__typename") == "RepetitionChampDescriptor"
                and "champDescriptors" in descriptor
            ):
                has_repetable_blocks = True

                # Préfixe pour les blocs d'annotations
                block_label = f"annotation_{descriptor.get('label')}"
                normalized_block_label = label_to_column_id(block_label)

                # Colonnes de base pour ce bloc
                block_columns = [
                    {"id": "dossier_number", "type": "Int"},
                    {"id": "block_id", "type": "Text"},
                    {"id": "block_row_index", "type": "Int"},
                    {"id": "block_row_id", "type": "Text"},
                ]

                block_has_carto = False

                # Traiter les sous-champs du bloc répétable
                for inner_descriptor in descriptor["champDescriptors"]:
                    inner_type = inner_descriptor.get("type")
                    inner_label = inner_descriptor.get("label")

                    # Détecter les champs cartographiques
                    if inner_type == "carte":
                        has_carto_fields = True
                        block_has_carto = True

                    # Ajouter le champ normalisé
                    normalized_label = label_to_column_id(inner_label)
                    column_type = determine_column_type(
                        inner_type, inner_descriptor.get("__typename")
                    )

                    # Gestion des doublons
                    base_label = normalized_label
                    counter = 1
                    while any(col["id"] == normalized_label for col in block_columns):
                        normalized_label = f"{base_label}_{counter}"
                        counter += 1

                    block_columns.append({"id": normalized_label, "type": column_type})

                # Ajouter les colonnes géographiques si nécessaire
                if block_has_carto:
                    geo_columns = [
                        {"id": "geo_id", "type": "Text"},
                        {"id": "geo_source", "type": "Text"},
                        {"id": "geo_description", "type": "Text"},
                        {"id": "geo_type", "type": "Text"},
                        {"id": "geo_coordinates", "type": "Text"},
                        {"id": "geo_wkt", "type": "Text"},
                        {"id": "geo_commune", "type": "Text"},
                        {"id": "geo_numero", "type": "Text"},
                        {"id": "geo_section", "type": "Text"},
                        {"id": "geo_prefixe", "type": "Text"},
                        {"id": "geo_surface", "type": "Numeric"},
                    ]

                    for geo_col in geo_columns:
                        if not any(col["id"] == geo_col["id"] for col in block_columns):
                            block_columns.append(geo_col)

                # Stocker dans le dict avec le label normalisé comme clé
                repetable_blocks[normalized_block_label] = {
                    "original_label": block_label,
                    "columns": block_columns,
                }
                continue  # Passer au descripteur suivant

            # Pour les annotations simples (non répétables)
            # Pour les annotations, enlever le préfixe "annotation_" pour le nom de colonne
            if champ_label.startswith("annotation_"):
                annotation_label = label_to_column_id(
                    champ_label[11:]
                )  # enlever "annotation_"
                display_label = champ_label[11:]  # Label sans préfixe pour affichage
            else:
                annotation_label = label_to_column_id(champ_label)
                display_label = champ_label

            column_type = determine_column_type(
                champ_type, descriptor.get("__typename")
            )

            #  GESTION DES DOUBLONS pour annotations
            base_label = annotation_label
            counter = 1
            while any(col["id"] == annotation_label for col in annotation_columns):
                annotation_label = f"{base_label}_{counter}"
                counter += 1

            # ✅ FORMAT AVEC FIELDS
            descriptor_to_column_id[descriptor.get("id")] = annotation_label
            annotation_columns.append(
                {
                    "id": annotation_label,
                    "fields": {"type": column_type, "label": display_label},
                }
            )

    # Préparer le résultat
    result = {
        "dossier": dossier_columns,
        "champs": champ_columns,
        "annotations": annotation_columns,
        "has_repetable_blocks": has_repetable_blocks,
        "has_carto_fields": has_carto_fields,
        "descriptor_to_column_id": descriptor_to_column_id,
    }

    if has_repetable_blocks:
        result["repetable_blocks"] = (
            repetable_blocks  # NOUVEAU : dict au lieu d'une liste
        )

    return result, problematic_ids


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
