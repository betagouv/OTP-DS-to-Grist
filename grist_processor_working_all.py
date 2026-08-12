import concurrent.futures
import hashlib
import json as json_module
import os
import re
import sys
import time
import traceback
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

import repetable_processor as rp
from deleted_dossiers_checker import check_deleted_dossiers
from grist.client import GristClient
from hide_id_columns import IdColumnHider
from queries import get_dossier
from queries_extract import dossier_to_flat_data
from queries_graphql import get_demarche_dossiers_filtered
from queries_util import get_timings
from schema_utils import (
    create_columns_from_schema,
    get_demarche_schema,
    get_demarche_schema_enhanced,
    update_grist_tables_from_schema,
)
from sync.tasks.instructeurs import sync_instructeurs
from sync.tasks.labels import sync_labels_for_demarche
from utils.api_validator import verify_api_connections
from utils.constants import DEMARCHES_API_URL, EXIT_CODE_EXTERNAL_API_ERROR
from utils.log import log, log_verbose, log_error, log_progress

API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = DEMARCHES_API_URL


def print_api_timings():
    timings = get_timings()
    if not timings:
        return

    total_duration = sum(t["duration"] for t in timings)

    print("\n" + "=" * 50)
    print("[API] Résumé des requêtes:")
    print("-" * 50)

    print("-" * 50)
    print(f"[API] Total: {len(timings)} requêtes en {total_duration:.2f}s")
    print("=" * 50 + "\n")


def _flatten_table_ids(value, acc):
    """Aplatit récursivement table_ids (dict/list/str imbriqués) en un set de tableId."""
    if isinstance(value, str):
        acc.add(value)
    elif isinstance(value, dict):
        for v in value.values():
            _flatten_table_ids(v, acc)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            _flatten_table_ids(v, acc)


def get_optimized_schema(demarche_number):
    """
    Récupération optimisée du schéma avec fallback automatique.
    """
    try:
        log("Récupération optimisée du schéma")
        return get_demarche_schema_enhanced(demarche_number, prefer_robust=True)
    except Exception as e:
        log_error(f"Erreur version optimisée: {e}")
        log("Fallback vers version classique")
        return get_demarche_schema(demarche_number)


def log_schema_improvements(schema, demarche_number):
    """Affiche les améliorations apportées par la nouvelle version"""
    if schema.get("metadata", {}).get("optimized"):
        log("AMÉLIORATIONS DÉTECTÉES:")
        revision_id = schema.get("metadata", {}).get("revision_id", "N/A")
        retrieved_at = schema.get("metadata", {}).get("retrieved_at", "N/A")
        log(f"Révision active: {revision_id}")
        log(f"Récupéré à: {retrieved_at}")
        log("Filtrage automatique des champs problématiques activé")
        log("Gestion robuste des erreurs activée")
        log("Métadonnées enrichies disponibles")


# Fonction pour supprimer les accents d'une chaîne de caractères
def normalize_column_name(name, max_length=150):
    """
    Normalise un nom de colonne pour Grist en garantissant des identifiants valides.
    Supprime les espaces en début, fin et les espaces consécutifs.

    Args:
        name: Le nom original de la colonne
        max_length: Longueur maximale autorisée (défaut: 50)

    Returns:
        str: Nom de colonne normalisé pour Grist
    """
    if not name:
        return "column"

    # Supprimer les espaces en début et fin, et remplacer les espaces consécutifs par un seul espace
    name = name.strip()
    name = re.sub(r"\s+", " ", name)

    name = name.replace("'", "_")
    name = name.replace("'", "_")  # Apostrophe typographique
    name = name.replace("`", "_")  # Accent grave utilisé comme apostrophe

    # ✅ NOUVEAU : Supprimer les numéros de début type "1. ", "2. ", etc.
    name = re.sub(r"^[\d]+[\.\)]\s*", "", name)

    # Supprimer les accents
    name = unicodedata.normalize("NFKD", name)
    name = "".join([c for c in name if not unicodedata.combining(c)])

    # Convertir en minuscules et remplacer les caractères non alphanumériques par des underscores
    name = name.lower()
    name = re.sub(r"[^a-z0-9_]", "_", name)

    # Éliminer les underscores multiples consécutifs
    name = re.sub(r"_+", "_", name)

    # Éliminer les underscores en début et fin
    name = name.strip("_")

    # S'assurer que le nom commence par une lettre
    if not name or not name[0].isalpha():
        name = "col_" + (name or "")

    # Tronquer si nécessaire à max_length caractères
    if len(name) > max_length:
        # Générer un hash pour garantir l'unicité
        hash_part = hashlib.md5(name.encode()).hexdigest()[:6]
        name = f"{name[: max_length - 7]}_{hash_part}"

    return name


# 1. D'abord, ajoutez la fonction filter_record_to_existing_columns après les autres fonctions utilitaires


def filter_record_to_existing_columns(client, table_id, record):
    """
    Filtre un enregistrement pour ne garder que les colonnes existantes dans la table.

    Args:
        client: Instance de GristClient
        table_id: ID de la table Grist
        record: Dictionnaire de l'enregistrement à filtrer

    Returns:
        dict: Enregistrement filtré
    """
    # Récupérer les colonnes existantes
    try:
        url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
        response = requests.get(url, headers=client.headers)

        if response.status_code != 200:
            log_error(
                f"Erreur lors de la récupération des colonnes: {response.status_code}"
            )
            return record  # Retourner l'enregistrement tel quel en cas d'erreur

        columns_data = response.json()
        existing_columns = set()

        if "columns" in columns_data:
            for col in columns_data["columns"]:
                existing_columns.add(col.get("id"))

        log_verbose(
            f"Colonnes existantes dans la table {table_id}: {len(existing_columns)}"
        )

        # Filtrer l'enregistrement
        filtered_record = {}
        for key, value in record.items():
            if key in existing_columns:
                filtered_record[key] = value
            else:
                log_verbose(f"  Colonne {key} ignorée car inexistante dans la table")

        # Toujours garder dossier_number pour les références
        if "dossier_number" in record and "dossier_number" not in filtered_record:
            filtered_record["dossier_number"] = record["dossier_number"]

        return filtered_record

    except Exception as e:
        log_error(f"Erreur lors du filtrage de l'enregistrement: {str(e)}")
        return record  # Retourner l'enregistrement tel quel en cas d'erreur


