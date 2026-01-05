"""
Module d'utilitaires pour récupérer et traiter le schéma complet d'une démarche
à partir de l'API Démarches Simplifiées, pour la création correcte de tables Grist.

VERSION AMÉLIORÉE - Compatible avec le code existant
Ajoute des fonctions optimisées tout en gardant les fonctions existantes
CORRECTION : Gestion des doublons de noms de colonnes
NOUVEAU : Tables séparées par bloc répétable
"""

import requests
import json
from typing import Dict, List, Any, Tuple, Optional, Set

# Importer les configurations nécessaires
from queries_config import API_TOKEN, API_URL

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
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            API_URL,
            json={"query": query, "variables": {"demarcheNumber": int(demarche_number)}},
            headers=headers,
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        if "errors" in result:
            print(f"⚠️  Erreur lors de la détection du type de demandeur pour la démarche {demarche_number}")
            return None
        
        dossiers = result.get("data", {}).get("demarche", {}).get("dossiers", {}).get("nodes", [])
        
        if dossiers and len(dossiers) > 0:
            demandeur = dossiers[0].get("demandeur", {})
            demandeur_type = demandeur.get("__typename")
            
            if demandeur_type in ["PersonnePhysique", "PersonneMorale", "PersonneMoraleIncomplete"]:
                # PersonneMoraleIncomplete est traité comme PersonneMorale
                if demandeur_type == "PersonneMoraleIncomplete":
                    return "PersonneMorale"
                return demandeur_type
        
        # Aucun dossier trouvé
        print(f"ℹ️  Aucun dossier trouvé pour la démarche {demarche_number}, type par défaut: PersonneMorale")
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
    else:  # PersonneMorale ou None (défaut)
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

# ========================================
# FONCTIONS EXISTANTES - CORRIGÉES
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

