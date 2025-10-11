"""
Module d'utilitaires pour récupérer et traiter le schéma complet d'une démarche
à partir de l'API Démarches Simplifiées, pour la création correcte de tables Grist.

VERSION AMÉLIORÉE - Compatible avec le code existant
Ajoute des fonctions optimisées tout en gardant les fonctions existantes
"""

import requests
import json
from typing import Dict, List, Any, Tuple, Optional, Set

# Importer les configurations nécessaires
from queries_config import API_TOKEN, API_URL

# ========================================
# FONCTIONS EXISTANTES - GARDÉES INTACTES
# ========================================

def get_demarche_schema(demarche_number):
    """
    Récupère le schéma complet d'une démarche avec tous ses descripteurs de champs,
    sans dépendre des dossiers existants.
    
    FONCTION EXISTANTE - GARDÉE POUR COMPATIBILITÉ
    
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
            if descriptor.get("__typename") in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor", "PieceJustificativeChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication", "piece_justificative"]:
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
    
    FONCTION EXISTANTE - GARDÉE POUR COMPATIBILITÉ
    
    Args:
        demarche_schema: Schéma de la démarche récupéré via get_demarche_schema
        
    Returns:
        dict: Définitions des colonnes pour toutes les tables
    """
    # IMPORT LOCAL pour éviter la dépendance circulaire
    from grist_processor_working_all import normalize_column_name, log, log_verbose, log_error
    
    # ✅ RÉCUPÉRER LES IDs DEPUIS LES MÉTADONNÉES SI DISPONIBLES
    if "metadata" in demarche_schema and "problematic_ids" in demarche_schema["metadata"]:
        problematic_ids = demarche_schema["metadata"]["problematic_ids"]
        log(f"Identificateurs de {len(problematic_ids)} descripteurs problématiques (depuis métadonnées)")
    else:
        # Fallback : essayer de les extraire du schéma (déjà nettoyé = 0)
        problematic_ids = get_problematic_descriptor_ids_from_schema(demarche_schema)
        log(f"Identificateurs de {len(problematic_ids)} descripteurs problématiques à filtrer")
    
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
            "repetition": "Text"
        }
        return type_mapping.get(champ_type, "Text")
    
    # Colonnes fixes pour la table des dossiers
    dossier_columns = [
        {"id": "dossier_id", "type": "Text"},
        {"id": "number", "type": "Int"},
        {"id": "state", "type": "Text"},
        {"id": "date_depot", "type": "DateTime"},
        {"id": "date_derniere_modification", "type": "DateTime"},
        {"id": "date_traitement", "type": "DateTime"},
        {"id": "demandeur_type", "type": "Text"},
        {"id": "demandeur_civilite", "type": "Text"},
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

    # Traiter les descripteurs de champs
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get("champDescriptors"):
        for descriptor in demarche_schema["activeRevision"]["champDescriptors"]:
            # Ignorer les types problématiques
            if descriptor["__typename"] in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor", "PieceJustificativeChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication", "piece_justificative"] or \
               descriptor.get("id") in problematic_ids:
                continue
                
            champ_type = descriptor.get("type")
            champ_label = descriptor.get("label")
            
            # Traitement spécial pour les blocs répétables
            if descriptor.get("__typename") == "RepetitionChampDescriptor" and "champDescriptors" in descriptor:
                has_repetable_blocks = True
                
                # Traiter les sous-champs du bloc répétable
                for inner_descriptor in descriptor["champDescriptors"]:
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
                # ✨ NOUVEAU : Colonnes RIB seulement pour les PJ avec "RIB" ou "IBAN" dans le label
                if descriptor.get("__typename") == "PieceJustificativeChampDescriptor":
                    if "rib" in champ_label.lower() or "iban" in champ_label.lower():
                        rib_suffixes = ["titulaire", "iban", "bic", "nom_de_la_banque"]
                        for suffix in rib_suffixes:
                            rib_col_id = f"{normalized_label}_{suffix}"
                            if not any(col["id"] == rib_col_id for col in champ_columns):
                                champ_columns.append({
                                    "id": rib_col_id,
                                    "type": "Text"
                                })
                # ✨ NOUVEAU : Colonnes Commune (code postal, département, code INSEE)
                if descriptor.get("__typename") == "CommuneChampDescriptor":
                    commune_suffixes = ["code_postal", "departement", "code_insee"]
                    for suffix in commune_suffixes:
                        commune_col_id = f"{normalized_label}_{suffix}"
                        if not any(col["id"] == commune_col_id for col in champ_columns):
                            champ_columns.append({
                                "id": commune_col_id,
                                "type": "Text"
                            })

    # Traiter les descripteurs d'annotations
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get("annotationDescriptors"):
        for descriptor in demarche_schema["activeRevision"]["annotationDescriptors"]:
            # Ignorer les types problématiques
            if descriptor["__typename"] in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor", "PieceJustificativeChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication", "piece_justificative"] or \
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
    
    FONCTION EXISTANTE - GARDÉE POUR COMPATIBILITÉ
    """
    # IMPORT LOCAL pour éviter la dépendance circulaire
    from grist_processor_working_all import log, log_verbose, log_error
    
    log(f"Mise à jour des tables Grist pour la démarche {demarche_number} d'après le schéma...")
    
    try:
        # Variables de suivi des indicateurs de présence
        has_repetable_blocks = column_types.get("has_repetable_blocks", False)
        has_carto_fields = column_types.get("has_carto_fields", False)
        
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
        
        # Créer ou mettre à jour les tables
        if not dossier_table:
            log(f"Création de la table {dossier_table_id}")
            dossier_table_result = client.create_table(dossier_table_id, column_types["dossier"])
            dossier_table = dossier_table_result['tables'][0]
            dossier_table_id = dossier_table.get('id')
        else:
            add_missing_columns(dossier_table_id, column_types["dossier"])
        
        if not champ_table:
            log(f"Création de la table {champ_table_id}")
            champ_table_result = client.create_table(champ_table_id, column_types["champs"])
            champ_table = champ_table_result['tables'][0]
            champ_table_id = champ_table.get('id')
        else:
            add_missing_columns(champ_table_id, column_types["champs"])
        
        if not annotation_table:
            log(f"Création de la table {annotation_table_id}")
            annotation_table_result = client.create_table(annotation_table_id, column_types["annotations"])
            annotation_table = annotation_table_result['tables'][0]
            annotation_table_id = annotation_table.get('id')
        else:
            add_missing_columns(annotation_table_id, column_types["annotations"])
        
        # Gérer la table des blocs répétables
        if has_repetable_blocks and repetable_table_id and "repetable_rows" in column_types:
            if not repetable_table:
                log(f"Création de la table {repetable_table_id}")
                base_columns = [
                    {"id": "dossier_number", "type": "Int"},
                    {"id": "block_label", "type": "Text"},
                    {"id": "block_row_index", "type": "Int"},
                    {"id": "block_row_id", "type": "Text"}
                ]
                repetable_table_result = client.create_table(repetable_table_id, base_columns)
                repetable_table = repetable_table_result['tables'][0]
                repetable_table_id = repetable_table.get('id')
                
                # Ajouter toutes les colonnes spécifiques
                add_missing_columns(repetable_table_id, column_types["repetable_rows"])
            else:
                add_missing_columns(repetable_table_id, column_types["repetable_rows"])
        
        # Retourner les IDs des tables
        result = {
            "dossiers": dossier_table_id,
            "champs": champ_table_id,
            "annotations": annotation_table_id
        }
        
        if has_repetable_blocks and repetable_table_id:
            result["repetable_rows"] = repetable_table_id
        
        log(f"Mise à jour des tables terminée avec succès")
        return result
        
    except Exception as e:
        log_error(f"Erreur lors de la mise à jour des tables: {str(e)}")
        raise

# ========================================
# NOUVELLES FONCTIONS OPTIMISÉES
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
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré")
    
    print(f"Récupération robuste du schéma pour la démarche {demarche_number}")
    
    # Requête GraphQL optimisée
    query = """
    query getRobustDemarcheSchema($demarcheNumber: Int!) {
        demarche(number: $demarcheNumber) {
            id
            number
            title
            activeRevision {
                id
                datePublication
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
                url
            }
        }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            API_URL,
            json={"query": query, "variables": {"demarcheNumber": demarche_number}},
            headers=headers,
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Gestion robuste des erreurs GraphQL
        if "errors" in result:
            non_critical_errors = []
            critical_errors = []
            
            for error in result["errors"]:
                error_message = error.get("message", "")
                if any(keyword in error_message.lower() for keyword in ["permission", "access", "unauthorized"]):
                    non_critical_errors.append(error_message)
                else:
                    critical_errors.append(error_message)
            
            if non_critical_errors:
                print(f"Erreurs d'accès (non-critiques): {len(non_critical_errors)}")
            
            if critical_errors:
                raise Exception(f"Erreurs critiques GraphQL: {'; '.join(critical_errors)}")
        
        # Validation de la réponse
        data = result.get("data", {})
        demarche = data.get("demarche")
        
        if not demarche:
            raise Exception(f"Démarche {demarche_number} non trouvée ou inaccessible")
        
        active_revision = demarche.get("activeRevision")
        if not active_revision:
            raise Exception(f"Aucune révision active pour la démarche {demarche_number}")
        
        # ✅ EXTRAIRE LES IDs PROBLÉMATIQUES AVANT LE NETTOYAGE
        problematic_ids = get_problematic_descriptor_ids_from_schema(demarche)
        
        # Nettoyage automatique des champs problématiques
        cleaned_schema = auto_clean_schema_descriptors(demarche)
        
        # Ajout de métadonnées
        from datetime import datetime
        cleaned_schema["metadata"] = {
            "revision_id": active_revision.get("id"),
            "date_publication": active_revision.get("datePublication"),
            "retrieved_at": datetime.now().isoformat(),
            "optimized": True,
            "problematic_ids": problematic_ids  # ✅ STOCKER LES IDs DANS LE SCHÉMA
        }
        
        print(f"Schéma récupéré:")
        print(f"Champs utiles: {len(cleaned_schema['activeRevision']['champDescriptors'])}")
        print(f"Annotations: {len(cleaned_schema['activeRevision']['annotationDescriptors'])}")
        print(f"Champs problématiques détectés: {len(problematic_ids)}")  # ✅ LOG
        
        return cleaned_schema
        
    except Exception as e:
        raise Exception(f"Erreur lors de la récupération du schéma: {e}")

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
            
            # Filtrer les types problématiques dont les pieces justificatives
            if typename in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor", "PieceJustificativeChampDescriptor"] or \
               descriptor_type in ["header_section", "explication", "piece_justificative"]:
                problematic_count += 1
                continue
            
            # Traitement spécial pour les blocs répétables
            if typename == "RepetitionChampDescriptor" and "champDescriptors" in descriptor:
                filtered_sub_descriptors = filter_descriptors(
                    descriptor["champDescriptors"], 
                    f"{context}_repetable"
                )
                descriptor["champDescriptors"] = filtered_sub_descriptors
            
            filtered.append(descriptor)
        
        if problematic_count > 0:
            print(f"{problematic_count} champs problématiques filtrés ({context})")
        
        return filtered
    
    # Nettoyer la démarche
    cleaned_demarche = demarche.copy()
    active_revision = cleaned_demarche["activeRevision"]
    
    # Filtrer les descripteurs de champs
    if "champDescriptors" in active_revision:
        active_revision["champDescriptors"] = filter_descriptors(
            active_revision["champDescriptors"], 
            "champs"
        )
    
    # Filtrer les descripteurs d'annotations
    if "annotationDescriptors" in active_revision:
        active_revision["annotationDescriptors"] = filter_descriptors(
            active_revision["annotationDescriptors"], 
            "annotations"
        )
    
    return cleaned_demarche

def detect_schema_changes(current_schema: Dict[str, Any], previous_schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Détecte les changements entre deux versions du schéma.
    Crucial pour optimiser les mises à jour quand une démarche est modifiée.
    """
    if not previous_schema:
        return {
            "is_first_run": True,
            "changes_detected": False,
            "requires_full_update": True
        }
    
    # Comparer les révisions
    current_revision = current_schema.get("metadata", {}).get("revision_id")
    previous_revision = previous_schema.get("metadata", {}).get("revision_id")
    
    if current_revision and previous_revision and current_revision == previous_revision:
        return {
            "is_first_run": False,
            "changes_detected": False,
            "revision_unchanged": True,
            "requires_full_update": False
        }
    
    # Analyser les changements détaillés
    def extract_field_signatures(descriptors):
        signatures = {}
        for desc in descriptors:
            field_id = desc.get("id")
            if field_id:
                signatures[field_id] = {
                    "type": desc.get("type"),
                    "label": desc.get("label"),
                    "required": desc.get("required"),
                    "typename": desc.get("__typename")
                }
        return signatures
    
    # Extraire les signatures
    current_champs = extract_field_signatures(
        current_schema.get("activeRevision", {}).get("champDescriptors", [])
    )
    previous_champs = extract_field_signatures(
        previous_schema.get("activeRevision", {}).get("champDescriptors", [])
    )
    
    current_annotations = extract_field_signatures(
        current_schema.get("activeRevision", {}).get("annotationDescriptors", [])
    )
    previous_annotations = extract_field_signatures(
        previous_schema.get("activeRevision", {}).get("annotationDescriptors", [])
    )
    
    # Comparer
    all_current = {**current_champs, **current_annotations}
    all_previous = {**previous_champs, **previous_annotations}
    
    new_fields = set(all_current.keys()) - set(all_previous.keys())
    removed_fields = set(all_previous.keys()) - set(all_current.keys())
    
    modified_fields = []
    for field_id in set(all_current.keys()) & set(all_previous.keys()):
        if all_current[field_id] != all_previous[field_id]:
            modified_fields.append(field_id)
    
    changes_detected = bool(new_fields or removed_fields or modified_fields)
    
    result = {
        "is_first_run": False,
        "changes_detected": changes_detected,
        "new_fields": list(new_fields),
        "removed_fields": list(removed_fields),
        "modified_fields": modified_fields,
        "requires_full_update": changes_detected,
        "revision_changed": current_revision != previous_revision
    }
    
    if changes_detected:
        print(f"Changements détectés:")
        if new_fields:
            print(f"Nouveaux champs: {len(new_fields)}")
        if removed_fields:
            print(f"Champs supprimés: {len(removed_fields)}")
        if modified_fields:
            print(f"Champs modifiés: {len(modified_fields)}")
    
    return result

def smart_schema_update(client, demarche_number: int, use_robust_version: bool = True):
    """
    Mise à jour intelligente qui choisit automatiquement la meilleure stratégie.
    
    Cette fonction:
    1. Utilise la version robuste ou classique selon le paramètre
    2. Détecte les changements de schéma
    3. Applique la stratégie de mise à jour optimale
    4. Préserve les données existantes
    
    Args:
        client: Instance GristClient
        demarche_number: Numéro de la démarche
        use_robust_version: True pour utiliser la version optimisée
        
    Returns:
        dict: Résultats de la mise à jour
    """
    # Import des fonctions de log
    try:
        from grist_processor_working_all import log, log_error
    except ImportError:
        def log(msg, level=1): print(msg)
        def log_error(msg): print(f"ERREUR: {msg}")
    
    try:
        log(f"Début de la mise à jour intelligente pour la démarche {demarche_number}")
        
        # Récupérer le schéma selon la version choisie
        if use_robust_version:
            log("Utilisation de la version robuste optimisée")
            schema = get_demarche_schema_robust(demarche_number)
        else:
            log("Utilisation de la version classique")
            schema = get_demarche_schema(demarche_number)
        
        # Créer les définitions de colonnes
        log("Création des définitions de colonnes...")
        column_types, problematic_ids = create_columns_from_schema(schema)
        
        # Utiliser la fonction de mise à jour existante
        log("Mise à jour des tables Grist...")
        table_ids = update_grist_tables_from_schema(client, demarche_number, column_types, problematic_ids)
        
        log("Mise à jour intelligente terminée avec succès")
        
        return {
            "success": True,
            "table_ids": table_ids,
            "schema_version": "robust" if use_robust_version else "classic",
            "column_counts": {
                "dossiers": len(column_types.get("dossier", [])),
                "champs": len(column_types.get("champs", [])),
                "annotations": len(column_types.get("annotations", [])),
                "repetable": len(column_types.get("repetable_rows", [])) if column_types.get("has_repetable_blocks") else 0
            },
            "features": {
                "has_repetable_blocks": column_types.get("has_repetable_blocks", False),
                "has_carto_fields": column_types.get("has_carto_fields", False)
            }
        }
        
    except Exception as e:
        log_error(f"Erreur lors de la mise à jour intelligente: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "schema_version": "robust" if use_robust_version else "classic"
        }

# ========================================
# FONCTIONS DE COMPATIBILITÉ ET MIGRATION
# ========================================

def migrate_to_robust_version(client, demarche_number: int):
    """
    Migre en douceur vers la version robuste en préservant les données existantes.
    """
    try:
        from grist_processor_working_all import log, log_error
    except ImportError:
        def log(msg, level=1): print(msg)
        def log_error(msg): print(f"ERREUR: {msg}")
    
    log("Migration vers la version robuste...")
    
    try:
        # Test de la version robuste
        robust_result = smart_schema_update(client, demarche_number, use_robust_version=True)
        
        if robust_result["success"]:
            log("Migration réussie vers la version robuste")
            log(f"Tables mises à jour: {list(robust_result['table_ids'].keys())}")
            log(f"Colonnes total: {sum(robust_result['column_counts'].values())}")
            return robust_result
        else:
            log("Échec de la version robuste, fallback vers la version classique")
            return smart_schema_update(client, demarche_number, use_robust_version=False)
            
    except Exception as e:
        log_error(f"Erreur durant la migration: {e}")
        log("Fallback vers la version classique...")
        return smart_schema_update(client, demarche_number, use_robust_version=False)

def validate_schema_compatibility(demarche_number: int) -> Dict[str, Any]:
    """
    Valide que les deux versions de schéma (classique et robuste) sont compatibles.
    Utile pour les tests et la validation.
    """
    results = {
        "demarche_number": demarche_number,
        "classic_version": None,
        "robust_version": None,
        "compatibility": None,
        "differences": []
    }
    
    try:
        # Test version classique
        try:
            classic_schema = get_demarche_schema(demarche_number)
            classic_columns, classic_problematic = create_columns_from_schema(classic_schema)
            results["classic_version"] = {
                "success": True,
                "column_counts": {k: len(v) for k, v in classic_columns.items() if isinstance(v, list)},
                "problematic_fields": len(classic_problematic)
            }
        except Exception as e:
            results["classic_version"] = {"success": False, "error": str(e)}
        
        # Test version robuste
        try:
            robust_schema = get_demarche_schema_robust(demarche_number)
            robust_columns, robust_problematic = create_columns_from_schema(robust_schema)
            results["robust_version"] = {
                "success": True,
                "column_counts": {k: len(v) for k, v in robust_columns.items() if isinstance(v, list)},
                "problematic_fields": len(robust_problematic),
                "metadata": robust_schema.get("metadata", {})
            }
        except Exception as e:
            results["robust_version"] = {"success": False, "error": str(e)}
        
        # Comparaison
        if results["classic_version"]["success"] and results["robust_version"]["success"]:
            classic_counts = results["classic_version"]["column_counts"]
            robust_counts = results["robust_version"]["column_counts"]
            
            # Vérifier la compatibilité
            differences = []
            for table_type in ["dossier", "champs", "annotations"]:
                classic_count = classic_counts.get(table_type, 0)
                robust_count = robust_counts.get(table_type, 0)
                
                if classic_count != robust_count:
                    differences.append(f"{table_type}: classique={classic_count}, robuste={robust_count}")
            
            results["compatibility"] = len(differences) == 0
            results["differences"] = differences
        
        return results
        
    except Exception as e:
        results["validation_error"] = str(e)
        return results

# ========================================
# POINT D'ENTRÉE POUR REMPLACEMENT PROGRESSIF
# ========================================

def get_demarche_schema_enhanced(demarche_number: int, prefer_robust: bool = True):
    """
    Point d'entrée principal pour remplacer progressivement get_demarche_schema.
    
    Cette fonction:
    - Essaie d'abord la version robuste si prefer_robust=True
    - Fallback automatique vers la version classique en cas d'échec
    - Interface identique à la fonction existante
    - Garantit la compatibilité avec le code existant
    
    Args:
        demarche_number: Numéro de la démarche
        prefer_robust: True pour préférer la version optimisée
        
    Returns:
        dict: Schéma de la démarche (format compatible)
    """
    if prefer_robust:
        try:
            return get_demarche_schema_robust(demarche_number)
        except Exception as e:
            print(f"Version robuste échouée: {e}")
            print("Fallback vers la version classique...")
            return get_demarche_schema(demarche_number)
    else:
        return get_demarche_schema(demarche_number)

# ========================================
# TESTS ET DIAGNOSTICS
# ========================================

def test_schema_functions(demarche_number: int = 107487):
    """
    Fonction de test pour valider toutes les fonctions du module.
    """
    print(f"Test des fonctions de schéma pour la démarche {demarche_number}")
    print("=" * 60)
    
    # Test de compatibilité
    print("Test de compatibilité des versions:")
    compatibility = validate_schema_compatibility(demarche_number)
    
    if compatibility.get("classic_version", {}).get("success"):
        print("Version classique: OK")
    else:
        print("Version classique: Échec")
    
    if compatibility.get("robust_version", {}).get("success"):
        print("Version robuste: OK")
    else:
        print("Version robuste: Échec")
    
    if compatibility.get("compatibility"):
        print("Compatibilité: Versions compatibles")
    else:
        print("Compatibilité: Différences détectées")
        for diff in compatibility.get("differences", []):
            print(f"   - {diff}")
    
    # Test de la fonction enhanced
    print("Test de la fonction enhanced:")
    try:
        enhanced_schema = get_demarche_schema_enhanced(demarche_number)
        print("Fonction enhanced: OK")
        print(f"Champs: {len(enhanced_schema.get('activeRevision', {}).get('champDescriptors', []))}")
        print(f"Annotations: {len(enhanced_schema.get('activeRevision', {}).get('annotationDescriptors', []))}")
    except Exception as e:
        print(f"Fonction enhanced: {e}")
    
    print("\n" + "=" * 60)
    print("Tests terminés")

if __name__ == "__main__":
    # Exécuter les tests si le fichier est lancé directement
    test_schema_functions()