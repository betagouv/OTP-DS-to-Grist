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
from typing import Any, Dict, List, Optional

import requests

from dn.client import get_demarche_descriptors, get_pj_ocr_columns
from dn.extract import pj_ocr_sub_label
from grist.client import SYNC_METADATA_TABLE_ID, GristClient
from grist.utils import normalize_column_name
from utils.constants import DEMARCHES_API_URL
from utils.log import log, log_error, log_verbose

API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = DEMARCHES_API_URL

# Type de colonne Grist pour chaque type de sous-colonne OCR DN. Mêmes types
# que ceux dont dn.extract sait lire la valeur (PJ_OCR_VALUE_KEYS, vérifié
# par les tests).
PJ_OCR_GRIST_TYPES = {
    "TextColumn": "Text",
    "EnumColumn": "Text",
    "DateColumn": "Date",
    "IntegerColumn": "Int",
    "DecimalColumn": "Numeric",
}

# Repli quand aucun dossier de l'échantillon ne contient la PJ : seules les
# sous-colonnes RIB sont créées, si le libellé évoque un RIB. Les autres
# natures le seront à la première synchro qui trouve un dossier.
PJ_OCR_RIB_FALLBACK = [
    ("Titulaire", "TextColumn"),
    ("IBAN", "TextColumn"),
    ("BIC", "TextColumn"),
    ("Nom de la Banque", "TextColumn"),
]

# Colonnes de la table Sync_metadata, partagée par toutes les démarches
SYNC_METADATA_COLUMNS = [
    {"id": "demarche_number", "type": "Int"},
    {"id": "last_sync_at", "type": "Text"},
    {"id": "updated_since_cursor", "type": "Text"},
    {"id": "deleted_since_cursor", "type": "Text"},
    {"id": "deleted_after_cursor", "type": "Text"},
    {"id": "last_sync_status", "type": "Text"},
    {"id": "last_sync_duration", "type": "Numeric"},
    {
        "id": "force_full_sync",
        "type": "Bool",
        "fields": {"type": "Bool", "isFormula": False, "formula": ""},
    },
    {"id": "filters_hash", "type": "Text"},
]

# Colonnes posées à la création des tables champs et annotations : les
# colonnes du schéma, sans type obligatoire, sont ajoutées ensuite.
CHAMPS_CREATION_COLUMNS = [
    {"id": "dossier_number", "type": "Int"},
    {"id": "champ_id", "type": "Text"},
]
ANNOTATIONS_CREATION_COLUMNS = [{"id": "dossier_number", "type": "Int"}]

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


def create_demandeurs_pp_columns():
    """
    Crée les colonnes pour la table demandeurs (PersonnePhysique)

    Returns:
        list: Définitions des colonnes Grist
    """
    return [
        {"id": "dossier_number", "type": "Int"},
        {"id": "type", "type": "Text"},
        {"id": "civilite", "type": "Text"},
        {"id": "nom", "type": "Text"},
        {"id": "prenom", "type": "Text"},
        {"id": "email", "type": "Text"},
        {"id": "usager_email", "type": "Text"},
        {"id": "prenom_mandataire", "type": "Text"},
        {"id": "nom_mandataire", "type": "Text"},
        {"id": "depose_par_un_tiers", "type": "Bool"},
        {"id": "connection_usager", "type": "Text"},
    ]


