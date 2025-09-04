"""
Module d'utilitaires pour récupérer et traiter le schéma complet d'une démarche
à partir de l'API Démarches Simplifiées, pour la création correcte de tables Grist.
"""

import requests
import json
from typing import Dict, List, Any, Tuple, Optional, Set

# Importer les configurations nécessaires
from queries_config import API_TOKEN, API_URL
# SUPPRESSION DE LA LIGNE PROBLÉMATIQUE :
# from grist_processor_working_all import normalize_column_name, log, log_verbose, log_error

def get_demarche_schema(demarche_number):
    """
    Récupère le schéma complet d'une démarche avec tous ses descripteurs de champs,
    sans dépendre des dossiers existants.
    
    Args:
        demarche_number: Numéro de la démarche
        
    Returns:
        dict: Structure complète des descripteurs de champs et d'annotations
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré. Définissez DEMARCHES_API_TOKEN dans le fichier .env")
    
    # Requête GraphQL spécifique pour récupérer les descripteurs de champs
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
        "Content-Type": "application/json"
    }
    
    # Exécuter la requête
    response = requests.post(
        API_URL,
        json={"query": query, "variables": {"demarcheNumber": int(demarche_number)}},
        headers=headers
    )
    
    # Vérifier le code de statut
    response.raise_for_status()
    
    # Analyser la réponse JSON
    result = response.json()
    
    # Vérifier les erreurs
    if "errors" in result:
        filtered_errors = []
        for error in result["errors"]:
            error_message = error.get("message", "")
            if "permissions" not in error_message and "hidden due to permissions" not in error_message:
                filtered_errors.append(error_message)
        
        if filtered_errors:
            raise Exception(f"GraphQL errors: {', '.join(filtered_errors)}")
    
    # Si aucune donnée n'est retournée, c'est un problème
    if not result.get("data") or not result["data"].get("demarche"):
        raise Exception(f"Aucune donnée de démarche trouvée pour le numéro {demarche_number}")
    
    demarche = result["data"]["demarche"]
    
    # Vérifier que activeRevision existe
    if not demarche.get("activeRevision"):
        raise Exception(f"Aucune révision active trouvée pour la démarche {demarche_number}")
    
    return demarche

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
    
    # Fonction récursive pour explorer les descripteurs
    def explore_descriptors(descriptors):
        for descriptor in descriptors:
            if descriptor.get("__typename") in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication"]:
                problematic_ids.add(descriptor.get("id"))
            
            # Explorer les descripteurs dans les blocs répétables
            if descriptor.get("__typename") == "RepetitionChampDescriptor" and "champDescriptors" in descriptor:
                explore_descriptors(descriptor["champDescriptors"])
    
    # Explorer les descripteurs de champs et d'annotations
    if demarche_schema.get("activeRevision"):
        if "champDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(demarche_schema["activeRevision"]["champDescriptors"])
        
        if "annotationDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(demarche_schema["activeRevision"]["annotationDescriptors"])
    
    return problematic_ids

def create_columns_from_schema(demarche_schema):
    """
    Crée les définitions de colonnes à partir du schéma de la démarche,
    en filtrant les champs problématiques (HeaderSection, Explication)
    
    Args:
        demarche_schema: Schéma de la démarche récupéré via get_demarche_schema
        
    Returns:
        dict: Définitions des colonnes pour toutes les tables
    """
    # IMPORT LOCAL pour éviter la dépendance circulaire
    from grist_processor_working_all import normalize_column_name, log, log_verbose, log_error
    
    # Récupérer les IDs des descripteurs problématiques à filtrer
    problematic_ids = get_problematic_descriptor_ids_from_schema(demarche_schema)
    log(f"Identificateurs de {len(problematic_ids)} descripteurs problématiques à filtrer")
    
    # Colonnes fixes pour la table des dossiers
    dossier_columns = [
        {"id": "dossier_id", "type": "Text"},
        {"id": "number", "type": "Int"},
        {"id": "state", "type": "Text"},
        {"id": "date_depot", "type": "DateTime"},
        {"id": "date_derniere_modification", "type": "DateTime"},
        {"id": "date_traitement", "type": "DateTime"},
        {"id": "demandeur_type", "type": "Text"},
        {"id": "demandeur_civilite", "type": "Text"},  # COLONNE AJOUTÉE
        {"id": "demandeur_nom", "type": "Text"},
        {"id": "demandeur_prenom", "type": "Text"},
        {"id": "demandeur_email", "type": "Text"},
        {"id": "demandeur_siret", "type": "Text"},
        {"id": "entreprise_raison_sociale", "type": "Text"},
        {"id": "usager_email", "type": "Text"},
        {"id": "groupe_instructeur_id", "type": "Text"},
        {"id": "groupe_instructeur_number", "type": "Int"},
        {"id": "groupe_instructeur_label", "type": "Text"},
        {"id": "supprime_par_usager", "type": "Bool"},
        {"id": "date_suppression", "type": "DateTime"},
        {"id": "prenom_mandataire", "type": "Text"},
        {"id": "nom_mandataire", "type": "Text"},
        {"id": "depose_par_un_tiers", "type": "Bool"},
        {"id": "label_names", "type": "Text"},
        {"id": "labels_json", "type": "Text"}
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
    
    # Colonnes de base pour la table des blocs répétables
    repetable_columns = [
        {"id": "dossier_number", "type": "Int"},
        {"id": "block_label", "type": "Text"},
        {"id": "block_row_index", "type": "Int"},
        {"id": "block_row_id", "type": "Text"},
        {"id": "field_name", "type": "Text"}  # Pour les champs cartographiques
    ]

    # Variables pour suivre la présence de blocs répétables et champs carto
    has_repetable_blocks = False
    has_carto_fields = False

    # Fonction pour déterminer le type de colonne Grist à partir du type de champ DS
    def determine_column_type(champ_type, typename=None):
        if champ_type in ["date", "datetime"] or typename in ["DateChamp", "DatetimeChamp"]:
            return "DateTime"
        elif champ_type == "decimal_number" or typename == "DecimalNumberChamp":
            return "Numeric"
        elif champ_type == "integer_number" or typename == "IntegerNumberChamp":
            return "Int"
        elif champ_type in ["checkbox", "yes_no"] or typename in ["CheckboxChamp", "YesNoChamp"]:
            return "Bool"
        else:
            return "Text"

    # Traiter les descripteurs de champs
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get("champDescriptors"):
        for descriptor in demarche_schema["activeRevision"]["champDescriptors"]:
            # Ignorer les descripteurs problématiques
            if descriptor["__typename"] in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication"] or \
               descriptor.get("id") in problematic_ids:
                continue
                
            champ_type = descriptor.get("type")
            champ_label = descriptor.get("label")
            
            # Détecter les blocs répétables
            if descriptor["__typename"] == "RepetitionChampDescriptor":
                has_repetable_blocks = True
                
                # Traiter les champs à l'intérieur des blocs répétables
                for inner_descriptor in descriptor.get("champDescriptors", []):
                    if inner_descriptor["__typename"] in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"] or \
                       inner_descriptor.get("type") in ["header_section", "explication"] or \
                       inner_descriptor.get("id") in problematic_ids:
                        continue
                    
                    inner_type = inner_descriptor.get("type")
                    inner_label = inner_descriptor.get("label")
                    
                    # Détecter les champs cartographiques
                    if inner_type == "carte":
                        has_carto_fields = True
                    
                    # Ajouter le champ normalisé à la table des blocs répétables
                    normalized_label = normalize_column_name(inner_label)
                    column_type = determine_column_type(inner_type, inner_descriptor.get("__typename"))
                    
                    if not any(col["id"] == normalized_label for col in repetable_columns):
                        repetable_columns.append({
                            "id": normalized_label,
                            "type": column_type
                        })
            
            # Détecter les champs cartographiques au niveau principal
            elif champ_type == "carte":
                has_carto_fields = True
            
            # Ajouter le champ normalisé à la table des champs
            normalized_label = normalize_column_name(champ_label)
            column_type = determine_column_type(champ_type, descriptor.get("__typename"))
            
            if not any(col["id"] == normalized_label for col in champ_columns):
                champ_columns.append({
                    "id": normalized_label,
                    "type": column_type
                })

    # Traiter les descripteurs d'annotations
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get("annotationDescriptors"):
        for descriptor in demarche_schema["activeRevision"]["annotationDescriptors"]:
            # Ignorer les types problématiques
            if descriptor["__typename"] in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication"] or \
               descriptor.get("id") in problematic_ids:
                continue
                
            champ_type = descriptor.get("type")
            champ_label = descriptor.get("label")
            
            # Pour les annotations, enlever le préfixe "annotation_" pour le nom de colonne
            if champ_label.startswith("annotation_"):
                annotation_label = normalize_column_name(champ_label[11:])  # enlever "annotation_"
            else:
                annotation_label = normalize_column_name(champ_label)
            
            column_type = determine_column_type(champ_type, descriptor.get("__typename"))
            
            if not any(col["id"] == annotation_label for col in annotation_columns):
                annotation_columns.append({
                    "id": annotation_label,
                    "type": column_type
                })
    
    # Ajouter les colonnes spécifiques pour les données géographiques
    if has_carto_fields:
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
            {"id": "geo_surface", "type": "Numeric"}
        ]
        
        # Ajouter aux blocs répétables s'ils existent
        if has_repetable_blocks:
            for geo_col in geo_columns:
                if not any(col["id"] == geo_col["id"] for col in repetable_columns):
                    repetable_columns.append(geo_col)

    # Préparer le résultat
    result = {
        "dossier": dossier_columns,
        "champs": champ_columns,
        "annotations": annotation_columns,
        "has_repetable_blocks": has_repetable_blocks,
        "has_carto_fields": has_carto_fields
    }
    
    if has_repetable_blocks:
        result["repetable_rows"] = repetable_columns
    
    return result, problematic_ids

def update_grist_tables_from_schema(client, demarche_number, column_types, problematic_ids=None):
    """
    Met à jour les tables Grist existantes en fonction du schéma actuel de la démarche,
    en ajoutant les nouvelles colonnes sans supprimer les données existantes.
    
    Args:
        client: Instance de GristClient
        demarche_number: Numéro de la démarche
        column_types: Types de colonnes calculés à partir du schéma
        problematic_ids: IDs des descripteurs problématiques à filtrer
        
    Returns:
        dict: IDs des tables mises à jour
    """
    # IMPORT LOCAL pour éviter la dépendance circulaire
    from grist_processor_working_all import log, log_verbose, log_error
    
    log(f"Mise à jour des tables Grist pour la démarche {demarche_number} d'après le schéma...")
    
    try:
        # Variables de suivi des indicateurs de présence
        has_repetable_blocks = column_types.get("has_repetable_blocks", False)
        has_carto_fields = column_types.get("has_carto_fields", False)
        
        # FILTRAGE EXPLICITE DES COLONNES PROBLÉMATIQUES
        # Filtrer les colonnes champs
        filtered_champ_columns = []
        for col in column_types.get("champs", []):
            filtered_champ_columns.append(col)
        column_types["champs"] = filtered_champ_columns
        
        # Filtrer les colonnes annotations
        filtered_annotation_columns = []
        for col in column_types.get("annotations", []):
            
            filtered_annotation_columns.append(col)
        column_types["annotations"] = filtered_annotation_columns
        
        # Définir les IDs de tables
        dossier_table_id = f"Demarche_{demarche_number}_dossiers"
        champ_table_id = f"Demarche_{demarche_number}_champs"
        annotation_table_id = f"Demarche_{demarche_number}_annotations"
        repetable_table_id = f"Demarche_{demarche_number}_repetable_rows" if has_repetable_blocks else None
        
        # Récupérer les tables existantes
        existing_tables_response = client.list_tables()
        existing_tables = existing_tables_response.get('tables', [])
        
        # Rechercher les tables existantes
        dossier_table = None
        champ_table = None
        annotation_table = None
        repetable_table = None
        
        for table in existing_tables:
            if isinstance(table, dict):
                table_id = table.get('id', '').lower()
                if table_id == dossier_table_id.lower():
                    dossier_table = table
                    dossier_table_id = table.get('id')
                    log(f"Table dossiers existante trouvée avec l'ID {dossier_table_id}")
                elif table_id == champ_table_id.lower():
                    champ_table = table
                    champ_table_id = table.get('id')
                    log(f"Table champs existante trouvée avec l'ID {champ_table_id}")
                elif table_id == annotation_table_id.lower():
                    annotation_table = table
                    annotation_table_id = table.get('id')
                    log(f"Table annotations existante trouvée avec l'ID {annotation_table_id}")
                elif repetable_table_id and table_id == repetable_table_id.lower():
                    repetable_table = table
                    repetable_table_id = table.get('id')
                    log(f"Table répétables existante trouvée avec l'ID {repetable_table_id}")
        
        # Fonction pour ajouter les colonnes manquantes à une table
        def add_missing_columns(table_id, all_columns):
            if not table_id:
                return
                
            # Récupérer les colonnes existantes
            url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
            response = requests.get(url, headers=client.headers)
            
            if response.status_code != 200:
                log_error(f"Erreur lors de la récupération des colonnes: {response.status_code}")
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
                    # Filtrage supplémentaire pour les colonnes problématiques
                    
                    missing_columns.append(col)
            
            # Ajouter les colonnes manquantes
            if missing_columns:
                log(f"Ajout de {len(missing_columns)} colonnes manquantes à la table {table_id}")
                add_url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
                add_columns_payload = {"columns": missing_columns}
                add_response = requests.post(add_url, headers=client.headers, json=add_columns_payload)
                
                if add_response.status_code != 200:
                    log_error(f"Erreur lors de l'ajout des colonnes: {add_response.text}")
                else:
                    log(f"Colonnes ajoutées avec succès à la table {table_id}")
        
        # Créer la table des dossiers si elle n'existe pas
        if not dossier_table:
            log(f"Création de la table {dossier_table_id}")
            dossier_table_result = client.create_table(dossier_table_id, column_types["dossier"])
            dossier_table = dossier_table_result['tables'][0]
            dossier_table_id = dossier_table.get('id')
        else:
            # Ajouter les colonnes manquantes à la table des dossiers
            add_missing_columns(dossier_table_id, column_types["dossier"])
        
        # Créer la table des champs si elle n'existe pas
        if not champ_table:
            log(f"Création de la table {champ_table_id}")
            champ_table_result = client.create_table(champ_table_id, column_types["champs"])
            champ_table = champ_table_result['tables'][0]
            champ_table_id = champ_table.get('id')
        else:
            # Ajouter les colonnes manquantes à la table des champs
            add_missing_columns(champ_table_id, column_types["champs"])
        
        # Créer la table des annotations si elle n'existe pas
        if not annotation_table:
            log(f"Création de la table {annotation_table_id}")
            annotation_table_result = client.create_table(annotation_table_id, column_types["annotations"])
            annotation_table = annotation_table_result['tables'][0]
            annotation_table_id = annotation_table.get('id')
        else:
            # Ajouter les colonnes manquantes à la table des annotations
            add_missing_columns(annotation_table_id, column_types["annotations"])
        
        # Gérer la table des blocs répétables
        if has_repetable_blocks and repetable_table_id and "repetable_rows" in column_types:
            if not repetable_table:
                log(f"Création de la table {repetable_table_id}")
                # Commencer avec les colonnes de base pour éviter des erreurs
                base_columns = [
                    {"id": "dossier_number", "type": "Int"},
                    {"id": "block_label", "type": "Text"},
                    {"id": "block_row_index", "type": "Int"},
                    {"id": "block_row_id", "type": "Text"}
                ]
                repetable_table_result = client.create_table(repetable_table_id, base_columns)
                repetable_table = repetable_table_result['tables'][0]
                repetable_table_id = repetable_table.get('id')
                
                # Ajouter les colonnes supplémentaires
                add_missing_columns(repetable_table_id, column_types["repetable_rows"])
            else:
                # Ajouter les colonnes manquantes à la table des blocs répétables
                add_missing_columns(repetable_table_id, column_types["repetable_rows"])
                
                # Ajouter des colonnes cartographiques si nécessaire
                if has_carto_fields:
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
                        {"id": "geo_surface", "type": "Numeric"}
                    ]
                    add_missing_columns(repetable_table_id, geo_columns)
        
        # Retourner les IDs des tables
        return {
            "dossier_table_id": dossier_table_id,
            "champ_table_id": champ_table_id,
            "annotation_table_id": annotation_table_id,
            "repetable_table_id": repetable_table_id
        }
        
    except Exception as e:
        log_error(f"Erreur lors de la mise à jour des tables Grist: {e}")
        import traceback
        traceback.print_exc()
        raise