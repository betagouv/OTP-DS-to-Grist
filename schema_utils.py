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

from utils.constants import DEMARCHES_API_URL
from dn.schema import (
    get_problematic_descriptor_ids_from_schema,
    auto_clean_schema_descriptors,
    get_demarche_schema,
    get_demarche_schema_robust,
    get_demarche_schema_enhanced,
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

from grist.schema import (
    create_demandeurs_pp_columns,
    create_demandeurs_pm_columns,
    create_instructeurs_columns,
    create_avis_columns,
)


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


# ========================================
# FONCTIONS EXISTANTES - RÉ-EXPORTÉES DEPUIS dn.schema
# ========================================
from dn.schema import create_columns_from_schema  # noqa: F401


def update_grist_tables_from_schema(
    client, demarche_number, column_types, problematic_ids=None
):
    """
    Met à jour les tables Grist existantes en fonction du schéma actuel de la démarche,
    en ajoutant les nouvelles colonnes sans supprimer les données existantes.

     NOUVEAU : Crée une table séparée pour chaque bloc répétable

    Args:
        client: Instance GristClient
        demarche_number: Numéro de la démarche
        column_types: Définitions des colonnes depuis create_columns_from_schema
        problematic_ids: IDs des descripteurs problématiques (optionnel)

    Returns:
        dict: IDs des tables créées/mises à jour
    """
    from utils.log import log, log_error

    try:
        log(
            f"Mise à jour des tables Grist pour la démarche {demarche_number} d'après le schéma..."
        )

        # Noms des tables
        dossier_table_id = f"Demarche_{demarche_number}_dossiers"
        champ_table_id = f"Demarche_{demarche_number}_champs"
        annotation_table_id = f"Demarche_{demarche_number}_annotations"
        has_repetable_blocks = column_types.get("has_repetable_blocks", False)

        # Récupérer toutes les tables existantes
        tables = client.list_tables()

        #  CORRECTION : Extraire la liste des tables
        if isinstance(tables, dict) and "tables" in tables:
            tables = tables["tables"]

        # Trouver les tables existantes
        dossier_table = None
        champ_table = None
        annotation_table = None

        for table in tables:
            table_id = table.get("id", "").lower()
            if table_id == dossier_table_id.lower():
                dossier_table = table
                dossier_table_id = table.get("id")
                log(f"Table dossiers existante trouvée avec l'ID {dossier_table_id}")
            elif table_id == champ_table_id.lower():
                champ_table = table
                champ_table_id = table.get("id")
                log(f"Table champs existante trouvée avec l'ID {champ_table_id}")
            elif table_id == annotation_table_id.lower():
                annotation_table = table
                annotation_table_id = table.get("id")
                log(
                    f"Table annotations existante trouvée avec l'ID {annotation_table_id}"
                )

        # Fonction pour ajouter les colonnes manquantes à une table
        def add_missing_columns(table_id, all_columns):
            if not table_id:
                return

            # Récupérer les colonnes existantes
            url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
            response = requests.get(url, headers=client.headers)

            if response.status_code != 200:
                log_error(
                    f"Erreur lors de la récupération des colonnes: {response.status_code}"
                )
                return

            columns_data = response.json()
            existing_columns = set()

            if "columns" in columns_data:
                for col in columns_data["columns"]:
                    existing_columns.add(col.get("id"))

            # Trouver les colonnes manquantes
            missing_columns = []
            for col in all_columns:
                if col["id"] not in existing_columns:
                    missing_columns.append(col)

            # Ajouter les colonnes manquantes
            if missing_columns:
                log(
                    f"Ajout de {len(missing_columns)} colonnes manquantes à la table {table_id}"
                )
                add_payload = {"columns": missing_columns}
                add_response = requests.post(
                    url, headers=client.headers, json=add_payload
                )

                if add_response.status_code == 200:
                    log("Colonnes ajoutées avec succès")
                else:
                    log_error(
                        f"Erreur lors de l'ajout des colonnes: {add_response.status_code}"
                    )

        # Créer ou mettre à jour la table des dossiers
        if not dossier_table:
            log(f"Création de la table {dossier_table_id}")
            dossier_table_result = client.create_table(
                dossier_table_id, column_types["dossier"]
            )
            dossier_table = dossier_table_result["tables"][0]
            dossier_table_id = dossier_table.get("id")
        else:
            add_missing_columns(dossier_table_id, column_types["dossier"])

        # Créer ou mettre à jour la table des champs
        if not champ_table:
            log(f"Création de la table {champ_table_id}")
            base_columns = [
                {"id": "dossier_number", "type": "Int"},
                {"id": "champ_id", "type": "Text"},
            ]
            champ_table_result = client.create_table(champ_table_id, base_columns)
            champ_table = champ_table_result["tables"][0]
            champ_table_id = champ_table.get("id")

            # Ajouter toutes les colonnes spécifiques
            add_missing_columns(champ_table_id, column_types["champs"])
        else:
            add_missing_columns(champ_table_id, column_types["champs"])

        # Créer ou mettre à jour la table des annotations
        if not annotation_table:
            # ✅ NOUVELLE CONDITION : Ne créer que s'il y a des annotations
            if (
                len(column_types["annotations"]) > 1
            ):  # > 1 car il y a toujours dossier_number
                log(f"Création de la table {annotation_table_id}")
                base_columns = [{"id": "dossier_number", "type": "Int"}]
                annotation_table_result = client.create_table(
                    annotation_table_id, base_columns
                )
                annotation_table = annotation_table_result["tables"][0]
                annotation_table_id = annotation_table.get("id")

                # Ajouter toutes les colonnes spécifiques
                add_missing_columns(annotation_table_id, column_types["annotations"])
            else:
                log(f"Aucune annotation - table {annotation_table_id} non créée")
                annotation_table_id = None
        else:
            add_missing_columns(annotation_table_id, column_types["annotations"])

        #  NOUVEAU : Créer ou mettre à jour les tables des blocs répétables (une par bloc)
        repetable_table_ids = {}
        if has_repetable_blocks and "repetable_blocks" in column_types:
            for block_key, block_info in column_types["repetable_blocks"].items():
                table_id = f"Demarche_{demarche_number}_repetable_{block_key}"

                # Chercher si la table existe déjà
                existing_table = None
                for table in tables:
                    if table.get("id", "").lower() == table_id.lower():
                        existing_table = table
                        table_id = table.get("id")
                        log(
                            f"Table répétable '{block_info['original_label']}' existante trouvée: {table_id}"
                        )
                        break

                if not existing_table:
                    log(
                        f"Création de la table {table_id} pour le bloc '{block_info['original_label']}'"
                    )
                    table_result = client.create_table(table_id, block_info["columns"])
                    table_id = table_result["tables"][0].get("id")
                else:
                    # Ajouter les colonnes manquantes
                    add_missing_columns(table_id, block_info["columns"])

                repetable_table_ids[block_key] = table_id

        #  NOUVEAU : Créer ou mettre à jour la table demandeurs
        log("Création/mise à jour de la table demandeurs...")
        demandeurs_table_id = f"Demarche_{demarche_number}_demandeurs"

        # Détecter le type et créer les colonnes
        demandeurs_columns, demandeur_type = create_demandeurs_columns(demarche_number)
        log(f"Type de demandeur: {demandeur_type} - {len(demandeurs_columns)} colonnes")

        # Chercher si la table existe
        demandeurs_table = None
        for table in tables:
            if table.get("id", "").lower() == demandeurs_table_id.lower():
                demandeurs_table = table
                demandeurs_table_id = table.get("id")
                log(f"Table demandeurs existante trouvée: {demandeurs_table_id}")
                break

        # Créer ou mettre à jour
        if not demandeurs_table:
            log(f"Création de la table {demandeurs_table_id} (type: {demandeur_type})")
            demandeurs_table_result = client.create_table(
                demandeurs_table_id, demandeurs_columns
            )
            demandeurs_table = demandeurs_table_result["tables"][0]
            demandeurs_table_id = demandeurs_table.get("id")
        else:
            log("Mise à jour des colonnes de la table demandeurs")
            add_missing_columns(demandeurs_table_id, demandeurs_columns)

        # Créer/mettre à jour la table instructeurs
        log("Création/mise à jour de la table instructeurs...")
        instructeurs_table_id = f"Demarche_{demarche_number}_instructeurs"
        instructeurs_table = next(
            (t for t in tables if t.get("id") == instructeurs_table_id), None
        )

        if not instructeurs_table:
            log(f"Création de la table {instructeurs_table_id}")
            instructeurs_columns = create_instructeurs_columns()
            instructeurs_table_result = client.create_table(
                instructeurs_table_id, instructeurs_columns
            )
            instructeurs_table = instructeurs_table_result["tables"][0]
            instructeurs_table_id = instructeurs_table.get("id")
        else:
            log("Mise à jour des colonnes de la table instructeurs")
            instructeurs_columns = create_instructeurs_columns()
            add_missing_columns(instructeurs_table_id, instructeurs_columns)

        # Créer/mettre à jour la table avis (seulement si elle existe déjà)
        avis_table_id = f"Demarche_{demarche_number}_avis"
        avis_table = next((t for t in tables if t.get("id") == avis_table_id), None)

        if avis_table:
            log(f"Table avis existante trouvée: {avis_table_id}")
            add_missing_columns(avis_table_id, create_avis_columns())
        else:
            log("Table avis non créée (sera créée au premier avis détecté)")
            avis_table_id = None

        # Retourner les IDs des tables
        result = {
            "dossiers": dossier_table_id,
            "champs": champ_table_id,
            "demandeurs": demandeurs_table_id,
            "demandeur_type": demandeur_type,
            "instructeurs": instructeurs_table_id,
            "avis": avis_table_id,  # None si pas encore créée
        }

        # ✅ Ajouter annotations seulement si la table existe
        if annotation_table_id:
            result["annotations"] = annotation_table_id

        # Ajouter les blocs répétables si présents
        if has_repetable_blocks:
            result["repetable_blocks"] = repetable_table_ids

        # Créer ou mettre à jour la table Sync_metadata
        sync_metadata_table_id = "Sync_metadata"
        sync_metadata_columns = [
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
        ]

        # Recharger la liste des tables pour les inclure celles créées pendant cette exécution
        fresh_tables = client.list_tables()
        if isinstance(fresh_tables, dict) and "tables" in fresh_tables:
            fresh_tables = fresh_tables["tables"]
        sync_table = next(
            (t for t in fresh_tables if t.get("id") == sync_metadata_table_id), None
        )
        if not sync_table:
            log(f"Création de la table {sync_metadata_table_id}")
            client.create_table(sync_metadata_table_id, sync_metadata_columns)
        else:
            add_missing_columns(sync_metadata_table_id, sync_metadata_columns)

        # Créer ou mettre à jour la table Sync_metadata
        sync_metadata_table_id = "Sync_metadata"
        sync_metadata_columns = [
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
        ]

        # Recharger la liste des tables pour les inclure celles créées pendant cette exécution
        fresh_tables = client.list_tables()
        if isinstance(fresh_tables, dict) and "tables" in fresh_tables:
            fresh_tables = fresh_tables["tables"]
        sync_table = next(
            (t for t in fresh_tables if t.get("id") == sync_metadata_table_id), None
        )
        if not sync_table:
            log(f"Création de la table {sync_metadata_table_id}")
            client.create_table(sync_metadata_table_id, sync_metadata_columns)
        else:
            add_missing_columns(sync_metadata_table_id, sync_metadata_columns)

        result["sync_metadata"] = sync_metadata_table_id

        log("Mise à jour des tables terminée avec succès")
        return result

    except Exception as e:
        log_error(f"Erreur lors de la mise à jour des tables: {str(e)}")
        raise