def create_demandeurs_pm_columns():
    """
    Crée les colonnes pour la table demandeurs (PersonneMorale)
    avec tous les champs enrichis SIRENE

    Returns:
        list: Définitions des colonnes Grist
    """
    return [
        # Métadonnées
        {"id": "dossier_number", "type": "Int"},
        {"id": "type", "type": "Text"},
        {"id": "usager_email", "type": "Text"},
        # Identifiants de base
        {"id": "siret", "type": "Text"},
        {"id": "siren", "type": "Text"},
        {"id": "siege_social", "type": "Bool"},
        {"id": "naf", "type": "Text"},
        {"id": "libelle_naf", "type": "Text"},
        # Entreprise (champs enrichis SIRENE)
        {"id": "raison_sociale", "type": "Text"},
        {"id": "nom_commercial", "type": "Text"},
        {"id": "forme_juridique", "type": "Text"},
        {"id": "forme_juridique_code", "type": "Text"},
        {"id": "capital_social", "type": "Text"},
        {"id": "code_effectif_entreprise", "type": "Text"},
        {"id": "numero_tva_intracommunautaire", "type": "Text"},
        {"id": "date_creation", "type": "Date"},
        {"id": "etat_administratif", "type": "Text"},
        # Association (si applicable)
        {"id": "rna", "type": "Text"},
        {"id": "titre_association", "type": "Text"},
        {"id": "objet_association", "type": "Text"},
        {"id": "date_creation_association", "type": "Date"},
        {"id": "date_declaration_association", "type": "Date"},
        {"id": "date_publication_association", "type": "Date"},
        # Adresse enrichie
        {"id": "adresse_label", "type": "Text"},
        {"id": "adresse_type", "type": "Text"},
        {"id": "street_address", "type": "Text"},
        {"id": "street_number", "type": "Text"},
        {"id": "street_name", "type": "Text"},
        {"id": "code_postal", "type": "Text"},
        {"id": "ville", "type": "Text"},
        {"id": "code_insee_ville", "type": "Text"},
        {"id": "departement", "type": "Text"},
        {"id": "code_departement", "type": "Text"},
        {"id": "region", "type": "Text"},
        {"id": "code_region", "type": "Text"},
        {"id": "connection_usager", "type": "Text"},
    ]


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


def create_instructeurs_columns():
    """
    Crée les colonnes pour la table instructeurs (niveau démarche)
    1 ligne = 1 instructeur dans 1 groupe

    Returns:
        list: Définitions des colonnes Grist
    """
    return [
        # Groupe instructeur
        {"id": "groupe_instructeur_id", "type": "Text"},
        {"id": "groupe_instructeur_number", "type": "Int"},
        {"id": "groupe_instructeur_label", "type": "Text"},
        # Instructeur
        {"id": "instructeur_id", "type": "Text"},
        {"id": "instructeur_email", "type": "Text"},
    ]


def create_avis_columns():
    return [
        {"id": "dossier_number", "type": "Int"},
        {"id": "avis_id", "type": "Text"},
        {"id": "instructeur_email", "type": "Text"},
        {"id": "expert_email", "type": "Text"},
        {"id": "date_question", "type": "Text"},
        {"id": "date_reponse", "type": "Text"},
        {"id": "question", "type": "Text"},
        {"id": "reponse", "type": "Text"},
    ]


# ========================================
# FONCTIONS EXISTANTES - CORRIGÉES
# ========================================


def get_demarche_schema(demarche_number: int | str) -> dict[str, Any]:
    """
    Schéma d'une démarche, sans dépendre des dossiers existants : ses
    descripteurs de champs et d'annotations, sans les champs qui ne portent
    pas de données (titres de section, explications). Les ids de ces champs
    retirés sont fournis dans `metadata["problematic_ids"]`.
    """
    demarche = get_demarche_descriptors(demarche_number)

    # Les sous-colonnes OCR des PJ ne sont pas exposées par les descripteurs :
    # elles sont lues sur des dossiers pour create_columns_from_schema
    if _has_piece_justificative(demarche["activeRevision"]):
        demarche["pj_ocr_columns"] = get_pj_ocr_columns(demarche_number)

    # Ids relevés avant le nettoyage, qui retire ces champs du schéma
    problematic_ids = get_problematic_descriptor_ids_from_schema(demarche)
    schema = auto_clean_schema_descriptors(demarche)
    schema["metadata"] = {"problematic_ids": problematic_ids}

    active_revision = schema["activeRevision"]
    log(
        f"Schéma récupéré (révision {active_revision.get('id')}) : "
        f"{len(active_revision.get('champDescriptors', []))} champs, "
        f"{len(active_revision.get('annotationDescriptors', []))} annotations, "
        f"{len(problematic_ids)} champs sans données retirés"
    )

    return schema