def detect_column_types_from_multiple_dossiers(dossiers_data, problematic_ids=None):
    """
    Détecte les types de colonnes pour les tables Grist à partir des données de plusieurs dossiers.
    """
    # Colonnes fixes pour la table des dossiers
    dossier_columns = [
        {"id": "dossier_id", "type": "Text"},
        {"id": "dossier_number", "type": "Int"},
        {"id": "state", "type": "Text"},
        {"id": "date_depot", "type": "DateTime"},
        {"id": "date_derniere_modification", "type": "DateTime"},
        {"id": "date_traitement", "type": "DateTime"},
        {"id": "date_expiration", "type": "DateTime"},
        {"id": "demandeur_type", "type": "Text"},
        {"id": "groupe_instructeur_id", "type": "Text"},
        {"id": "groupe_instructeur_number", "type": "Int"},
        {"id": "groupe_instructeur_label", "type": "Text"},
        {"id": "date_suppression", "type": "DateTime"},
        {"id": "label_names", "type": "Text"},
        {"id": "labels_json", "type": "Text"},
        {"id": "suivi_par", "type": "Text"},
        {"id": "date_accuse_lecture", "type": "DateTime"},
        {"id": "correction_instructeur", "type": "Text"},
        {"id": "date_derniere_correction_en_attente", "type": "DateTime"},
    ]

    # Colonnes de base pour la table des champs
    champ_columns = [
        {"id": "dossier_number", "type": "Int"},
    ]

    # Colonnes de base pour la table des annotations
    annotation_columns = [
        {"id": "dossier_number", "type": "Int"},
    ]

    # Dictionnaires pour suivre les types uniques
    unique_champ_columns = {}
    unique_annotation_columns = {}

    # Indicateurs de présence
    has_repetable_blocks = False
    has_carto_fields = False

    # Fonction pour déterminer le type de colonne
    def determine_column_type(value):
        if value is None:
            return "Text"
        elif isinstance(value, bool):
            return "Bool"
        elif isinstance(value, int):
            return "Int"
        elif isinstance(value, float):
            return "Numeric"
        elif isinstance(value, (datetime, str)) and (
            isinstance(value, datetime) or any(fmt in value for fmt in ["-", "T", ":"])
        ):
            return "DateTime"
        else:
            return "Text"

    # Fonction récursive pour vérifier les champs
    def check_for_repetable_and_carto(champs):
        nonlocal has_repetable_blocks, has_carto_fields

        for champ in champs:
            # Ignorer les types HeaderSectionChamp et ExplicationChamp
            if champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"]:
                continue

            if champ["__typename"] == "RepetitionChamp":
                has_repetable_blocks = True
                # Vérifier les champs à l'intérieur des blocs répétables
                for row in champ.get("rows", []):
                    if "champs" in row:
                        for field in row["champs"]:
                            # Ignorer les types HeaderSectionChamp et ExplicationChamp dans les blocs répétables
                            if field["__typename"] in [
                                "HeaderSectionChamp",
                                "ExplicationChamp",
                            ]:
                                continue

                            if field["__typename"] == "CarteChamp":
                                has_carto_fields = True
                                return  # Sortir dès qu'on a trouvé les deux types

            elif champ["__typename"] == "CarteChamp":
                has_carto_fields = True

    # Analyser tous les dossiers pour détecter les colonnes et les types de champs
    for dossier_data in dossiers_data:
        # Utiliser dossier_to_flat_data avec exclude_repetition_champs=True
        # pour exclure les blocs répétables de la table des champs
        flat_data = dossier_to_flat_data(
            dossier_data,
            exclude_repetition_champs=True,
            problematic_ids=problematic_ids,
        )

        # Collecter les champs
        for champ in flat_data["champs"]:
            # Ignorer les champs de type HeaderSectionChamp et ExplicationChamp
            if champ["type"] in ["HeaderSectionChamp", "ExplicationChamp"]:
                continue

            # Ignorer les champs dont l'ID est dans la liste des problématiques
            if problematic_ids and champ.get("id") in problematic_ids:
                continue

            champ_label = normalize_column_name(champ["label"])

            if champ_label not in unique_champ_columns:
                column_type = determine_column_type(champ.get("value"))

            if champ.get("type") == "YesNoChamp":
                print(f"DEBUG detect_column: {champ['label']}")
                print(
                    f"  Value: {champ.get('value')} (type: {type(champ.get('value'))})"
                )
                print(f"  Type déterminé: {column_type}")

                unique_champ_columns[champ_label] = column_type

        # Collecter les annotations
        for annotation in flat_data["annotations"]:
            # Ignorer les annotations de type HeaderSectionChamp et ExplicationChamp
            if annotation["type"] in ["HeaderSectionChamp", "ExplicationChamp"]:
                continue

            # Enlever le préfixe "annotation_" pour le nom de colonne dans la table des annotations
            original_label = annotation["label"]
            if original_label.startswith("annotation_"):
                annotation_label = normalize_column_name(
                    original_label[11:]
                )  # enlever "annotation_"
            else:
                annotation_label = normalize_column_name(original_label)

            if annotation_label not in unique_annotation_columns:
                column_type = determine_column_type(annotation.get("value"))
                unique_annotation_columns[annotation_label] = column_type

        # Vérifier la présence de blocs répétables et de champs cartographiques
        check_for_repetable_and_carto(dossier_data.get("champs", []))
        if not (
            has_repetable_blocks and has_carto_fields
        ):  # Continuer seulement si on n'a pas encore trouvé les deux
            check_for_repetable_and_carto(dossier_data.get("annotations", []))

        if has_repetable_blocks and has_carto_fields:
            break  # Sortir de la boucle si on a déjà trouvé les deux types

    # Ajouter les colonnes uniques détectées
    for col_name, col_type in unique_champ_columns.items():
        champ_columns.append({"id": col_name, "type": col_type})

    # Ajouter les colonnes uniques d'annotations détectées
    for col_name, col_type in unique_annotation_columns.items():
        annotation_columns.append({"id": col_name, "type": col_type})

    # Préparer le résultat
    result = {
        "dossier": dossier_columns,
        "champs": champ_columns,
        "annotations": annotation_columns,
        "has_repetable_blocks": has_repetable_blocks,
        "has_carto_fields": has_carto_fields,
    }

    # Ne détecter les colonnes des blocs répétables que si nécessaire
    if has_repetable_blocks:
        try:
            repetable_columns = rp.detect_repetable_columns_from_multiple_dossiers(
                dossiers_data
            )
            result["repetable_rows"] = repetable_columns
        except Exception as e:
            log_error(
                f"Erreur lors de la détection des colonnes des blocs répétables: {str(e)}"
            )
            traceback.print_exc()
            # Fournir au moins une structure de base en cas d'erreur
            result["repetable_rows"] = [
                {"id": "dossier_number", "type": "Int"},
                {"id": "block_label", "type": "Text"},
                {"id": "block_row_index", "type": "Int"},
                {"id": "block_row_id", "type": "Text"},
            ]

    return result