def create_columns_from_schema(demarche_schema, demarche_number=None):
    """
    Crée les définitions de colonnes à partir du schéma de la démarche,
    en filtrant les champs problématiques (HeaderSection, Explication)
    
     CORRIGÉ : 
    - Les PieceJustificativeChamp sont traités AVANT le filtrage
    - Gestion des doublons de noms de colonnes avec suffixes numériques
    - Tables séparées par bloc répétable
    
    FONCTION EXISTANTE - GARDÉE POUR COMPATIBILITÉ
    
    Args:
        demarche_schema: Schéma de la démarche récupéré via get_demarche_schema
        
    Returns:
        tuple: (dict définitions des colonnes, set IDs problématiques)
    """
    # IMPORT LOCAL pour éviter la dépendance circulaire
    from grist_processor_working_all import normalize_column_name, log, log_verbose, log_error
    #  NOUVEAU : Logging optionnel
    if demarche_number:
        log(f"Création des colonnes pour la démarche {demarche_number}")
    
    #  RÉCUPÉRER LES IDs DEPUIS LES MÉTADONNÉES SI DISPONIBLES
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
        {"id": "dossier_number", "type": "Int"},
        {"id": "state", "type": "Text"},
        {"id": "date_depot", "type": "DateTime"},
        {"id": "date_derniere_modification", "type": "DateTime"},
        {"id": "date_expiration", "type": "DateTime"},
        {"id": "date_traitement", "type": "DateTime"},
        {"id": "supprime_par_usager", "type": "Bool"},
        {"id": "date_suppression", "type": "DateTime"},
        {"id": "date_derniere_correction_en_attente", "type": "DateTime"},
        {"id": "date_derniere_modification_champs", "type": "DateTime"},
        {"id": "date_derniere_modification_annotations", "type": "DateTime"},
        {"id": "motivation", "type": "Text"},
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

    # Variables pour suivre la présence de blocs répétables et champs carto
    has_repetable_blocks = False
    repetable_blocks = {}  #  NOUVEAU : Dict au lieu d'une seule liste
    has_carto_fields = False

    # Traiter les descripteurs de champs
    if demarche_schema.get("activeRevision") and demarche_schema["activeRevision"].get("champDescriptors"):
        for descriptor in demarche_schema["activeRevision"]["champDescriptors"]:
            champ_type = descriptor.get("type")
            champ_label = descriptor.get("label")
            
            #  CORRECTION MAJEURE : Traiter les PieceJustificativeChamp AVANT le filtrage
            if descriptor.get("__typename") == "PieceJustificativeChampDescriptor":
                normalized_label = normalize_column_name(champ_label)
                
                # Détecter si c'est un champ RIB
                if "rib" in champ_label.lower() or "iban" in champ_label.lower():
                    rib_suffixes = ["titulaire", "iban", "bic", "nom_de_la_banque"]
                    for suffix in rib_suffixes:
                        rib_col_id = f"{normalized_label}_{suffix}"
                        if not any(col["id"] == rib_col_id for col in champ_columns):
                            champ_columns.append({
                                "id": rib_col_id,
                                "type": "Text"
                            })
                
                # Ajouter aussi la colonne principale pour le nom du fichier
                #  GESTION DES DOUBLONS
                base_label = normalized_label
                counter = 1
                while any(col["id"] == normalized_label for col in champ_columns):
                    normalized_label = f"{base_label}_{counter}"
                    counter += 1
                
                champ_columns.append({
                    "id": normalized_label,
                    "type": "Text"
                })
            
            # Maintenant filtrer les types problématiques
            if descriptor["__typename"] in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication"] or \
               descriptor.get("id") in problematic_ids:
                continue
            
            # Traitement spécial pour les blocs répétables
            if descriptor.get("__typename") == "RepetitionChampDescriptor" and "champDescriptors" in descriptor:
                has_repetable_blocks = True

                #  NOUVEAU : Créer une entrée par bloc
                block_label = descriptor.get("label")
                normalized_block_label = normalize_column_name(block_label)
                
                # Colonnes de base pour ce bloc
                block_columns = [
                    {"id": "dossier_number", "type": "Int"},
                    {"id": "block_row_index", "type": "Int"},
                    {"id": "block_row_id", "type": "Text"},
                ]
                
                block_has_carto = False  #  Pour suivre si CE bloc a des champs carto
                
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
                    column_type = determine_column_type(inner_type, inner_descriptor.get("__typename"))
                    
                    #  GESTION DES DOUBLONS pour ce bloc (utiliser block_columns)
                    base_label = normalized_label
                    counter = 1
                    while any(col["id"] == normalized_label for col in block_columns):
                        normalized_label = f"{base_label}_{counter}"
                        counter += 1
                    
                    block_columns.append({
                        "id": normalized_label,
                        "type": column_type
                    })
                
                #  Ajouter les colonnes géographiques si nécessaire pour CE bloc
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
                        {"id": "geo_surface", "type": "Numeric"}
                    ]
                    
                    for geo_col in geo_columns:
                        if not any(col["id"] == geo_col["id"] for col in block_columns):
                            block_columns.append(geo_col)
                
                #  STOCKER dans le dict avec le label normalisé comme clé
                repetable_blocks[normalized_block_label] = {
                    "original_label": block_label,
                    "columns": block_columns
                }
            
            # Détecter les champs cartographiques au niveau principal
            elif champ_type == "carte":
                has_carto_fields = True
            
            # Ajouter le champ normalisé à la table des champs
            # MAIS PAS pour les PieceJustificativeChamp car déjà traités ci-dessus
            if descriptor.get("__typename") != "PieceJustificativeChampDescriptor":
                normalized_label = normalize_column_name(champ_label)
                column_type = determine_column_type(champ_type, descriptor.get("__typename"))
                
                #  GESTION DES DOUBLONS
                base_label = normalized_label
                counter = 1
                while any(col["id"] == normalized_label for col in champ_columns):
                    normalized_label = f"{base_label}_{counter}"
                    counter += 1
                
                champ_columns.append({
                    "id": normalized_label,
                    "type": column_type
                })
            
            # ✨ Colonnes Commune
            if descriptor.get("__typename") == "CommuneChampDescriptor":
                normalized_label = normalize_column_name(champ_label)
                commune_suffixes = ["nom", "code_postal", "departement", "code_insee", "code_departement"]
                for suffix in commune_suffixes:
                    commune_col_id = f"{normalized_label}_{suffix}"
                    
                    #  GESTION DES DOUBLONS pour colonnes communes
                    base_col = commune_col_id
                    counter = 1
                    while any(col["id"] == commune_col_id for col in champ_columns):
                        commune_col_id = f"{base_col}_{counter}"
                        counter += 1
                    
                    champ_columns.append({
                        "id": commune_col_id,
                        "type": "Text"
                    })
            
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
                    
                    champ_columns.append({
                        "id": pays_col_id,
                        "type": "Text"
                    })
            
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
                    
                    champ_columns.append({
                        "id": region_col_id,
                        "type": "Text"
                    })

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
                    
                    champ_columns.append({
                        "id": dept_col_id,
                        "type": "Text"
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
            
            #  GESTION DES DOUBLONS pour annotations
            base_label = annotation_label
            counter = 1
            while any(col["id"] == annotation_label for col in annotation_columns):
                annotation_label = f"{base_label}_{counter}"
                counter += 1
            
            annotation_columns.append({
                "id": annotation_label,
                "type": column_type
            })

    # Préparer le résultat
    result = {
        "dossier": dossier_columns,
        "champs": champ_columns,
        "annotations": annotation_columns,
        "has_repetable_blocks": has_repetable_blocks,
        "has_carto_fields": has_carto_fields
    }
    
    if has_repetable_blocks:
        result["repetable_blocks"] = repetable_blocks  #  NOUVEAU : dict au lieu d'une liste
    
    return result, problematic_ids

def update_grist_tables_from_schema(client, demarche_number, column_types, problematic_ids=None):
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
    from grist_processor_working_all import log, log_error
    
    try:
        log(f"Mise à jour des tables Grist pour la démarche {demarche_number} d'après le schéma...")

        # Noms des tables
        dossier_table_id = f"Demarche_{demarche_number}_dossiers"
        champ_table_id = f"Demarche_{demarche_number}_champs"
        annotation_table_id = f"Demarche_{demarche_number}_annotations"
        has_repetable_blocks = column_types.get("has_repetable_blocks", False)
        
        # Récupérer toutes les tables existantes
        tables = client.list_tables()

        #  CORRECTION : Extraire la liste des tables
        if isinstance(tables, dict) and 'tables' in tables:
            tables = tables['tables']
        
        # Trouver les tables existantes
        dossier_table = None
        champ_table = None
        annotation_table = None
        
        for table in tables:
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
                add_payload = {"columns": missing_columns}
                add_response = requests.post(url, headers=client.headers, json=add_payload)
                
                if add_response.status_code == 200:
                    log(f"Colonnes ajoutées avec succès")
                else:
                    log_error(f"Erreur lors de l'ajout des colonnes: {add_response.status_code}")
        
        # Créer ou mettre à jour la table des dossiers
        if not dossier_table:
            log(f"Création de la table {dossier_table_id}")
            dossier_table_result = client.create_table(dossier_table_id, column_types["dossier"])
            dossier_table = dossier_table_result['tables'][0]
            dossier_table_id = dossier_table.get('id')
        else:
            add_missing_columns(dossier_table_id, column_types["dossier"])
        
        # Créer ou mettre à jour la table des champs
        if not champ_table:
            log(f"Création de la table {champ_table_id}")
            base_columns = [
                {"id": "dossier_number", "type": "Int"},
                {"id": "champ_id", "type": "Text"}
            ]
            champ_table_result = client.create_table(champ_table_id, base_columns)
            champ_table = champ_table_result['tables'][0]
            champ_table_id = champ_table.get('id')
            
            # Ajouter toutes les colonnes spécifiques
            add_missing_columns(champ_table_id, column_types["champs"])
        else:
            add_missing_columns(champ_table_id, column_types["champs"])
        
        # Créer ou mettre à jour la table des annotations
        if not annotation_table:
            # ✅ NOUVELLE CONDITION : Ne créer que s'il y a des annotations
            if len(column_types["annotations"]) > 1:  # > 1 car il y a toujours dossier_number
                log(f"Création de la table {annotation_table_id}")
                base_columns = [{"id": "dossier_number", "type": "Int"}]
                annotation_table_result = client.create_table(annotation_table_id, base_columns)
                annotation_table = annotation_table_result['tables'][0]
                annotation_table_id = annotation_table.get('id')
                
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
                    if table.get('id', '').lower() == table_id.lower():
                        existing_table = table
                        table_id = table.get('id')
                        log(f"Table répétable '{block_info['original_label']}' existante trouvée: {table_id}")
                        break
                
                if not existing_table:
                    log(f"Création de la table {table_id} pour le bloc '{block_info['original_label']}'")
                    table_result = client.create_table(table_id, block_info["columns"])
                    table_id = table_result['tables'][0].get('id')
                else:
                    # Ajouter les colonnes manquantes
                    add_missing_columns(table_id, block_info["columns"])

                repetable_table_ids[block_key] = table_id
        
        #  NOUVEAU : Créer ou mettre à jour la table demandeurs
        log(f"Création/mise à jour de la table demandeurs...")
        demandeurs_table_id = f"Demarche_{demarche_number}_demandeurs"
        
        # Détecter le type et créer les colonnes
        demandeurs_columns, demandeur_type = create_demandeurs_columns(demarche_number)
        log(f"Type de demandeur: {demandeur_type} - {len(demandeurs_columns)} colonnes")
        
        # Chercher si la table existe
        demandeurs_table = None
        for table in tables:
            if table.get('id', '').lower() == demandeurs_table_id.lower():
                demandeurs_table = table
                demandeurs_table_id = table.get('id')
                log(f"Table demandeurs existante trouvée: {demandeurs_table_id}")
                break
        
        # Créer ou mettre à jour
        if not demandeurs_table:
            log(f"Création de la table {demandeurs_table_id} (type: {demandeur_type})")
            demandeurs_table_result = client.create_table(demandeurs_table_id, demandeurs_columns)
            demandeurs_table = demandeurs_table_result['tables'][0]
            demandeurs_table_id = demandeurs_table.get('id')
        else:
            log(f"Mise à jour des colonnes de la table demandeurs")
            add_missing_columns(demandeurs_table_id, demandeurs_columns)

        # Créer/mettre à jour la table instructeurs
        log(f"Création/mise à jour de la table instructeurs...")
        instructeurs_table_id = f"Demarche_{demarche_number}_instructeurs"
        instructeurs_table = next((t for t in tables if t.get('id') == instructeurs_table_id), None)

        if not instructeurs_table:
            log(f"Création de la table {instructeurs_table_id}")
            instructeurs_columns = create_instructeurs_columns()
            instructeurs_table_result = client.create_table(instructeurs_table_id, instructeurs_columns)
            instructeurs_table = instructeurs_table_result['tables'][0]
            instructeurs_table_id = instructeurs_table.get('id')
        else:
            log(f"Mise à jour des colonnes de la table instructeurs")
            instructeurs_columns = create_instructeurs_columns()
            add_missing_columns(instructeurs_table_id, instructeurs_columns)

        # Retourner les IDs des tables
        result = {
            "dossiers": dossier_table_id,
            "champs": champ_table_id,
            "demandeurs": demandeurs_table_id,
            "demandeur_type": demandeur_type,
            "instructeurs": instructeurs_table_id
        }

        # ✅ Ajouter annotations seulement si la table existe
        if annotation_table_id:
            result["annotations"] = annotation_table_id

        # Ajouter les blocs répétables si présents
        if has_repetable_blocks:
            result["repetable_blocks"] = repetable_table_ids

        log(f"Mise à jour des tables terminée avec succès")
        return result
        
    except Exception as e:
        log_error(f"Erreur lors de la mise à jour des tables: {str(e)}")
        raise

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
        # Utiliser la fonction de base
        demarche = get_demarche_schema(demarche_number)
        
        active_revision = demarche.get("activeRevision")
        if not active_revision:
            raise Exception(f"Aucune révision active pour la démarche {demarche_number}")
        
        #  EXTRAIRE LES IDs PROBLÉMATIQUES AVANT LE NETTOYAGE
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
            "problematic_ids": problematic_ids  #  STOCKER LES IDs DANS LE SCHÉMA
        }
        
        print(f"Schéma récupéré:")
        print(f"Champs utiles: {len(cleaned_schema['activeRevision']['champDescriptors'])}")
        print(f"Annotations: {len(cleaned_schema['activeRevision']['annotationDescriptors'])}")
        print(f"Champs problématiques détectés: {len(problematic_ids)}")  #  LOG
        
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
            
            # Filtrer les types problématiques (SANS piece_justificative)
            if typename in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"] or \
               descriptor_type in ["header_section", "explication"]:
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