def get_problematic_descriptor_ids_from_schema(demarche_schema):
    """
    Extrait les IDs des descripteurs problématiques (HeaderSection, Explication)
    directement depuis le schéma de la démarche.

     CORRIGÉ : "piece_justificative" retiré de la liste

    FONCTION EXISTANTE - GARDÉE POUR COMPATIBILITÉ

    Args:
        demarche_schema: Schéma de la démarche récupéré via get_demarche_schema

    Returns:
        set: Ensemble des IDs problématiques à filtrer
    """
    problematic_ids = set()

    # Fonction récursive pour explorer les descripteurs
    def explore_descriptors(descriptors):
        for descriptor in descriptors:
            #  CORRECTION : "piece_justificative" RETIRÉ
            if descriptor.get("__typename") in [
                "HeaderSectionChampDescriptor",
                "ExplicationChampDescriptor",
            ] or descriptor.get("type") in ["header_section", "explication"]:
                problematic_ids.add(descriptor.get("id"))

            # Explorer les descripteurs dans les blocs répétables
            if (
                descriptor.get("__typename") == "RepetitionChampDescriptor"
                and "champDescriptors" in descriptor
            ):
                explore_descriptors(descriptor["champDescriptors"])

    # Explorer les descripteurs de champs et d'annotations
    if demarche_schema.get("activeRevision"):
        if "champDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(demarche_schema["activeRevision"]["champDescriptors"])

        if "annotationDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(
                demarche_schema["activeRevision"]["annotationDescriptors"]
            )

    return problematic_ids


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
    from utils.log import log

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
    pj_ocr_columns = demarche_schema.get("pj_ocr_columns") or {}

    # Traiter les descripteurs de champs
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get(
        "champDescriptors"
    ):
        for descriptor in demarche_schema["activeRevision"]["champDescriptors"]:
            champ_type = descriptor.get("type")
            champ_label = descriptor.get("label")

            # CORRECTION MAJEURE : Traiter les PieceJustificativeChamp AVANT le filtrage
            if descriptor.get("__typename") == "PieceJustificativeChampDescriptor":
                normalized_label = normalize_column_name(champ_label)

                for column_id, column_type, label in _pj_ocr_columns(
                    descriptor, pj_ocr_columns
                ):
                    if not any(col["id"] == column_id for col in champ_columns):
                        champ_columns.append(
                            {
                                "id": column_id,
                                "fields": {"type": column_type, "label": label},
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
                normalized_block_label = normalize_column_name(block_label)

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
                    normalized_label = normalize_column_name(inner_label)
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

                    # Sous-colonnes OCR d'une pièce justificative du bloc
                    if (
                        inner_descriptor.get("__typename")
                        == "PieceJustificativeChampDescriptor"
                    ):
                        for column_id, ocr_type, _ in _pj_ocr_columns(
                            inner_descriptor, pj_ocr_columns
                        ):
                            if not any(col["id"] == column_id for col in block_columns):
                                block_columns.append(
                                    {"id": column_id, "type": ocr_type}
                                )

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
                normalized_label = normalize_column_name(champ_label)
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
                normalized_label = normalize_column_name(champ_label)
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
                normalized_label = normalize_column_name(champ_label)
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
                normalized_label = normalize_column_name(champ_label)
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
                normalized_label = normalize_column_name(champ_label)
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
                normalized_block_label = normalize_column_name(block_label)

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
                    normalized_label = normalize_column_name(inner_label)
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
                annotation_label = normalize_column_name(
                    champ_label[11:]
                )  # enlever "annotation_"
                display_label = champ_label[11:]  # Label sans préfixe pour affichage
            else:
                annotation_label = normalize_column_name(champ_label)
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


def ensure_sync_table_structure(
    client: GristClient, demarche_number: int | str, column_types: dict[str, Any]
) -> dict[str, Any]:
    """
    Tables dans lesquelles écrit la synchronisation d'une démarche : chacune
    est créée si elle manque, sinon complétée des colonnes ajoutées au
    schéma, sans toucher aux données. Renvoie l'id de chaque table.

    La table des annotations n'est créée que si la démarche en a, la table
    des avis seulement au premier avis (`create_avis_table`).
    """
    log(
        f"Mise à jour des tables Grist pour la démarche {demarche_number} d'après le schéma..."
    )
    existing_ids = _get_existing_table_ids(client)
    prefix = f"Demarche_{demarche_number}"

    result: dict[str, Any] = {
        "dossiers": _ensure_table_structure(
            client,
            existing_ids,
            f"{prefix}_dossiers",
            column_types["dossier"],
            demarche_number=demarche_number,
        ),
        "champs": _ensure_table_structure(
            client,
            existing_ids,
            f"{prefix}_champs",
            column_types["champs"],
            demarche_number=demarche_number,
            creation_columns=CHAMPS_CREATION_COLUMNS,
        ),
    }

    annotations_table_id = f"{prefix}_annotations"
    # dossier_number est toujours présente : au-delà, la démarche a des annotations
    if (
        annotations_table_id.lower() in existing_ids
        or len(column_types["annotations"]) > 1
    ):
        result["annotations"] = _ensure_table_structure(
            client,
            existing_ids,
            annotations_table_id,
            column_types["annotations"],
            demarche_number=demarche_number,
            creation_columns=ANNOTATIONS_CREATION_COLUMNS,
        )
    else:
        log(f"Aucune annotation - table {annotations_table_id} non créée")

    if column_types.get("has_repetable_blocks", False):
        result["repetable_blocks"] = {
            block_key: _ensure_table_structure(
                client,
                existing_ids,
                f"{prefix}_repetable_{block_key}",
                block_info["columns"],
                demarche_number=demarche_number,
            )
            for block_key, block_info in column_types.get(
                "repetable_blocks", {}
            ).items()
        }

    demandeurs_columns, demandeur_type = create_demandeurs_columns(demarche_number)
    log(f"Type de demandeur: {demandeur_type} - {len(demandeurs_columns)} colonnes")
    result["demandeurs"] = _ensure_table_structure(
        client,
        existing_ids,
        f"{prefix}_demandeurs",
        demandeurs_columns,
        demarche_number=demarche_number,
    )
    result["demandeur_type"] = demandeur_type

    result["instructeurs"] = _ensure_table_structure(
        client,
        existing_ids,
        f"{prefix}_instructeurs",
        create_instructeurs_columns(),
        demarche_number=demarche_number,
    )

    avis_table_id = existing_ids.get(_get_avis_table_id(demarche_number).lower())
    if avis_table_id:
        _add_missing_columns(client, avis_table_id, create_avis_columns())
    else:
        log("Table avis non créée (sera créée au premier avis détecté)")
    result["avis"] = avis_table_id

    result["sync_metadata"] = _ensure_table_structure(
        client, existing_ids, SYNC_METADATA_TABLE_ID, SYNC_METADATA_COLUMNS
    )

    log("Mise à jour des tables terminée avec succès")

    return result


def create_avis_table(client: GristClient, demarche_number: int | str) -> str:
    """Crée la table des avis de la démarche, au premier avis rencontré."""
    result = client.create_demarche_table(
        demarche_number, _get_avis_table_id(demarche_number), create_avis_columns()
    )

    return result["tables"][0]["id"]


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

            # Filtrer les types problématiques (SANS piece_justificative)
            if typename in [
                "HeaderSectionChampDescriptor",
                "ExplicationChampDescriptor",
            ] or descriptor_type in ["header_section", "explication"]:
                problematic_count += 1
                continue

            # Traitement spécial pour les blocs répétables
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
            log_verbose(f"{problematic_count} champs sans données filtrés ({context})")

        return filtered

    # Nettoyer la démarche
    cleaned_demarche = demarche.copy()
    active_revision = cleaned_demarche["activeRevision"]

    # Filtrer les descripteurs de champs
    if "champDescriptors" in active_revision:
        active_revision["champDescriptors"] = filter_descriptors(
            active_revision["champDescriptors"], "champs"
        )

    # Filtrer les descripteurs d'annotations
    if "annotationDescriptors" in active_revision:
        active_revision["annotationDescriptors"] = filter_descriptors(
            active_revision["annotationDescriptors"], "annotations"
        )

    return cleaned_demarche


# --- Helpers privés (module) ---


def _has_piece_justificative(active_revision: dict[str, Any]) -> bool:
    """Indique si la révision contient au moins une pièce justificative, blocs inclus."""
    descriptors = active_revision.get("champDescriptors") or []
    inner_descriptors = [
        inner
        for descriptor in descriptors
        for inner in descriptor.get("champDescriptors") or []
    ]
    return any(
        descriptor.get("__typename") == "PieceJustificativeChampDescriptor"
        for descriptor in descriptors + inner_descriptors
    )


def _pj_ocr_columns(
    descriptor: dict[str, Any], pj_ocr_columns: dict[str, list[tuple[str, str]]]
) -> list[tuple[str, str, str]]:
    """
    Sous-colonnes OCR d'une pièce justificative : (id de colonne, type Grist,
    libellé affiché).

    Les libellés et types viennent de DN (get_pj_ocr_columns). L'id est le nom
    normalisé de "<libellé du champ> <sous-libellé>", comme dans
    dn.extract.iter_pj_ocr_columns. Les types que l'extraction ne sait pas
    lire sont ignorés.
    """
    champ_label = descriptor.get("label") or ""
    dn_columns = pj_ocr_columns.get(descriptor.get("id"))
    if dn_columns is None:
        label = champ_label.lower()
        is_rib = "rib" in label or "iban" in label
        sub_labels = PJ_OCR_RIB_FALLBACK if is_rib else []
    else:
        sub_labels = [
            (pj_ocr_sub_label(dn_label), dn_type) for dn_label, dn_type in dn_columns
        ]

    return [
        (
            normalize_column_name(f"{champ_label} {sub_label}"),
            PJ_OCR_GRIST_TYPES[dn_type],
            f"{champ_label} – {sub_label}",
        )
        for sub_label, dn_type in sub_labels
        if dn_type in PJ_OCR_GRIST_TYPES
    ]


def _get_existing_table_ids(client: GristClient) -> dict[str, str]:
    """Ids des tables du document, indexés en minuscules : Grist ne distingue
    pas deux tables par la casse."""
    return {
        table["id"].lower(): table["id"]
        for table in client.list_tables().get("tables", [])
    }


def _get_avis_table_id(demarche_number: int | str) -> str:
    return f"Demarche_{demarche_number}_avis"


def _ensure_table_structure(
    client: GristClient,
    existing_ids: dict[str, str],
    table_id: str,
    columns: list[dict[str, Any]],
    demarche_number: int | str | None = None,
    creation_columns: list[dict[str, Any]] | None = None,
) -> str:
    """
    Table créée si elle manque, sinon complétée des colonnes manquantes ;
    renvoie son id réel.

    `creation_columns` remplace `columns` à la création, qui sont ajoutées
    ensuite. Avec `demarche_number`, la table est rangée sous la page de la
    démarche.
    """
    existing_id = existing_ids.get(table_id.lower())
    if existing_id:
        log(f"Table existante trouvée: {existing_id}")
        _add_missing_columns(client, existing_id, columns)
        return existing_id

    initial_columns = creation_columns if creation_columns is not None else columns
    if demarche_number is None:
        created = client.create_table(table_id, initial_columns)
    else:
        created = client.create_demarche_table(
            demarche_number, table_id, initial_columns
        )
    created_id = created["tables"][0]["id"]

    if creation_columns is not None:
        _add_missing_columns(client, created_id, columns)

    return created_id


def _add_missing_columns(
    client: GristClient, table_id: str, columns: list[dict[str, Any]]
) -> None:
    """Ajoute à la table les colonnes de `columns` qu'elle n'a pas encore."""
    existing_columns = client.get_columns(table_id)
    if not existing_columns:
        log_error(
            f"Erreur lors de la récupération des colonnes pour la table {table_id}"
        )
        return

    missing_columns = [col for col in columns if col["id"] not in existing_columns]
    if not missing_columns:
        return

    log(f"Ajout de {len(missing_columns)} colonnes manquantes à la table {table_id}")
    add_response = client.add_columns(table_id, missing_columns)
    if add_response.status_code == 200:
        log("Colonnes ajoutées avec succès")
    else:
        log_error(f"Erreur lors de l'ajout des colonnes: {add_response.status_code}")