def get_problematic_descriptor_ids(demarche_number):
    """
    Récupère les IDs des descripteurs de champs problématiques (HeaderSectionChamp et ExplicationChamp)
    pour une démarche donnée, y compris dans les blocs répétables.
    """

    #  REQUÊTE CORRIGÉE avec exploration des blocs répétables
    query = """
    query getDemarche($demarcheNumber: Int!) {
      demarche(number: $demarcheNumber) {
        activeRevision {
          champDescriptors {
            __typename
            id
            type
            ... on RepetitionChampDescriptor {
              champDescriptors {
                __typename
                id
                type
              }
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

    response = requests.post(
        API_URL,
        json={"query": query, "variables": {"demarcheNumber": int(demarche_number)}},
        headers=headers,
    )

    response.raise_for_status()
    result = response.json()

    problematic_ids = set()

    # Vérifier les erreurs
    if "errors" in result:
        log_error(
            f"GraphQL errors: {', '.join([error.get('message', 'Unknown error') for error in result['errors']])}"
        )
        return problematic_ids

    #  FONCTION RÉCURSIVE pour explorer tous les descripteurs
    def explore_descriptors(descriptors):
        for descriptor in descriptors:
            # Ajouter si problématique
            if descriptor.get("type") in [
                "header_section",
                "explication",
            ] or descriptor.get("__typename") in [
                "HeaderSectionChampDescriptor",
                "ExplicationChampDescriptor",
            ]:
                problematic_ids.add(descriptor.get("id"))

            # Explorer récursivement les blocs répétables
            if (
                descriptor.get("__typename") == "RepetitionChampDescriptor"
                and "champDescriptors" in descriptor
            ):
                explore_descriptors(descriptor["champDescriptors"])

    # Extraire les IDs des champs problématiques
    if (
        result.get("data")
        and result["data"].get("demarche")
        and result["data"]["demarche"].get("activeRevision")
        and result["data"]["demarche"]["activeRevision"].get("champDescriptors")
    ):
        descriptors = result["data"]["demarche"]["activeRevision"]["champDescriptors"]
        explore_descriptors(descriptors)

    log(f"Nombre de descripteurs problématiques identifiés: {len(problematic_ids)}")

    return problematic_ids


# ========================================
# EXTRACTION DES DONNÉES DEMANDEUR
# ========================================


def extract_demandeur_data(dossier, demandeur_type):
    """
    Extrait les données du demandeur depuis un dossier selon son type
    """
    demandeur = dossier.get("demandeur", {})
    dossier_number = dossier.get("number")
    usager = dossier.get("usager", {})

    if demandeur_type == "PersonnePhysique":
        email = demandeur.get("email") or usager.get("email")
        return {
            "dossier_number": dossier_number,
            "type": demandeur_type,
            "civilite": demandeur.get("civilite"),
            "nom": demandeur.get("nom"),
            "prenom": demandeur.get("prenom"),
            "email": email,
            #  UNIQUEMENT pour PP
            "usager_email": usager.get("email", ""),
            "prenom_mandataire": dossier.get("prenomMandataire", ""),
            "nom_mandataire": dossier.get("nomMandataire", ""),
            "depose_par_un_tiers": dossier.get("deposeParUnTiers", False),
            "connection_usager": dossier.get("connectionUsager"),
        }

    # PersonneMorale

    entreprise = demandeur.get("entreprise", {})
    association = demandeur.get("association")
    address = demandeur.get("address", {})

    return {
        "dossier_number": dossier_number,
        "type": demandeur_type,
        #  UNIQUEMENT usager_email pour PM
        "usager_email": usager.get("email", ""),
        # Identifiants
        "siret": demandeur.get("siret"),
        "siren": entreprise.get("siren"),
        "siege_social": demandeur.get("siegeSocial"),
        "naf": demandeur.get("naf"),
        "libelle_naf": demandeur.get("libelleNaf"),
        # Entreprise (enrichi SIRENE)
        "raison_sociale": entreprise.get("raisonSociale"),
        "nom_commercial": entreprise.get("nomCommercial"),
        "forme_juridique": entreprise.get("formeJuridique"),
        "forme_juridique_code": entreprise.get("formeJuridiqueCode"),
        "capital_social": str(entreprise.get("capitalSocial"))
        if entreprise.get("capitalSocial") is not None
        else None,
        "code_effectif_entreprise": entreprise.get("codeEffectifEntreprise"),
        "numero_tva_intracommunautaire": entreprise.get("numeroTvaIntracommunautaire"),
        "date_creation": entreprise.get("dateCreation"),
        "etat_administratif": entreprise.get("etatAdministratif"),
        # Association (si applicable)
        "rna": association.get("rna") if association else None,
        "titre_association": association.get("titre") if association else None,
        "objet_association": association.get("objet") if association else None,
        "date_creation_association": association.get("dateCreation")
        if association
        else None,
        "date_declaration_association": association.get("dateDeclaration")
        if association
        else None,
        "date_publication_association": association.get("datePublication")
        if association
        else None,
        # Adresse enrichie
        "adresse_label": address.get("label"),
        "adresse_type": address.get("type"),
        "street_address": address.get("streetAddress"),
        "street_number": address.get("streetNumber"),
        "street_name": address.get("streetName"),
        "code_postal": address.get("postalCode"),
        "ville": address.get("cityName"),
        "code_insee_ville": address.get("cityCode"),
        "departement": address.get("departmentName"),
        "code_departement": address.get("departmentCode"),
        "region": address.get("regionName"),
        "code_region": address.get("regionCode"),
        "connection_usager": dossier.get("connectionUsager"),
    }


def format_value_for_grist(value, value_type):
    if value is None:
        return None

    if value_type == "DateTime":
        if isinstance(value, str):
            if value:
                for fmt in [
                    "%Y-%m-%dT%H:%M:%S.%fZ",
                    "%Y-%m-%dT%H:%M:%SZ",
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                ]:
                    try:
                        dt = datetime.strptime(value, fmt)
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        continue
            return value
        return value

    if value_type == "Text":
        return str(value)

    if value_type in ["Int", "Numeric"]:
        try:
            if value_type == "Int":
                return int(float(value)) if value else None
            return float(value) if value else None
        except (ValueError, TypeError):
            return None

    if value_type == "Bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["true", "1", "yes", "oui", "vrai"]
        return bool(value)

    return value


class ColumnCache:
    """
    Classe pour mettre en cache les informations sur les colonnes de tables Grist,
    évitant ainsi des requêtes répétées pour obtenir la structure des tables.
    """

    def __init__(self, client):
        self.client = client
        self.columns_cache = {}  # {table_id: {column_id: column_type}}

    def get_columns(self, table_id, force_refresh=False):
        """
        Récupère les colonnes d'une table, en utilisant le cache si disponible.

        Args:
            table_id: ID de la table Grist
            force_refresh: Force la récupération depuis l'API même si en cache

        Returns:
            set: Ensemble des IDs de colonnes
        """
        if table_id not in self.columns_cache or force_refresh:
            log_verbose(f"Récupération des colonnes pour la table {table_id}")
            url = f"{self.client.base_url}/docs/{self.client.doc_id}/tables/{table_id}/columns"
            response = requests.get(url, headers=self.client.headers)

            if response.status_code == 200:
                columns_data = response.json()
                column_ids = set()
                column_types = {}

                if "columns" in columns_data:
                    for col in columns_data["columns"]:
                        col_id = col.get("id")
                        col_type = col.get("type", "Text")
                        if col_id:
                            column_ids.add(col_id)
                            column_types[col_id] = col_type

                self.columns_cache[table_id] = {
                    "ids": column_ids,
                    "types": column_types,
                }
                log_verbose(f"  {len(column_ids)} colonnes en cache pour {table_id}")
            else:
                log_error(
                    f"Erreur lors de la récupération des colonnes: {response.status_code}"
                )
                self.columns_cache[table_id] = {"ids": set(), "types": {}}

        return self.columns_cache[table_id]["ids"]

    def get_column_type(self, table_id, column_id):
        """
        Récupère le type d'une colonne spécifique.

        Args:
            table_id: ID de la table Grist
            column_id: ID de la colonne

        Returns:
            str: Type de la colonne ou "Text" par défaut
        """
        if table_id not in self.columns_cache:
            self.get_columns(table_id)

        return self.columns_cache[table_id]["types"].get(column_id, "Text")

    def add_missing_columns(self, table_id, missing_columns, column_types=None):
        """
        Ajoute les colonnes manquantes et met à jour le cache.

        Args:
            table_id: ID de la table
            missing_columns: Liste des noms de colonnes manquantes
            column_types: Dictionnaire des types de colonnes

        Returns:
            tuple: (bool succès, dict mapping des noms de colonnes)
        """
        if not missing_columns:
            return True, {}

        # Obtenir les colonnes existantes
        existing_columns = self.get_columns(table_id)

        # Ne garder que les colonnes réellement manquantes
        columns_to_add = []
        column_mapping = {}

        for col_name in missing_columns:
            normalized_col_name = normalize_column_name(col_name)
            column_mapping[col_name] = normalized_col_name

            if normalized_col_name not in existing_columns:
                # Déterminer le type
                col_type = "Text"
                if column_types and "champs" in column_types:
                    champ_column_types = {
                        col["id"]: col["type"] for col in column_types["champs"]
                    }
                    if col_name in champ_column_types:
                        col_type = champ_column_types[col_name]

                columns_to_add.append({"id": normalized_col_name, "type": col_type})

        if not columns_to_add:
            return True, column_mapping

        # Ajouter les colonnes
        url = f"{self.client.base_url}/docs/{self.client.doc_id}/tables/{table_id}/columns"
        payload = {"columns": columns_to_add}

        log(f"  Ajout de {len(columns_to_add)} colonnes à la table {table_id}")
        response = requests.post(url, headers=self.client.headers, json=payload)

        if response.status_code == 200:
            log(
                f"  {len(columns_to_add)} colonnes ajoutées avec succès à la table {table_id}"
            )

            # Mettre à jour le cache
            if table_id in self.columns_cache:
                for col in columns_to_add:
                    self.columns_cache[table_id]["ids"].add(col["id"])
                    self.columns_cache[table_id]["types"][col["id"]] = col["type"]

            return True, column_mapping
        else:
            log_error(
                f"  Erreur lors de l'ajout des colonnes: {response.status_code} - {response.text}"
            )

            return False, column_mapping


def fetch_dossiers_in_parallel(dossier_numbers, max_workers=2, timeout=120):
    """
    Récupère plusieurs dossiers en parallèle.
    """
    results = {}
    errors = []

    def fetch_dossier(dossier_number):
        try:
            start_time = time.time()
            dossier_data = get_dossier(dossier_number)
            elapsed = time.time() - start_time
            log_verbose(f"Dossier {dossier_number} récupéré en {elapsed:.2f}s")
            return dossier_number, dossier_data
        except Exception as e:
            log_error(
                f"Erreur lors de la récupération du dossier {dossier_number}: {str(e)}"
            )
            return dossier_number, None

    log(
        f"Récupération en parallèle de {len(dossier_numbers)} dossiers avec {max_workers} workers..."
    )

    # Utiliser ThreadPoolExecutor pour le parallélisme
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_dossier = {
            executor.submit(fetch_dossier, dossier_num): dossier_num
            for dossier_num in dossier_numbers
        }

        for future in concurrent.futures.as_completed(
            future_to_dossier, timeout=timeout
        ):
            dossier_num = future_to_dossier[future]
            try:
                dossier_num, dossier_data = future.result()
                if dossier_data:
                    results[dossier_num] = dossier_data
                else:
                    errors.append(dossier_num)
            except Exception as e:
                log_error(f"Exception pour le dossier {dossier_num}: {str(e)}")
                errors.append(dossier_num)

    success_rate = len(results) / len(dossier_numbers) * 100 if dossier_numbers else 0
    log(
        f"Récupération parallèle terminée: {len(results)}/{len(dossier_numbers)} dossiers récupérés ({success_rate:.1f}%)"
    )

    if errors:
        log(f"Échecs: {len(errors)} dossiers n'ont pas pu être récupérés")

    return results


# Fonction pour récupérer les labels d'un dossier spécifique
def get_dossier_labels(dossier_number):
    """Récupère uniquement les labels d'un dossier spécifique"""

    query = """
    query GetDossierLabels($dossierNumber: Int!) {
        dossier(number: $dossierNumber) {
            id
            number
            labels {
                id
                name
                color
            }
        }
    }
    """

    variables = {"dossierNumber": int(dossier_number)}

    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        API_URL, json={"query": query, "variables": variables}, headers=headers
    )

    if response.status_code != 200:
        log_error(
            f"Erreur HTTP lors de la récupération des labels: {response.status_code}"
        )
        return None

    result = response.json()

    if "errors" in result:
        log_error("Erreurs GraphQL lors de la récupération des labels")
        return None

    return result.get("data", {}).get("dossier", {}).get("labels", [])


# Fonction pour ajouter des colonnes manquantes à une table Grist
def add_missing_columns_to_table(client, table_id, missing_columns, column_types=None):
    """
    Ajoute les colonnes manquantes à une table Grist existante.
    Vérifie que l'ajout a bien fonctionné avant de continuer.

    Args:
        client: Instance de GristClient
        table_id: ID de la table
        missing_columns: Liste des noms de colonnes manquantes
        column_types: Dictionnaire des types de colonnes (optionnel)

    Returns:
        tuple: (bool succès, dict mapping des noms de colonnes)
    """
    try:
        if not missing_columns:
            return True, {}  # Rien à ajouter

        # Mapping des noms originaux vers les noms normalisés
        column_mapping = {}
        columns_to_add = []

        for col_name in missing_columns:
            # Normaliser le nom de colonne
            normalized_col_name = normalize_column_name(col_name)
            column_mapping[col_name] = normalized_col_name

            # Déterminer le type de colonne (Text par défaut)
            col_type = "Text"

            # Si column_types est fourni, essayer de trouver le type
            if column_types and "champs" in column_types:
                champ_column_types = {
                    col["id"]: col["type"] for col in column_types["champs"]
                }
                if col_name in champ_column_types:
                    col_type = champ_column_types[col_name]

            # Ajouter la définition de colonne
            columns_to_add.append({"id": normalized_col_name, "type": col_type})

        if not columns_to_add:
            return True, column_mapping

        # Ajouter les colonnes à la table
        url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
        payload = {"columns": columns_to_add}

        log(f"  Ajout de {len(columns_to_add)} colonnes à la table {table_id}")
        for col in columns_to_add:
            log_verbose(f"  - Ajout de la colonne '{col['id']}' (type: {col['type']})")

        response = requests.post(url, headers=client.headers, json=payload)

        if response.status_code == 200:
            log(
                f"  {len(columns_to_add)} colonnes ajoutées avec succès à la table {table_id}"
            )

            # Vérifier que les colonnes ont bien été ajoutées
            verify_url = (
                f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
            )
            verify_response = requests.get(verify_url, headers=client.headers)

            if verify_response.status_code == 200:
                columns_data = verify_response.json()
                existing_column_ids = set()

                if "columns" in columns_data:
                    for col in columns_data["columns"]:
                        existing_column_ids.add(col.get("id"))

                # Vérifier quelles colonnes ont bien été ajoutées
                all_added = True
                for col in columns_to_add:
                    if col["id"] not in existing_column_ids:
                        log_error(f"  Colonne '{col['id']}' n'a pas été ajoutée")
                        all_added = False

                return all_added, column_mapping
            else:
                log_error(
                    f"  Erreur lors de la vérification des colonnes: {verify_response.status_code} - {verify_response.text}"
                )
                return False, column_mapping
        else:
            log_error(
                f"  Erreur lors de l'ajout des colonnes: {response.status_code} - {response.text}"
            )
            log_error(f"  Détails: {response.text}")
            return False, column_mapping

    except Exception as e:
        log_error(f"  Erreur lors de l'ajout des colonnes: {str(e)}")
        traceback.print_exc()
        return False, column_mapping


def add_id_columns_based_on_annotations(client, table_id, annotations):
    """
    Ajoute des colonnes pour les IDs des annotations basées sur leur label
    """
    columns_to_add = []

    for annotation in annotations:
        if "label" not in annotation or "id" not in annotation:
            continue

        original_label = annotation["label"]
        if original_label.startswith("annotation_"):
            normalized_label = normalize_column_name(original_label[11:])
        else:
            normalized_label = normalize_column_name(original_label)

        id_column = f"{normalized_label}_id"
        columns_to_add.append({"id": id_column, "type": "Text"})

    if columns_to_add:
        # Vérifier les colonnes existantes pour éviter des doublons
        url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
        response = requests.get(url, headers=client.headers)

        if response.status_code == 200:
            columns_data = response.json()
            existing_column_ids = set()

            if "columns" in columns_data:
                for col in columns_data["columns"]:
                    existing_column_ids.add(col.get("id"))

            # Filtrer pour n'ajouter que les colonnes manquantes
            columns_to_add = [
                col for col in columns_to_add if col["id"] not in existing_column_ids
            ]

        if columns_to_add:
            url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
            payload = {"columns": columns_to_add}
            response = requests.post(url, headers=client.headers, json=payload)

            if response.status_code != 200:
                log_error(f"Erreur lors de l'ajout des colonnes d'ID: {response.text}")
            else:
                log("Colonnes d'ID ajoutées avec succès")

                return [col["id"] for col in columns_to_add]


def run_demarche_level_tasks(
    client,
    table_ids,
    demarche_number,
    updated_since_cursor=None,
    force_full_sync=False,
    deleted_since_cursor=None,
    schema_method_successful=False,
):
    """
    Opérations de niveau démarche, indépendantes des dossiers effectivement traités.

    À appeler depuis les deux `return` de `process_demarche_for_grist_optimized` :
    celui de fin de fonction et celui du cas `total_dossiers == 0`. Poser une
    étiquette, ajouter un instructeur ou supprimer un dossier ne met à jour aucun
    dossier au sens d'`updatedSince` : sans le second appel, ces changements ne
    remonteraient dans Grist que si un dossier avait bougé par ailleurs.

    Chaque tâche est isolée dans son propre try/except : un échec n'empêche pas
    les suivantes.
    """
    # 1. Instructeurs (niveau démarche, à chaque sync)
    if table_ids.get("instructeurs"):
        try:
            sync_instructeurs(
                client, table_ids["instructeurs"], demarche_number, log, log_error
            )
        except Exception as e:
            log_error(f"Erreur synchronisation instructeurs: {e}")

    # 2. Labels : uniquement en sync incrémentale.
    #    En sync complète, tous les dossiers sont refetchés et leurs labels réécrits
    #    par le chemin principal — ce passage serait redondant.
    if updated_since_cursor and not force_full_sync:
        try:
            sync_labels_for_demarche(
                client, table_ids["dossier_table_id"], demarche_number, log, log_error
            )
        except Exception as e:
            log_error(f"Erreur rafraîchissement des labels: {e}")
    else:
        log("Sync complète — rafraîchissement des labels ignoré (déjà à jour).")

    # 3. Dossiers supprimés (API DN, curseur dédié)
    try:
        deletion_result = check_deleted_dossiers(
            client=client,
            table_id=table_ids["dossier_table_id"],
            demarche_number=demarche_number,
            log=log,
            log_error=log_error,
            deleted_since=deleted_since_cursor,
        )
        nb_deleted = (deletion_result or {}).get("newly_marked", 0)
        log(f"Nombre de dossiers marqués supprimés dans Grist : {nb_deleted}")
    except Exception as e:
        log_error(f"Erreur vérification dossiers supprimés : {e}")

    # 4. Masquage des colonnes _id (toujours en dernier)
    if schema_method_successful:
        try:
            current_table_ids = set()
            _flatten_table_ids(table_ids, current_table_ids)
            hider = IdColumnHider(client.base_url, client.api_key, client.doc_id)
            hider.hide_id_columns(table_ids=current_table_ids)
        except Exception as e:
            log_error(f"Erreur lors du masquage des colonnes _id: {e}")


# Fonction optimisée pour le traitement d'une démarche pour Grist (Possibilité d'augmenter ou de diminuer batch_size et max_workers)
# Cette fonction est conçue pour être plus rapide et plus efficace, en utilisant le traitement par lots et le traitement parallèle.
# Fonction optimisée complète et corrigée
# Remplace la fonction process_demarche_for_grist_optimized dans ton fichier
def process_demarche_for_grist_optimized(
    client,
    demarche_number,
    parallel=True,
    batch_size=100,
    max_workers=3,
    api_filters=None,
):
    """
    Version optimisée du traitement d'une démarche pour Grist avec filtrage côté serveur.

    Args:
        client: Instance de GristClient
        demarche_number: Numéro de la démarche
        parallel: Utiliser le traitement parallèle si True
        batch_size: Taille des lots pour le traitement par lot
        max_workers: Nombre maximum de workers pour le traitement parallèle
        api_filters: Filtres optimisés à appliquer côté serveur

    Returns:
        bool: Succès ou échec global
    """
    try:
        start_time = time.time()
        sync_start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Initialiser des ensembles pour suivre les dossiers traités
        successful_dossiers = set()
        failed_dossiers = set()

        # Initialiser le cache de colonnes
        column_cache = ColumnCache(client)

        # Vérifier que le document Grist existe
        try:
            doc_info = client.get_document_info()
            doc_name = (
                doc_info.get("name", client.doc_id)
                if isinstance(doc_info, dict)
                else "Document ID " + client.doc_id
            )
            log(f"Document Grist trouvé: {doc_name}")
        except Exception as e:
            log_error(f"Erreur lors de la vérification du document Grist: {e}")
            return False

        # Méthode avancée: Récupérer le schéma complet de la démarche
        problematic_descriptor_ids = set()
        column_types = None
        schema_method_successful = False
        log_progress.log(
            f"Récupération du schéma complet de la démarche {demarche_number}",
            reset=True,
        )

        # Essayer d'abord la méthode basée sur le schéma
        log(f"Récupération du schéma complet de la démarche {demarche_number}...")
        try:
            if (
                "get_demarche_schema" in globals()
                and "create_columns_from_schema" in globals()
            ):
                demarche_schema = get_optimized_schema(demarche_number)
                log_schema_improvements(demarche_schema, demarche_number)
                log(
                    f"Schéma récupéré avec succès pour la démarche: {demarche_schema['title']}"
                )

                # Générer les définitions de colonnes à partir du schéma complet
                column_types, problematic_descriptor_ids = create_columns_from_schema(
                    demarche_schema, demarche_number
                )

                # Récupérer les indicateurs de présence
                has_repetable_blocks = column_types.get("has_repetable_blocks", False)
                has_carto_fields = column_types.get("has_carto_fields", False)

                log(
                    f"Identificateurs de {len(problematic_descriptor_ids)} descripteurs problématiques à filtrer"
                )
                log("Types de colonnes détectés à partir du schéma:")
                log(f"  - Colonnes dossiers: {len(column_types['dossier'])}")
                log(f"  - Colonnes champs: {len(column_types['champs'])}")
                log(f"  - Colonnes annotations: {len(column_types['annotations'])}")
                log(
                    f"  - Blocs répétables détectés: {'Oui' if has_repetable_blocks else 'Non'}"
                )
                log(
                    f"  - Champs cartographiques détectés: {'Oui' if has_carto_fields else 'Non'}"
                )

                if has_repetable_blocks and "repetable_rows" in column_types:
                    log_verbose(
                        f"  - Colonnes blocs répétables: {len(column_types['repetable_rows'])}"
                    )

                # Marquer la méthode comme réussie
                schema_method_successful = True
            else:
                log(
                    "Méthode basée sur le schéma non disponible, utilisation de la méthode alternative..."
                )
        except Exception as e:
            log_error(f"Erreur lors de la récupération du schéma: {str(e)}")
            traceback.print_exc()
            log(
                "Utilisation de la méthode alternative avec échantillons de dossiers..."
            )

        # Essayer d'utiliser la méthode de mise à jour qui préserve les données existantes
        try:
            if "update_grist_tables_from_schema" in globals():
                log(
                    "Mise à jour des tables Grist en préservant les données existantes..."
                )
                table_result = update_grist_tables_from_schema(
                    client,
                    demarche_number,
                    column_types if schema_method_successful else None,
                    problematic_descriptor_ids,
                )

                # Convertir le format de retour pour compatibilité
                table_ids = {
                    "dossier_table_id": table_result.get("dossiers"),
                    "champ_table_id": table_result.get("champs"),
                    "annotations": table_result.get("annotations"),  #  Nouvelle clé
                    "annotation_table_id": table_result.get(
                        "annotations"
                    ),  #  Rétro-compatibilité
                }

                if "repetable_blocks" in table_result:
                    table_ids["repetable_blocks"] = table_result["repetable_blocks"]

                if "demandeurs" in table_result:
                    table_ids["demandeurs"] = table_result["demandeurs"]

                if "demandeur_type" in table_result:
                    table_ids["demandeur_type"] = table_result["demandeur_type"]

                if "instructeurs" in table_result:
                    table_ids["instructeurs"] = table_result["instructeurs"]

                if "avis" in table_result:
                    table_ids["avis"] = table_result["avis"]  # None si pas encore créée

            else:
                # Méthode classique qui peut effacer des données
                log(
                    "Utilisation de la méthode classique de création/modification de tables"
                )
                table_ids = client.create_or_clear_grist_tables(
                    demarche_number, column_types if schema_method_successful else None
                )
        except Exception as e:
            log_error(f"Erreur lors de la mise à jour des tables Grist: {str(e)}")
            # Fallback sur la méthode classique si pas de column_types
            if not schema_method_successful:
                # Récupérer les IDs des champs problématiques à filtrer
                problematic_descriptor_ids = get_problematic_descriptor_ids(
                    demarche_number
                )
                log(
                    f"Filtrage de {len(problematic_descriptor_ids)} descripteurs problématiques"
                )

                # Récupérer quelques dossiers pour analyse du schéma
                sample_dossiers = []
                sample_dossier_numbers = []

                # Utiliser l'ancienne méthode pour récupérer des échantillons
                try:
                    from queries_graphql import get_demarche_dossiers

                    all_dossiers_brief = get_demarche_dossiers(demarche_number)
                    sample_size = min(3, len(all_dossiers_brief))
                    sample_dossier_numbers = [
                        all_dossiers_brief[i]["number"] for i in range(sample_size)
                    ]

                    for num in sample_dossier_numbers:
                        dossier = get_dossier(num)
                        if dossier:
                            sample_dossiers.append(dossier)
                except Exception as e:
                    log_error(f"Erreur lors de la récupération des échantillons: {e}")
                    return False

                if not sample_dossiers:
                    log_error(
                        "Aucun dossier n'a pu être récupéré pour l'analyse du schéma"
                    )
                    return False

                # Détecter les types de colonnes
                log("Détection des types de colonnes...")
                column_types = detect_column_types_from_multiple_dossiers(
                    sample_dossiers, problematic_ids=problematic_descriptor_ids
                )

            # Fallback sur la méthode classique
            log("Fallback sur la méthode classique de création/modification de tables")
            table_ids = client.create_or_clear_grist_tables(
                demarche_number, column_types
            )

        # Charger les métadonnées de sync
        sync_meta = client.get_sync_metadata(demarche_number)
        force_full_sync = (
            sync_meta.get("force_full_sync", False) if sync_meta else False
        )
        updated_since_cursor = (
            None
            if force_full_sync
            else (sync_meta.get("updated_since_cursor") if sync_meta else None)
        )
        if updated_since_cursor and isinstance(updated_since_cursor, (int, float)):
            updated_since_cursor = datetime.fromtimestamp(
                updated_since_cursor, tz=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        sync_meta_grist_id = sync_meta.get("grist_id") if sync_meta else None
        deleted_since_cursor = (
            None
            if force_full_sync
            else (sync_meta.get("deleted_since_cursor") if sync_meta else None)
        )

        if force_full_sync:
            log("force_full_sync activé → sync complète forcée")
        elif updated_since_cursor:
            log(f"updatedSince cursor trouvé: {updated_since_cursor}")
        else:
            log("Pas de cursor updatedSince → sync complète")

        # Log des table IDs
        log("Tables utilisées pour l'importation:")
        log(f"  Table dossiers: {table_ids['dossier_table_id']}")
        log(f"  Table champs: {table_ids['champ_table_id']}")
        log(f"  Table annotations: {table_ids['annotation_table_id']}")

        # Récupération des dossiers
        if api_filters and api_filters:
            log(
                "[FILTRAGE] Récupération optimisée des dossiers avec filtres côté serveur..."
            )
            if api_filters.get("groupes_instructeurs"):
                log(
                    f"Filtre par groupes instructeurs (numéros): {', '.join(map(str, api_filters['groupes_instructeurs']))}"
                )
            if api_filters.get("statuts"):
                log(f"Filtre par statuts: {', '.join(api_filters['statuts'])}")
            if api_filters.get("date_debut"):
                log(f"Filtre par date de début: {api_filters['date_debut']}")
            if api_filters.get("date_fin"):
                log(f"Filtre par date de fin: {api_filters['date_fin']}")

            all_dossiers = get_demarche_dossiers_filtered(
                demarche_number,
                date_debut=api_filters.get("date_debut"),
                date_fin=api_filters.get("date_fin"),
                groupes_instructeurs=api_filters.get("groupes_instructeurs"),
                statuts=api_filters.get("statuts"),
                updated_since=updated_since_cursor,
            )

            total_dossiers = len(all_dossiers)
            log(f"[OK] Dossiers récupérés avec filtres optimisés: {total_dossiers}")
            filtered_dossiers = all_dossiers

        else:
            log(
                "[ATTENTION] Récupération classique de tous les dossiers (pas de filtres optimisés)"
            )

            # Récupérer les filtres depuis les variables d'environnement pour compatibilité
            date_debut_str = os.getenv("DATE_DEPOT_DEBUT", "")
            date_fin_str = os.getenv("DATE_DEPOT_FIN", "")
            statuts_filter = (
                os.getenv("STATUTS_DOSSIERS", "").split(",")
                if os.getenv("STATUTS_DOSSIERS")
                else []
            )
            groupes_filter = (
                os.getenv("GROUPES_INSTRUCTEURS", "").split(",")
                if os.getenv("GROUPES_INSTRUCTEURS")
                else []
            )

            # Nettoyer les filtres
            if date_debut_str.strip() == "":
                date_debut_str = None
            if date_fin_str.strip() == "":
                date_fin_str = None
            statuts_filter = [s for s in statuts_filter if s.strip()]
            groupes_filter = [g for g in groupes_filter if g.strip()]

            # Convertir les dates
            date_debut = None
            date_fin = None
            if date_debut_str:
                try:
                    date_debut = datetime.strptime(date_debut_str, "%Y-%m-%d")
                    log(f"Filtre par date de début: {date_debut.strftime('%Y-%m-%d')}")
                except ValueError:
                    log_error(f"Format de date de début invalide: {date_debut_str}")

            if date_fin_str:
                try:
                    date_fin = datetime.strptime(date_fin_str, "%Y-%m-%d")
                    log(f"Filtre par date de fin: {date_fin.strftime('%Y-%m-%d')}")
                except ValueError:
                    log_error(f"Format de date de fin invalide: {date_fin_str}")

            if statuts_filter:
                log(f"Filtre par statuts: {', '.join(statuts_filter)}")
            if groupes_filter:
                log(f"Filtre par groupes instructeurs: {', '.join(groupes_filter)}")

            # Récupérer tous les dossiers puis filtrer côté client
            from queries_graphql import get_demarche_dossiers

            log("Récupération de tous les dossiers avec pagination...")
            if updated_since_cursor:
                log(f"Récupération filtrée avec updatedSince: {updated_since_cursor}")
                all_dossiers = get_demarche_dossiers_filtered(
                    demarche_number, updated_since=updated_since_cursor
                )
            else:
                all_dossiers = get_demarche_dossiers(demarche_number)

            total_dossiers_brut = len(all_dossiers)
            log(f"Nombre total de dossiers trouvés: {total_dossiers_brut}")

            # Appliquer les filtres côté client
            filtered_dossiers = []
            for dossier in all_dossiers:
                # Filtre par statut
                if statuts_filter and dossier["state"] not in statuts_filter:
                    continue

                # Filtre par groupe instructeur
                if groupes_filter and (
                    not dossier.get("groupeInstructeur")
                    or str(dossier["groupeInstructeur"].get("number", ""))
                    not in groupes_filter
                ):
                    continue

                # Filtre par date de dépôt
                if date_debut or date_fin:
                    date_depot_str = dossier.get("dateDepot")
                    if not date_depot_str:
                        continue

                    try:
                        date_depot = datetime.strptime(
                            date_depot_str.split("T")[0], "%Y-%m-%d"
                        )

                        if date_debut and date_depot < date_debut:
                            continue
                        if date_fin and date_depot > date_fin:
                            continue
                    except (ValueError, AttributeError, TypeError):
                        continue

                filtered_dossiers.append(dossier)

            total_dossiers = len(filtered_dossiers)
            log(
                f"Après filtrage: {total_dossiers} dossiers ({(total_dossiers / total_dossiers_brut * 100) if total_dossiers_brut > 0 else 0:.1f}%)"
            )

        # Si aucun dossier ne correspond aux critères
        if total_dossiers == 0:
            if updated_since_cursor:
                cursor_dt = datetime.strptime(
                    updated_since_cursor, "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
                cursor_fr = cursor_dt.astimezone(ZoneInfo("Europe/Paris")).strftime(
                    "%d/%m/%Y à %H:%M:%S"
                )
                log(
                    f"Aucun dossier modifié ou ajouté depuis la dernière sync ({cursor_fr}) — Grist déjà à jour"
                )
            else:
                log("Aucun dossier ne correspond aux critères de filtrage")
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = elapsed_time % 60
            log("\nTraitement terminé!")
            log(f"Durée totale: {minutes} min {seconds:.1f} sec")
            log("Tables créées avec succès, mais aucun dossier à traiter.")
            sync_end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            try:
                client.save_sync_metadata(
                    demarche_number,
                    {
                        "last_sync_at": sync_end_time,
                        "updated_since_cursor": sync_start_time,
                        "deleted_since_cursor": sync_start_time,
                        "last_sync_status": "success",
                        "last_sync_duration": round(elapsed_time, 1),
                        "force_full_sync": False,
                    },
                )
            except Exception as e:
                log_error(f"Erreur sauvegarde Sync_metadata: {e}")

            run_demarche_level_tasks(
                client,
                table_ids,
                demarche_number,
                updated_since_cursor=updated_since_cursor,
                force_full_sync=force_full_sync,
                deleted_since_cursor=deleted_since_cursor,
                schema_method_successful=schema_method_successful,
            )

            return True

        # Organiser les dossiers en lots
        dossier_batches = []
        batch_count = (total_dossiers + batch_size - 1) // batch_size

        for i in range(0, total_dossiers, batch_size):
            batch_dossier_numbers = [
                filtered_dossiers[j]["number"]
                for j in range(i, min(i + batch_size, total_dossiers))
            ]
            dossier_batches.append(batch_dossier_numbers)

        log(f"Dossiers organisés en {batch_count} lots de {batch_size} maximum")

        descriptor_to_column_id = column_types.get("descriptor_to_column_id", {})

        # Fonction pour préparer un seul dossier (DÉFINIE AVANT LA BOUCLE)
        def prepare_single_dossier(
            dossier_num, dossier_data, column_types, problematic_descriptor_ids
        ):
            """Prépare les records pour un dossier (dossier, champ, annotation)"""
            try:
                exclude_repetition = column_types.get("has_repetable_blocks", False)
                flat_data = dossier_to_flat_data(
                    dossier_data,
                    exclude_repetition_champs=exclude_repetition,
                    problematic_ids=problematic_descriptor_ids,
                    descriptor_to_column_id=descriptor_to_column_id,
                )

                # Préparer dossier_record
                dossier_info = flat_data["dossier"]
                dossier_record = {}
                for column in column_types["dossier"]:
                    field_id = column["id"]
                    field_type = column["type"]

                    if field_id in dossier_info:
                        value = dossier_info[field_id]
                    elif "dossier_" + field_id in dossier_info:
                        value = dossier_info["dossier_" + field_id]
                    else:
                        continue

                    dossier_record[field_id] = format_value_for_grist(value, field_type)

                if "dossier_number" not in dossier_record:
                    dossier_record["dossier_number"] = dossier_num

                # ✅ Nouveau AJOUTER CES 4 LIGNES
                # Extraire les instructeurs qui suivent ce dossier
                instructeurs = dossier_data.get("instructeurs", [])
                emails_instructeurs = [
                    inst.get("email") for inst in instructeurs if inst.get("email")
                ]
                dossier_record["suivi_par"] = (
                    ", ".join(emails_instructeurs) if emails_instructeurs else None
                )

                # Préparer champ_record
                champ_record = {"dossier_number": dossier_num}
                champ_column_types = {
                    col["id"]: col.get("type")
                    or col.get("fields", {}).get("type", "Text")
                    for col in column_types["champs"]
                }

                champ_ids = []
                for champ in flat_data["champs"]:
                    if champ.get("id"):
                        champ_ids.append(str(champ["id"]))
                if champ_ids:
                    champ_record["champ_id"] = "_".join(champ_ids)

                for champ in flat_data["champs"]:
                    if champ.get("type") in ["HeaderSectionChamp", "ExplicationChamp"]:
                        continue
                    normalized_label = normalize_column_name(champ["label"])
                    value = champ.get("value", "")
                    if champ["type"] in [
                        "CarteChamp",
                        "AddressChamp",
                        "SiretChamp",
                    ] and champ.get("json_value"):
                        try:
                            value = json_module.dumps(
                                champ["json_value"], ensure_ascii=False
                            )
                        except Exception:
                            value = str(champ["json_value"])

                    column_type = champ_column_types.get(normalized_label, "Text")
                    champ_record[normalized_label] = format_value_for_grist(
                        value, column_type
                    )

                # Préparer annotation_record
                annotation_record = {"dossier_number": dossier_num}
                annotation_column_types = {
                    col["id"]: col.get("type")
                    or col.get("fields", {}).get("type", "Text")
                    for col in column_types["annotations"]
                }

                annotation_ids = []
                for annotation in flat_data["annotations"]:
                    if annotation.get("id"):
                        annotation_ids.append(str(annotation["id"]))
                if annotation_ids:
                    annotation_record["annotation_id"] = "_".join(annotation_ids)

                for annotation in flat_data["annotations"]:
                    if annotation["type"] in ["HeaderSectionChamp", "ExplicationChamp"]:
                        continue

                    original_label = annotation["label"]
                    if original_label.startswith("annotation_"):
                        normalized_label = normalize_column_name(original_label[11:])
                    else:
                        normalized_label = normalize_column_name(original_label)

                    value = annotation.get("value", "")
                    if annotation["type"] in [
                        "CarteChamp",
                        "AddressChamp",
                        "SiretChamp",
                    ] and annotation.get("json_value"):
                        try:
                            value = json_module.dumps(
                                annotation["json_value"], ensure_ascii=False
                            )
                        except Exception:
                            value = str(annotation["json_value"])

                    column_type = annotation_column_types.get(normalized_label, "Text")
                    annotation_record[normalized_label] = format_value_for_grist(
                        value, column_type
                    )

                    if "id" in annotation:
                        id_column = f"{normalized_label}_id"
                        annotation_record[id_column] = annotation["id"]

                return {
                    "dossier": dossier_record,
                    "champ": champ_record,
                    "annotation": annotation_record,
                    "annotations_list": flat_data["annotations"],
                }
            except Exception as e:
                log_error(f"Erreur préparation dossier {dossier_num}: {str(e)}")
                return None

        # Traiter les lots de dossiers
        total_success = 0
        total_errors = 0
        # Préchargement des caches UNE SEULE FOIS avant la boucle
        log("Préchargement des enregistrements existants (global)...")
        start_cache = time.time()
        cache_dossiers = client.get_existing_dossier_numbers(
            table_ids["dossier_table_id"]
        )
        cache_champs = client.get_existing_dossier_numbers(table_ids["champ_table_id"])
        cache_annotations = {}
        if table_ids.get("annotations"):
            cache_annotations = client.get_existing_dossier_numbers(
                table_ids.get("annotations")
            )
        cache_demandeurs = client.get_existing_dossier_numbers(table_ids["demandeurs"])
        log(f"Cache global préchargé en {time.time() - start_cache:.1f}s")

        # Construire les sets de dossiers à skipper par table
        skip_dossiers = set()
        skip_champs = set()
        skip_annotations = set()

        for batch_idx, batch in enumerate(dossier_batches):
            log(
                f"Traitement du lot {batch_idx + 1}/{batch_count} ({len(batch)} dossiers)..."
            )
            batch_start = time.time()

            # Filtrer les dossiers à fetcher (skip si inchangé sur toutes les tables)
            batch_to_fetch = [num for num in batch if str(num) not in skip_dossiers]
            skipped_count = len(batch) - len(batch_to_fetch)
            if skipped_count:
                log(f"  {skipped_count} dossier(s) inchangés → fetch DS skippé")

            # Récupérer les dossiers complets
            if batch_to_fetch:
                if parallel:
                    batch_dossiers_dict = fetch_dossiers_in_parallel(
                        batch_to_fetch, max_workers=max_workers
                    )
                else:
                    batch_dossiers_dict = {}
                    for num in batch_to_fetch:
                        dossier = get_dossier(num)
                        if dossier:
                            batch_dossiers_dict[num] = dossier
                        else:
                            log_error(
                                f"Dossier {num} inaccessible en raison de restrictions de permission, ignoré"
                            )
            else:
                batch_dossiers_dict = {}

            log(f"[TIMING] Récupération API DS: {time.time() - batch_start:.1f}s")
            log_progress.log("Communication API DN")

            if not batch_dossiers_dict:
                if skipped_count == len(batch):
                    log(
                        f"  Lot {batch_idx + 1} entièrement skippé (tous les dossiers sont à jour)"
                    )
                else:
                    log_error(
                        f"Aucun dossier n'a pu être récupéré pour le lot {batch_idx + 1}"
                    )
                continue

            # Préparer les dossiers EN PARALLÈLE
            log("Préparation des records en parallèle...")
            start_prep = time.time()
            dossier_records = []
            champ_records = []
            annotation_records = []
            all_annotations_for_columns = []

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                future_to_dossier = {
                    executor.submit(
                        prepare_single_dossier,
                        num,
                        data,
                        column_types,
                        problematic_descriptor_ids,
                    ): num
                    for num, data in batch_dossiers_dict.items()
                }

                for future in concurrent.futures.as_completed(future_to_dossier):
                    result = future.result()
                    if result:
                        dossier_records.append(result["dossier"])
                        champ_records.append(result["champ"])
                        annotation_records.append(result["annotation"])
                        all_annotations_for_columns.extend(result["annotations_list"])
                    else:
                        log_error("Résultat None pour un dossier")  # ← AJOUTE CE LOG

            log(
                f"Records préparés: {len(dossier_records)} dossiers, {len(champ_records)} champs, {len(annotation_records)} annotations"
            )  # ← AJOUTE APRÈS LA BOUCLE
            log(f"[TIMING] Préparation parallèle: {time.time() - start_prep:.1f}s")

            # Créer les colonnes UNE SEULE FOIS après la préparation
            if table_ids.get("annotations"):
                #  DÉDUPLICATION : Ne garder qu'une annotation par label unique
                unique_annotations = {}
                for ann in all_annotations_for_columns:
                    label = ann.get("label")
                    if label and label not in unique_annotations:
                        unique_annotations[label] = ann

                unique_annotations_list = list(unique_annotations.values())

                add_id_columns_based_on_annotations(
                    client,
                    table_ids.get("annotations"),
                    unique_annotations_list,  #  Passer la liste dédupliquée
                )
            # Effectuer les opérations d'upsert par lot
            dossier_records = [
                r
                for r in dossier_records
                if str(r.get("dossier_number") or r.get("number")) not in skip_dossiers
            ]
            if dossier_records:
                log(f"  Upsert par lot de {len(dossier_records)} dossiers...")
                success = client.upsert_multiple_dossiers_in_grist(
                    table_ids["dossier_table_id"],
                    dossier_records,
                    existing_records=cache_dossiers,
                    column_cache=column_cache,
                )

                # Mettre à jour les ensembles de dossiers
                for record in dossier_records:
                    dossier_num = record.get("number") or record.get("dossier_number")
                    if dossier_num:
                        if success:
                            successful_dossiers.add(str(dossier_num))
                        else:
                            failed_dossiers.add(str(dossier_num))

            champ_records = [
                r
                for r in champ_records
                if str(r.get("dossier_number")) not in skip_champs
            ]
            if champ_records:
                log(
                    f"  Upsert par lot de {len(champ_records)} enregistrements de champs..."
                )
                success = client.upsert_multiple_dossiers_in_grist(
                    table_ids["champ_table_id"],
                    champ_records,
                    existing_records=cache_champs,
                    column_cache=column_cache,
                )
                if success:
                    total_success += len(champ_records)
                else:
                    total_errors += len(champ_records)

                log(f"[TIMING] Après upsert champs: {time.time() - batch_start:.1f}s")
                log_progress.log("Mise à jour des enregistrements de champs")

            annotation_records = [
                r
                for r in annotation_records
                if str(r.get("dossier_number")) not in skip_annotations
            ]
            if annotation_records and table_ids.get("annotations"):
                log(
                    f"  Upsert par lot de {len(annotation_records)} enregistrements d'annotations..."
                )
                success = client.upsert_multiple_dossiers_in_grist(
                    table_ids.get("annotations"),
                    annotation_records,
                    existing_records=cache_annotations,
                    column_cache=column_cache,
                )

                log(
                    f"[TIMING] Après upsert annotations: {time.time() - batch_start:.1f}s"
                )
            elif annotation_records:
                log("  Annotations présentes mais pas de table - ignorées")

            log_progress.log("Mise à jour des annotations")

            # Traiter les demandeurs par lot
            if table_ids.get("demandeurs") and table_ids.get("demandeur_type"):
                log(
                    f"  Traitement des demandeurs par lot ({len(batch_dossiers_dict)} dossiers)..."
                )

                demandeur_records = []
                demandeur_type = table_ids["demandeur_type"]

                for dossier_num, dossier_data in batch_dossiers_dict.items():
                    if str(dossier_num) in skip_dossiers:
                        continue
                    try:
                        demandeur_data = extract_demandeur_data(
                            dossier_data, demandeur_type
                        )
                        demandeur_records.append(demandeur_data)
                    except Exception as e:
                        log_error(
                            f"  Erreur extraction demandeur dossier {dossier_num}: {str(e)}"
                        )

                if demandeur_records:
                    log(f"  Upsert par lot de {len(demandeur_records)} demandeurs...")
                    success = client.upsert_multiple_dossiers_in_grist(
                        table_ids["demandeurs"],
                        demandeur_records,
                        existing_records=cache_demandeurs,
                        column_cache=column_cache,
                    )
                    if success:
                        log(
                            f"   {len(demandeur_records)} demandeurs traités avec succès"
                        )
                    else:
                        log_error("   Erreur lors du traitement des demandeurs")

                log(
                    f"[TIMING] Après upsert demandeurs: {time.time() - batch_start:.1f}s"
                )
                log_progress.log("Mise à jour des demandeurs")

            # Traiter les blocs répétables si nécessaire (tables séparées par bloc)
            if column_types.get("has_repetable_blocks", False) and table_ids.get(
                "repetable_blocks"
            ):
                # Collecter toutes les lignes répétables
                all_repetable_rows = []
                filtered_repetable_dict = {
                    num: data
                    for num, data in batch_dossiers_dict.items()
                    if str(num) not in skip_champs
                }
                for dossier_data in filtered_repetable_dict.values():
                    exclude_repetition = False
                    flat_data = dossier_to_flat_data(
                        dossier_data,
                        exclude_repetition_champs=exclude_repetition,
                        problematic_ids=problematic_descriptor_ids,
                    )
                    if flat_data.get("repetable_rows"):
                        all_repetable_rows.extend(flat_data["repetable_rows"])

                # Grouper par block_label
                rows_by_block = {}
                for row in all_repetable_rows:
                    block_label = row.get("block_label", "")
                    if block_label not in rows_by_block:
                        rows_by_block[block_label] = []
                    rows_by_block[block_label].append(row)

                # Traiter chaque bloc
                for block_label, rows in rows_by_block.items():
                    normalized_block = normalize_column_name(block_label)

                    if normalized_block in table_ids.get("repetable_blocks", {}):
                        block_table_id = table_ids["repetable_blocks"][normalized_block]

                        try:
                            from repetable_processor import process_repetables_batch

                            # Préparer les données pour le batch
                            success_count, error_count = process_repetables_batch(
                                client,
                                list(batch_dossiers_dict.values()),
                                {normalized_block: block_table_id},
                                {
                                    normalized_block: column_types["repetable_blocks"][
                                        normalized_block
                                    ]
                                },
                                problematic_ids=problematic_descriptor_ids,
                                batch_size=50,
                            )
                            log(
                                f"  Bloc '{block_label}': {success_count} réussis, {error_count} échecs"
                            )
                        except Exception as e:
                            log_error(
                                f"  Erreur traitement bloc '{block_label}': {str(e)}"
                            )

            log(f"[TIMING] Après blocs répétables: {time.time() - batch_start:.1f}s")
            log_progress.log("Traitement des champs répétables")

            # Traiter les avis du lot
            all_avis_records = []
            for dossier_data in batch_dossiers_dict.values():
                avis = dossier_data.get("avis", [])
                if avis:
                    from queries_extract import extract_avis_from_dossier

                    all_avis_records.extend(extract_avis_from_dossier(dossier_data))

            if all_avis_records:
                # Créer la table à la volée si elle n'existe pas encore
                if not table_ids.get("avis"):
                    log("  Création lazy de la table avis...")
                    from schema_utils import create_avis_columns

                    avis_table_id = f"Demarche_{demarche_number}_avis"
                    result = client.create_table(avis_table_id, create_avis_columns())
                    table_ids["avis"] = result["tables"][0].get("id")
                    log(f"  Table avis créée: {table_ids['avis']}")

                log(f"  Upsert de {len(all_avis_records)} avis...")
                url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_ids['avis']}/records"

                # Récupérer existants pour upsert par avis_id
                existing_avis = {}
                response = requests.get(url, headers=client.headers)
                if response.status_code == 200:
                    for record in response.json().get("records", []):
                        avis_id = record.get("fields", {}).get("avis_id")
                        if avis_id:
                            existing_avis[avis_id] = record.get("id")

                to_create = []
                to_update = []
                for avis in all_avis_records:
                    avis_id = avis.get("avis_id")
                    if avis_id in existing_avis:
                        to_update.append({"id": existing_avis[avis_id], "fields": avis})
                    else:
                        to_create.append(avis)

                if to_create:
                    requests.post(
                        url,
                        headers=client.headers,
                        json={"records": [{"fields": r} for r in to_create]},
                    )
                    log(f"   {len(to_create)} avis créé(s)")
                if to_update:
                    requests.patch(
                        url, headers=client.headers, json={"records": to_update}
                    )
                    log(f"   {len(to_update)} avis mis à jour")

            if all_avis_records:
                log(f"[TIMING] Après avis: {time.time() - batch_start:.1f}s")
                log_progress.log("Traitement de la table Avis")

        # Calculer les statistiques finales
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = elapsed_time % 60

        # Calculer les nombres à partir des ensembles
        total_success = len(successful_dossiers)
        total_errors = len(failed_dossiers)

        log("\nTraitement terminé!")
        log(f"Durée totale: {minutes} min {seconds:.1f} sec")
        log(f"Dossiers traités avec succès: {total_success}")
        if total_errors > 0:
            log(f"Dossiers en échec: {total_errors}")

        # Sauvegarder le curseur de sync
        sync_end_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            client.save_sync_metadata(
                demarche_number,
                {
                    "last_sync_at": sync_end_time,
                    "updated_since_cursor": sync_start_time,
                    "deleted_since_cursor": sync_start_time,
                    "last_sync_status": "success" if total_errors == 0 else "partial",
                    "last_sync_duration": round(elapsed_time, 1),
                    "force_full_sync": False,
                },
                existing_grist_id=sync_meta_grist_id,
            )
        except Exception as e:
            log_error(f"Erreur sauvegarde Sync_metadata: {e}")

        run_demarche_level_tasks(
            client,
            table_ids,
            demarche_number,
            updated_since_cursor=updated_since_cursor,
            force_full_sync=force_full_sync,
            deleted_since_cursor=deleted_since_cursor,
            schema_method_successful=schema_method_successful,
        )
        return total_success > 0 or schema_method_successful

    except Exception as e:
        log_error(f"Erreur lors du traitement de la démarche pour Grist: {e}")
        traceback.print_exc()
        return False


def main():
    load_dotenv()

    # Récupérer les variables d'environnement
    ds_api_token = os.getenv("DEMARCHES_API_TOKEN")
    demarche_number = os.getenv("DEMARCHE_NUMBER")
    grist_base_url = os.getenv("GRIST_BASE_URL")
    grist_api_key = os.getenv("GRIST_API_KEY")
    grist_doc_id = os.getenv("GRIST_DOC_ID")

    # Vérifier la configuration Grist
    if not all([grist_base_url, grist_api_key, grist_doc_id]):
        log_error("Configuration Grist incomplète")
        log("Assurez-vous d'avoir défini GRIST_BASE_URL, GRIST_API_KEY et GRIST_DOC_ID")
        return 1

    # Masquer partiellement la clé API par sécurité
    api_key_masked = (
        grist_api_key[:4] + "..." + grist_api_key[-4:]
        if len(grist_api_key) > 8
        else "***"
    )
    log("Configuration Grist:")
    log(f"  URL de base: {grist_base_url}")
    log(f"  Clé API: {api_key_masked}")
    log(f"  ID du document: {grist_doc_id}")

    # Vérifier le numéro de démarche
    if not demarche_number:
        log_error("DEMARCHE_NUMBER non défini")
        return 1

    # Vérifier les connexions aux APIs avant de commencer
    if all(
        [ds_api_token, demarche_number, grist_base_url, grist_api_key, grist_doc_id]
    ):
        log("Vérification des connexions aux APIs...")
        log_progress.log("Vérification des connexions aux APIs")
        success, results = verify_api_connections(
            ds_api_token, demarche_number, grist_base_url, grist_api_key, grist_doc_id
        )

        if not success:
            log_error("Échec de la vérification des connexions API:")

            for r in results:
                status = "✓" if r["success"] else "✗"
                log_error(f"  {r['type']}: {status} {r['message']}")

            return EXIT_CODE_EXTERNAL_API_ERROR
        else:
            log("✓ Connexions aux APIs vérifiées avec succès")
    else:
        log(
            "⚠ Configuration incomplète pour tester les connexions API (certaines variables sont manquantes)"
        )
    try:
        # Convertir le numéro de démarche en entier
        demarche_number = int(demarche_number)
        log(f"Traitement de la démarche: {demarche_number}")
    except ValueError:
        log_error("DEMARCHE_NUMBER doit être un nombre entier")
        return 1

    # Initialiser le client Grist
    client = GristClient(grist_base_url, grist_api_key, grist_doc_id)

    # NOUVEAU : Récupérer les filtres optimisés depuis l'environnement
    api_filters_json = os.getenv("API_FILTERS_JSON", "{}")
    try:
        api_filters = json_module.loads(api_filters_json)
        if api_filters:
            log(f"[FILTRAGE] Filtres optimisés détectés: {list(api_filters.keys())}")
    except Exception:
        api_filters = {}
        log("Aucun filtre optimisé détecté, utilisation de l'ancienne méthode")

    # Récupérer les autres paramètres
    parallel = os.getenv("PARALLEL", "true").lower() == "true"
    batch_size = int(os.getenv("BATCH_SIZE", "50"))
    max_workers = int(os.getenv("MAX_WORKERS", "3"))

    # Traiter la démarche avec la fonction optimisée
    if process_demarche_for_grist_optimized(
        client,
        demarche_number,
        parallel=parallel,
        batch_size=batch_size,
        max_workers=max_workers,
        api_filters=api_filters,  # Passer les filtres optimisés
    ):
        log(f"Traitement de la démarche {demarche_number} terminé avec succès")
        print_api_timings()
        return 0
    else:
        log_error(f"Échec du traitement de la démarche {demarche_number}")
        print_api_timings()
        return 1


if __name__ == "__main__":
    sys.exit(main())
