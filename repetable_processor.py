"""
Module spécialisé pour le traitement des blocs répétables dans les formulaires Démarches Simplifiées.
Ce module extrait, transforme et stocke les données des blocs répétables dans Grist.
"""

import json
import requests
import traceback
from typing import Dict, List, Any, Tuple, Optional

# Importer les fonctions de logging depuis le module principal
try:
    from grist_processor_working_all import log, log_verbose, log_error
except ImportError:
    # Définitions de secours en cas d'échec de l'import
    def log(message, level=1):
        print(message)
        
    def log_verbose(message):
        print(message)
        
    def log_error(message):
        print(f"ERREUR: {message}")

def should_skip_field(field, problematic_ids=None):
    """
    Détermine si un champ doit être ignoré.
    Utilise la même logique que dossier_to_flat_data pour la cohérence.
    
    Args:
        field: Le champ à vérifier
        problematic_ids: Set des IDs problématiques
        
    Returns:
        bool: True si le champ doit être ignoré
    """
    # Ignorer par type (même logique que dossier_to_flat_data)
    if field.get("__typename") in ["HeaderSectionChamp", "ExplicationChamp"]:
        return True
    
    # Ignorer par ID problématique
    if problematic_ids and field.get("id") in problematic_ids:
        return True
    
    # Ignorer par type de champ (au cas où)
    if field.get("type") in ["header_section", "explication"]:
        return True
    
    return False


def normalize_key(key_string):
    """
    Normalise une clé en supprimant les caractères spéciaux et en convertissant en minuscules
    pour garantir une correspondance cohérente.
    
    Args:
        key_string: La chaîne à normaliser
        
    Returns:
        str: La chaîne normalisée, utilisable comme clé
    """
    import re
    
    # Convertir en chaîne si ce n'est pas déjà le cas
    if not isinstance(key_string, str):
        key_string = str(key_string)
    
    # Remplacer les caractères problématiques par des underscores
    # et conserver uniquement les caractères alphanumériques et les underscores
    normalized = re.sub(r'[^\w_]', '_', key_string)
    
    # Convertir en minuscules et supprimer les underscores multiples consécutifs
    normalized = re.sub(r'_+', '_', normalized.lower())
    
    return normalized

def normalize_column_name(name, max_length=40):
    """
    Normalise un nom de colonne pour Grist :
    - Supprime les accents et les caractères spéciaux
    - Remplace les espaces par des underscores
    - Tronque la longueur si nécessaire
    - S'assure que le nom commence par une lettre
    
    Args:
        name: Nom original de la colonne
        max_length: Longueur maximale autorisée
        
    Returns:
        str: Nom normalisé pour Grist
    """
    if not name:
        return "column"
    
    # Importer ici pour éviter les dépendances circulaires
    import unicodedata
    import re
    
    # Supprimer les accents
    name = unicodedata.normalize('NFKD', name)
    name = ''.join([c for c in name if not unicodedata.combining(c)])
    
    # Supprimer les caractères spéciaux et espaces multiples
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', '_', name)
    
    # S'assurer que le nom commence par une lettre
    if not name[0].isalpha():
        name = "c_" + name
    
    # Tronquer si nécessaire
    if len(name) > max_length:
        name = name[:max_length]
    
    return name.lower()

def format_value_for_grist(value, value_type):
    """
    Formate une valeur selon le type de colonne Grist.
    
    Args:
        value: Valeur à formater
        value_type: Type de colonne Grist ('Text', 'Int', 'Numeric', 'Bool', 'DateTime')
        
    Returns:
        Valeur formatée selon le type spécifié
    """
    if value is None:
        return None
    
    if value_type == "DateTime":
        if isinstance(value, str):
            if value:
                # Importer datetime seulement si nécessaire
                from datetime import datetime
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        dt = datetime.strptime(value, fmt)
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        continue
            return value
        return value
    
    if value_type == "Text":
        if isinstance(value, str) and len(value) > 1000:
            return value[:1000] + "..."
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

def extract_field_value(champ: Dict[str, Any]) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """
    Extrait la valeur d'un champ selon son type.
    Gère correctement le cas des valeurs None.
    
    Args:
        champ: Dictionnaire contenant les données du champ
        
    Returns:
        tuple: (valeur texte, valeur JSON)
    """
    # Utiliser la fonction commune de filtrage
    if should_skip_field(champ):
        return None, None
    
    typename = champ["__typename"]
    value = None
    json_value = None
    
    if typename == "DateChamp":
        value = champ.get("date")
        
    elif typename == "DatetimeChamp":
        value = champ.get("datetime")
        
    elif typename == "CheckboxChamp":
        value = champ.get("checked")
        
    elif typename == "YesNoChamp":
        value = champ.get("selected")
        
    elif typename == "DecimalNumberChamp":
        value = champ.get("decimalNumber")
        
    elif typename == "IntegerNumberChamp":
        value = champ.get("integerNumber")
        
    elif typename == "CiviliteChamp":
        value = champ.get("civilite")
        
    elif typename == "LinkedDropDownListChamp":
        primary = champ.get('primaryValue', '')
        secondary = champ.get('secondaryValue', '')
        value = f"{primary} - {secondary}" if primary and secondary else primary or secondary
        json_value = {"primaryValue": primary, "secondaryValue": secondary}
        
    elif typename == "MultipleDropDownListChamp":
        values_list = champ.get("values", [])
        value = ", ".join(values_list) if values_list else None
        json_value = values_list
        
    elif typename == "PieceJustificativeChamp":
        files = champ.get("files", [])
        value = ", ".join([f.get('filename', '') for f in files if f.get('filename')]) if files else None
        json_value = files
        
    elif typename == "AddressChamp" and champ.get("address"):
        address = champ.get("address", {})
        value = f"{address.get('streetAddress', '')}, {address.get('postalCode', '')} {address.get('cityName', '')}"
        json_value = address
        
        # Ajouter les informations de commune et département si disponibles
        commune = champ.get("commune")
        departement = champ.get("departement")
        if commune or departement:
            address_extra = {}
            if commune:
                address_extra["commune"] = commune
            if departement:
                address_extra["departement"] = departement
            json_value = {"address": address, **address_extra}
        
    elif typename == "SiretChamp" and champ.get("etablissement"):
        etablissement = champ.get("etablissement", {})
        siret = etablissement.get("siret", "")
        raison_sociale = etablissement.get("entreprise", {}).get("raisonSociale", "")
        value = f"{siret} - {raison_sociale}" if siret and raison_sociale else siret or raison_sociale
        json_value = etablissement
        
    elif typename == "CarteChamp":
        geo_areas = champ.get("geoAreas", [])
        if geo_areas:
            # Filtrer les descriptions None et les remplacer par "Sans description"
            descriptions = [area.get("description", "Sans description") or "Sans description" for area in geo_areas]
            value = "; ".join(descriptions)
            json_value = geo_areas
        else:
            value = "Aucune zone géographique définie"
            
    elif typename == "DossierLinkChamp" and champ.get("dossier"):
        linked_dossier = champ.get("dossier", {})
        dossier_number = linked_dossier.get("number", "")
        dossier_state = linked_dossier.get("state", "")
        value = f"Dossier #{dossier_number} ({dossier_state})" if dossier_number else "Aucun dossier lié"
        json_value = linked_dossier
        
    elif typename == "TextChamp":
        value = champ.get("stringValue", "")
        
    elif typename == "CommuneChamp":
        commune = champ.get("commune", {})
        commune_name = commune.get("name", "")
        commune_code = commune.get("code", "")
        departement = champ.get("departement", {})
        dept_name = departement.get("name", "") if departement else ""
        
        value = f"{commune_name} ({commune_code})" if commune_name else ""
        if dept_name:
            value = f"{value}, {dept_name}" if value else dept_name
            
        json_value = {"commune": commune}
        if departement:
            json_value["departement"] = departement
    
    elif typename == "RegionChamp" and champ.get("region"):
        region = champ.get("region", {})
        name = region.get("name", "")
        code = region.get("code", "")
        value = f"{name} ({code})" if name and code else name or code
        json_value = region
    
    elif typename == "DepartementChamp" and champ.get("departement"):
        departement = champ.get("departement", {})
        name = departement.get("name", "")
        code = departement.get("code", "")
        value = f"{name} ({code})" if name and code else name or code
        json_value = departement
    
    elif typename == "EpciChamp" and champ.get("epci"):
        epci = champ.get("epci", {})
        name = epci.get("name", "")
        code = epci.get("code", "")
        value = f"{name} ({code})" if name and code else name or code
        departement = champ.get("departement")
        if departement:
            dept_name = departement.get("name", "")
            value = f"{value}, {dept_name}" if value and dept_name else value or dept_name
        json_value = {"epci": epci}
        if departement:
            json_value["departement"] = departement
            
    elif typename == "RNFChamp" and champ.get("rnf"):
        rnf = champ.get("rnf", {})
        title = rnf.get("title", "")
        rnf_address = rnf.get("address", {})
        city_name = rnf_address.get("cityName", "")
        postal_code = rnf_address.get("postalCode", "")
        
        if title:
            if city_name and postal_code:
                value = f"{title} - {city_name} ({postal_code})"
            else:
                value = title
        else:
            value = ""
            
        json_value = {"rnf": rnf}
        if champ.get("commune"):
            json_value["commune"] = champ.get("commune")
        if champ.get("departement"):
            json_value["departement"] = champ.get("departement")
            
    elif typename == "EngagementJuridiqueChamp" and champ.get("engagementJuridique"):
        engagement = champ.get("engagementJuridique", {})
        montant_engage = engagement.get("montantEngage")
        montant_paye = engagement.get("montantPaye")
        
        value = ""
        if montant_engage is not None:
            value = f"Montant engagé: {montant_engage}"
        if montant_paye is not None:
            value = f"{value}, Montant payé: {montant_paye}" if value else f"Montant payé: {montant_paye}"
            
        json_value = engagement
        
    else:
        # Pour les autres types, utiliser la valeur textuelle
        value = champ.get("stringValue")
    
    # Pour la valeur de retour, s'assurer qu'elle n'est pas None pour les chaînes
    if value is None and isinstance(value, str):
        value = ""
        
    return value, json_value

def extract_geo_data(geo_area: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait les données géographiques d'une zone.
    Version améliorée pour extraire correctement les coordonnées WKT.
    
    Args:
        geo_area: Dictionnaire contenant les données d'une zone géographique
        
    Returns:
        dict: Données géographiques extraites
    """
    geo_data = {
        "geo_id": geo_area.get("id"),
        "geo_source": geo_area.get("source"),
        "geo_description": geo_area.get("description", "Sans description"),
        "geo_commune": geo_area.get("commune"),
        "geo_numero": geo_area.get("numero"),
        "geo_section": geo_area.get("section"),
        "geo_prefixe": geo_area.get("prefixe"),
        "geo_surface": geo_area.get("surface"),
    }
    
    # Traiter les données géométriques
    geometry = geo_area.get("geometry", {})
    geo_type = geometry.get("type")
    coordinates = geometry.get("coordinates")
    
    geo_data["geo_type"] = geo_type
    
    # Stocker les coordonnées brutes sous forme de chaîne JSON
    if coordinates:
        try:
            geo_data["geo_coordinates"] = json.dumps(coordinates)
        except (TypeError, ValueError):
            geo_data["geo_coordinates"] = str(coordinates)
    
    # Créer la géométrie WKT (Well-Known Text) si possible
    if geo_type and coordinates:
        wkt = None
        try:
            if geo_type == "Point":
                # Point: POINT(X Y)
                wkt = f"POINT({coordinates[0]} {coordinates[1]})"
            
            elif geo_type == "LineString":
                # LineString: LINESTRING(X1 Y1, X2 Y2, ...)
                points = ", ".join([f"{p[0]} {p[1]}" for p in coordinates])
                wkt = f"LINESTRING({points})"
            
            elif geo_type == "Polygon":
                # Polygon: POLYGON((X1 Y1, X2 Y2, ..., X1 Y1), (hole1), (hole2), ...)
                rings = []
                for ring in coordinates:
                    # S'assurer que le premier et le dernier point sont identiques (fermer l'anneau)
                    if ring[0] != ring[-1]:
                        ring = ring + [ring[0]]
                    
                    points = ", ".join([f"{p[0]} {p[1]}" for p in ring])
                    rings.append(f"({points})")
                
                wkt = f"POLYGON({', '.join(rings)})"
            
            elif geo_type == "MultiPoint":
                # MultiPoint: MULTIPOINT((X1 Y1), (X2 Y2), ...)
                points = ", ".join([f"({p[0]} {p[1]})" for p in coordinates])
                wkt = f"MULTIPOINT({points})"
            
            elif geo_type == "MultiLineString":
                # MultiLineString: MULTILINESTRING((X1 Y1, X2 Y2, ...), (X1 Y1, X2 Y2, ...), ...)
                linestrings = []
                for line in coordinates:
                    points = ", ".join([f"{p[0]} {p[1]}" for p in line])
                    linestrings.append(f"({points})")
                
                wkt = f"MULTILINESTRING({', '.join(linestrings)})"
            
            elif geo_type == "MultiPolygon":
                # MultiPolygon: MULTIPOLYGON(((X1 Y1, X2 Y2, ..., X1 Y1), (hole1), ...), (...), ...)
                polygons = []
                for polygon in coordinates:
                    rings = []
                    for ring in polygon:
                        # S'assurer que le premier et le dernier point sont identiques
                        if ring[0] != ring[-1]:
                            ring = ring + [ring[0]]
                        
                        points = ", ".join([f"{p[0]} {p[1]}" for p in ring])
                        rings.append(f"({points})")
                    
                    polygons.append(f"({', '.join(rings)})")
                
                wkt = f"MULTIPOLYGON({', '.join(polygons)})"
            
            elif geo_type == "GeometryCollection":
                # Non pris en charge pour l'instant
                wkt = None
                print(f"  Type de géométrie non pris en charge: {geo_type}")
            
            geo_data["geo_wkt"] = wkt
        
        except Exception as e:
            print(f"  Erreur lors de la création du WKT pour le type {geo_type}: {str(e)}")
            geo_data["geo_wkt"] = None
    
    return geo_data

def get_existing_repetable_rows_improved_no_filter(client, table_id, dossier_number=None):
    """
    Version améliorée qui évite d'utiliser le filtre côté serveur,
    récupère toutes les lignes et filtre côté client.
    """
    if not client.doc_id:
        raise ValueError("Document ID is required")

    # Récupérer tous les enregistrements sans filtre
    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
    log_verbose(f"Récupération de tous les enregistrements de la table {table_id}")
    
    response = requests.get(url, headers=client.headers)
    
    if response.status_code != 200:
        log_error(f"Erreur lors de la récupération des enregistrements: {response.status_code} - {response.text}")
        return {}
        
    data = response.json()
    
    # Dictionnaire pour stocker les enregistrements par différentes clés composites
    records_dict = {}
    
    if 'records' in data and isinstance(data['records'], list):
        for record in data['records']:
            if 'id' in record and 'fields' in record:
                fields = record['fields']
                record_id = record['id']
                
                # Vérifier que les champs requis sont présents
                if all(key in fields for key in ['dossier_number', 'block_label']):
                    # Filtrer par dossier si un dossier_number est spécifié
                    if dossier_number is not None and str(fields['dossier_number']) != str(dossier_number):
                        continue
                        
                    current_dossier_number = str(fields['dossier_number'])
                    block_label = fields['block_label']
                    
                    # Utiliser block_row_id s'il est disponible, sinon block_row_index
                    if 'block_row_id' in fields and fields['block_row_id']:
                        row_identifier = fields['block_row_id']
                    elif 'block_row_index' in fields:
                        row_identifier = f"index_{fields['block_row_index']}"
                    else:
                        # Sans identifiant de ligne, passer à l'enregistrement suivant
                        continue
                    
                    # Créer plusieurs formats de clés composites pour augmenter les chances de correspondance
                    
                    # Format 1: dossier_number_block_label_row_id
                    key1 = f"{current_dossier_number}_{block_label}_{row_identifier}"
                    records_dict[key1] = record_id
                    
                    # Format 2: dossier_number_block_label_row_id (tout en minuscules)
                    key2 = key1.lower()
                    records_dict[key2] = record_id
                    
                    # Format 3: dossier_number_block_label_index (si block_row_index est disponible)
                    if 'block_row_index' in fields:
                        key3 = f"{current_dossier_number}_{block_label}_index_{fields['block_row_index']}"
                        records_dict[key3] = record_id
                    
                    # Format 4: avec espaces remplacés par des underscores dans block_label
                    clean_label = block_label.replace(' ', '_')
                    key4 = f"{current_dossier_number}_{clean_label}_{row_identifier}"
                    records_dict[key4] = record_id
                    
                    # Format 5: avec tous les caractères non alphanumériques supprimés
                    import re
                    clean_label = re.sub(r'[^\w]', '', block_label)
                    key5 = f"{current_dossier_number}_{clean_label}_{row_identifier}"
                    records_dict[key5] = record_id
                    
                    # Enregistrer le record_id par l'ID seul pour vérification directe
                    if 'block_row_id' in fields and fields['block_row_id']:
                        records_dict[fields['block_row_id']] = record_id
                        
                    # Gestion spéciale des géométries
                    if 'field_name' in fields and 'geo_id' in fields and fields['geo_id']:
                        field_name = fields['field_name']
                        geo_id = fields['geo_id']
                        
                        # Clé pour les géométries
                        geo_key = f"{current_dossier_number}_{block_label}_{field_name}_{geo_id}"
                        records_dict[geo_key.lower()] = record_id
                        
                        # Autre format avec position de la géométrie si disponible
                        if row_identifier and '_geo' in row_identifier:
                            # Extraire l'index de la géométrie depuis row_identifier
                            match = re.search(r'_geo(\d+)$', row_identifier)
                            if match:
                                geo_index = match.group(1)
                                base_id = row_identifier.split('_geo')[0]
                                geo_key_alt = f"{current_dossier_number}_{block_label}_{base_id}_geo{geo_index}"
                                records_dict[geo_key_alt.lower()] = record_id
        
        # Afficher des statistiques détaillées sur les lignes trouvées pour ce dossier
        filtered_count = sum(1 for key in records_dict.keys() if key.startswith(f"{dossier_number}_"))
        log(f"  {filtered_count} clés d'identification trouvées pour les lignes de blocs répétables du dossier {dossier_number}")
    
    return records_dict

def process_repetables_for_grist(client, dossier_data, table_id, column_types, problematic_ids=None):
    """
    Traite les blocs répétables d'un dossier et les stocke dans Grist.
    Version améliorée qui évite les doublons et gère mieux l'identification des lignes existantes.
    
    Args:
        client: Instance de GristClient
        dossier_data: Données du dossier (format brut de l'API)
        table_id: ID de la table Grist pour les blocs répétables
        column_types: Types de colonnes pour la table répétable
        problematic_ids: Liste des IDs de descripteurs à ignorer
        
    Returns:
        tuple: (nombre de lignes créées avec succès, nombre de lignes en échec)
    """
    dossier_number = dossier_data["number"]
    repetable_success = 0
    repetable_errors = 0
    
    # Récupérer les types de colonnes pour la table répétable
    repetable_columns = {col["id"]: col["type"] for col in column_types}
    
    # Vérifier quelles colonnes existent réellement dans Grist
    try:
        # Récupérer les colonnes actuelles de la table 
        url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
        response = requests.get(url, headers=client.headers)
        
        if response.status_code == 200:
            columns_data = response.json()
            actual_columns = set()
            
            if "columns" in columns_data:
                for col in columns_data["columns"]:
                    actual_columns.add(col.get("id"))
                    
            log_verbose(f"  Colonnes existantes dans Grist: {len(actual_columns)} colonnes")
            
            # Filtrer les colonnes qui n'existent pas
            valid_columns = set(repetable_columns.keys()).intersection(actual_columns)
            
            # Si certaines colonnes manquent, les ajouter
            missing_columns = []
            for col_id, col_type in repetable_columns.items():
                if col_id not in actual_columns:
                    missing_columns.append({"id": col_id, "type": col_type})
            
            # Colonnes géographiques standard à ajouter si elles n'existent pas déjà
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
            
            # Ajouter les colonnes géographiques si elles n'existent pas
            for col in geo_columns:
                if col["id"] not in actual_columns and col["id"] not in [c["id"] for c in missing_columns]:
                    missing_columns.append(col)
                    # Ajouter aussi au dictionnaire des colonnes répétables
                    repetable_columns[col["id"]] = col["type"]
            
            if missing_columns:
                log(f"  Ajout de {len(missing_columns)} colonnes manquantes...")
                add_columns_url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/columns"
                add_columns_payload = {"columns": missing_columns}
                add_response = requests.post(add_columns_url, headers=client.headers, json=add_columns_payload)
                
                if add_response.status_code != 200:
                    log_error(f"  Erreur lors de l'ajout des colonnes: {add_response.text}")
                else:
                    log(f"  Colonnes ajoutées avec succès")
                    valid_columns = set(repetable_columns.keys())
        else:
            log_error(f"  Erreur lors de la récupération des colonnes: {response.text}")
            valid_columns = set(repetable_columns.keys())
    except Exception as e:
        log_error(f"  Erreur lors de la vérification des colonnes: {str(e)}")
        valid_columns = set(repetable_columns.keys())

    # Récupérer tous les enregistrements sans filtrage qui cause l'erreur 500
    existing_rows = get_existing_repetable_rows_improved_no_filter(client, table_id, dossier_number)
    log(f"  {len(existing_rows)} clés d'identification trouvées pour les lignes de blocs répétables du dossier {dossier_number}")

    # Fonction récursive pour explorer les champs et traiter les blocs répétables
    def explore_and_store_repetables(champs, is_annotation=False):
        nonlocal repetable_success, repetable_errors
        
        for champ in champs:
            # Ignorer explicitement les champs HeaderSectionChamp et ExplicationChamp
            if (champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"] or 
                (problematic_ids and champ.get("id") in problematic_ids)):
                log_verbose(f"  Ignoré: '{champ.get('label', '')}' (Type: {champ['__typename']})")
                continue
                
            if champ["__typename"] == "RepetitionChamp":
                block_label = champ["label"]
                log(f"  Traitement du bloc répétable: {block_label}")
                
                # Traiter chaque ligne du bloc répétable
                for row_index, row in enumerate(champ.get("rows", [])):
                    try:
                        # Collecter d'abord toutes les données des champs de cette ligne
                        row_data = {}
                        geo_data_list = []  # Liste pour stocker les données géographiques multiples

                        if "champs" in row:
                            for field in row["champs"]:
                                # Ignorer les champs problématiques
                                if field["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"]:
                                   continue
                                   
                                field_label = field["label"]
                                normalized_label = normalize_column_name(field_label)
                                
                                try:
                                    # Extraire la valeur du champ selon son type
                                    value, json_value = extract_field_value(field)
                                    
                                    # Ajouter la valeur au dictionnaire des données de la ligne
                                    if normalized_label in repetable_columns and normalized_label in valid_columns:
                                        column_type = repetable_columns[normalized_label]
                                        row_data[normalized_label] = format_value_for_grist(value, column_type)
                                    
                                    # Traitement spécial pour les champs de type carte (CarteChamp)
                                    if field["__typename"] == "CarteChamp" and field.get("geoAreas"):
                                        # Pour chaque zone géographique, créer un dictionnaire de données
                                        for geo_area in field.get("geoAreas", []):
                                            geo_data = extract_geo_data(geo_area)
                                            geo_data["field_name"] = normalized_label
                                            geo_data_list.append(geo_data)
                                    
                                except Exception as e:
                                    log_error(f"      Erreur lors de l'extraction de la valeur pour {field_label}: {str(e)}")
                        
                        # Récupérer l'ID de la ligne
                        row_id = row.get("id", f"row_{row_index}")
                        
                        # Créer l'enregistrement avec les métadonnées de base
                        base_record = {
                            "dossier_number": dossier_number,
                            "block_label": block_label,
                            "block_row_index": row_index + 1,
                            "block_row_id": row_id
                        }
                        
                        # Si nous avons des données géographiques, créer un enregistrement par géométrie
                        if geo_data_list:
                            for geo_index, geo_data in enumerate(geo_data_list):
                                # Combiner les données de base, les données de la ligne et les données géographiques
                                geo_record = base_record.copy()
                                geo_record.update(row_data)
                                
                                # Créer un ID unique pour cette géométrie
                                geo_identifier = f"{row_id}_geo{geo_index+1}"
                                geo_record["block_row_id"] = geo_identifier
                                
                                # Ajouter les données géographiques
                                for key, value in geo_data.items():
                                    if key in repetable_columns and key in valid_columns:
                                        geo_record[key] = format_value_for_grist(value, repetable_columns[key])
                                
                                # Créer différentes clés de recherche pour trouver des correspondances
                                search_keys = []
                                
                                # Format 1: dossier_number_block_label_geo_identifier
                                search_keys.append(f"{dossier_number}_{block_label}_{geo_identifier}")
                                
                                # Format 2: dossier_number_block_label_row_id_geo_index
                                search_keys.append(f"{dossier_number}_{block_label}_{row_id}_geo{geo_index+1}")
                                
                                # Format 3: dossier_number_block_label_field_name_geo_id
                                field_name = geo_data.get("field_name", "")
                                geo_id = geo_data.get("geo_id", "")
                                if field_name and geo_id:
                                    search_keys.append(f"{dossier_number}_{block_label}_{field_name}_{geo_id}")
                                
                                # Chercher dans les enregistrements existants avec toutes les clés
                                found_id = None
                                for key in search_keys:
                                    # Normaliser la clé pour la recherche
                                    normalized_key = key.lower()
                                    if normalized_key in existing_rows:
                                        found_id = existing_rows[normalized_key]
                                        log_verbose(f"    Ligne trouvée avec la clé: {normalized_key}")
                                        break
                                
                                # Si on a trouvé un enregistrement existant, le mettre à jour
                                if found_id:
                                    log_verbose(f"    Mise à jour de la ligne existante (ID: {found_id})")
                                    update_payload = {"records": [{"id": found_id, "fields": geo_record}]}
                                    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
                                    response = requests.patch(url, headers=client.headers, json=update_payload)
                                    
                                    if response.status_code in [200, 201]:
                                        repetable_success += 1
                                        log_verbose(f"    Géométrie {geo_index+1} du bloc {block_label}, ligne {row_index+1} mise à jour avec succès")
                                    else:
                                        repetable_errors += 1
                                        log_error(f"    Erreur lors de la mise à jour: {response.text}")
                                else:
                                    # Création d'un nouvel enregistrement
                                    log_verbose(f"    Création d'une nouvelle ligne (aucune correspondance trouvée)")
                                    create_payload = {"records": [{"fields": geo_record}]}
                                    url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
                                    response = requests.post(url, headers=client.headers, json=create_payload)
                                    
                                    if response.status_code in [200, 201]:
                                        repetable_success += 1
                                        log_verbose(f"    Géométrie {geo_index+1} du bloc {block_label}, ligne {row_index+1} créée avec succès")
                                        
                                        # Ajouter l'ID à existing_rows pour éviter les doublons futurs
                                        result = response.json()
                                        if 'records' in result and result['records']:
                                            new_id = result['records'][0].get('id')
                                            if new_id:
                                                for key in search_keys:
                                                    existing_rows[key.lower()] = new_id
                                    else:
                                        repetable_errors += 1
                                        log_error(f"    Erreur lors de la création: {response.text}")
                        else:
                            # Si pas de données géographiques, créer un seul enregistrement avec les données de la ligne
                            record = base_record.copy()
                            record.update(row_data)
                            
                            # Créer différentes clés de recherche
                            search_keys = []
                            
                            # Format 1: dossier_number_block_label_row_id
                            search_keys.append(f"{dossier_number}_{block_label}_{row_id}")
                            
                            # Format 2: dossier_number_block_label_index
                            search_keys.append(f"{dossier_number}_{block_label}_index_{row_index+1}")
                            
                            # Format 3: Utilisation directe de row_id
                            search_keys.append(row_id)
                            
                            # Chercher dans les enregistrements existants
                            found_id = None
                            for key in search_keys:
                                normalized_key = key.lower()
                                if normalized_key in existing_rows:
                                    found_id = existing_rows[normalized_key]
                                    log_verbose(f"    Ligne trouvée avec la clé: {normalized_key}")
                                    break
                            
                            # Si on a trouvé un enregistrement existant, le mettre à jour
                            if found_id:
                                log_verbose(f"    Mise à jour de la ligne existante (ID: {found_id})")
                                update_payload = {"records": [{"id": found_id, "fields": record}]}
                                url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
                                response = requests.patch(url, headers=client.headers, json=update_payload)
                                
                                if response.status_code in [200, 201]:
                                    repetable_success += 1
                                    log_verbose(f"    Ligne {row_index+1} du bloc {block_label} mise à jour avec succès")
                                else:
                                    repetable_errors += 1
                                    log_error(f"    Erreur lors de la mise à jour: {response.text}")
                            else:
                                # Création d'un nouvel enregistrement
                                log_verbose(f"    Création d'une nouvelle ligne (aucune correspondance trouvée)")
                                create_payload = {"records": [{"fields": record}]}
                                url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
                                response = requests.post(url, headers=client.headers, json=create_payload)
                                
                                if response.status_code in [200, 201]:
                                    repetable_success += 1
                                    log_verbose(f"    Ligne {row_index+1} du bloc {block_label} créée avec succès")
                                    
                                    # Ajouter l'ID à existing_rows pour éviter les doublons futurs
                                    result = response.json()
                                    if 'records' in result and result['records']:
                                        new_id = result['records'][0].get('id')
                                        if new_id:
                                            for key in search_keys:
                                                existing_rows[key.lower()] = new_id
                                else:
                                    repetable_errors += 1
                                    log_error(f"    Erreur lors de la création: {response.text}")
                            
                    except Exception as e:
                        repetable_errors += 1
                        log_error(f"    Exception lors du traitement de la ligne {row_index+1} du bloc {block_label}: {str(e)}")
                        import traceback
                        traceback.print_exc()
    
    # Traiter les blocs répétables directement depuis les données brutes
    log(f"Exploration des blocs répétables pour le dossier {dossier_number}...")
    explore_and_store_repetables(dossier_data.get("champs", []))
    
    # Traiter également les blocs répétables dans les annotations
    if "annotations" in dossier_data:
        explore_and_store_repetables(dossier_data.get("annotations", []), is_annotation=True)
    
    # Afficher le résumé
    if repetable_success > 0:
        log(f"Blocs répétables: {repetable_success} lignes créées avec succès, {repetable_errors} lignes en échec")
    elif repetable_errors > 0:
        log_error(f"Attention: Aucun bloc répétable traité avec succès, {repetable_errors} lignes en échec")
    else:
        log_verbose("Aucun bloc répétable trouvé dans ce dossier")
    
    return repetable_success, repetable_errors

def process_repetables_batch(client, dossiers_data, table_id, column_types, problematic_ids=None, batch_size=50):
    """
    Traite les blocs répétables par lot pour plusieurs dossiers.
    
    Args:
        client: Instance de GristClient
        dossiers_data: Liste des données de dossiers avec leurs blocs répétables
        table_id: ID de la table des blocs répétables
        column_types: Types de colonnes
        problematic_ids: IDs à filtrer
        batch_size: Taille du lot pour les opérations d'upsert
        
    Returns:
        tuple: (success_count, error_count)
    """
    total_success = 0
    total_errors = 0
    
    # Récupérer tous les enregistrements existants en une seule fois
    existing_rows = get_existing_repetable_rows_improved_no_filter(client, table_id)
    log(f"  {len(existing_rows)} identifiants de lignes existantes récupérés pour tous les dossiers")
    
    # Collecter toutes les lignes à traiter
    all_rows_to_update = []
    all_rows_to_create = []
    
    # Fonction pour explorer les blocs répétables et extraire leurs données
    def extract_repetable_rows(dossier_data):
        rows_to_update = []
        rows_to_create = []
        dossier_number = dossier_data["number"]
        
        # Fonction pour traiter un champ répétable
        def process_repetable_field(champ, is_annotation=False):
            if champ["__typename"] != "RepetitionChamp":
                return
                
            block_label = champ["label"]
            
            for row_index, row in enumerate(champ.get("rows", [])):
                try:
                    # Collecter d'abord toutes les données des champs de cette ligne
                    row_data = {}
                    geo_data_list = []
                    
                    if "champs" in row:
                        for field in row["champs"]:
                            # Utiliser la fonction commune de filtrage
                            if should_skip_field(field, problematic_ids):
                                log_verbose(f"    Champ ignoré: {field.get('label', 'sans label')} (type: {field.get('__typename', 'unknown')})")
                                continue
                            
                            field_label = field["label"]
                            normalized_label = normalize_column_name(field_label)
                            
                            # NOUVEAU : Dernière vérification de sécurité
                            if normalized_label.lower() in ["attention", "titre", "explication", "header", "section"]:
                                log_verbose(f"    Label normalisé ignoré: {normalized_label}")
                                continue


                            # Extraire la valeur
                            value, json_value = extract_field_value(field)
                            
                            # Si les deux valeurs sont None, passer au champ suivant
                            if value is None and json_value is None:
                                continue
                            
                            # Ajouter au dictionnaire des données
                            column_type = next((col["type"] for col in column_types if col["id"] == normalized_label), "Text")
                            row_data[normalized_label] = format_value_for_grist(value, column_type)
                                
                            # Traitement spécial pour les champs cartographiques
                            if field["__typename"] == "CarteChamp" and field.get("geoAreas"):
                                for geo_area in field.get("geoAreas", []):
                                    geo_data = extract_geo_data(geo_area)
                                    geo_data["field_name"] = normalized_label
                                    geo_data_list.append(geo_data)
                    
                    # Récupérer l'ID de la ligne
                    row_id = row.get("id", f"row_{row_index}")
                    
                    # Créer l'enregistrement avec les métadonnées de base
                    base_record = {
                        "dossier_number": dossier_number,
                        "block_label": block_label,
                        "block_row_index": row_index + 1,
                        "block_row_id": row_id
                    }
                    
                    # Si nous avons des données géographiques, créer un enregistrement par géométrie
                    if geo_data_list:
                        for geo_index, geo_data in enumerate(geo_data_list):
                            geo_record = base_record.copy()
                            geo_record.update(row_data)
                            
                            # Créer un ID unique pour cette géométrie
                            geo_identifier = f"{row_id}_geo{geo_index+1}"
                            geo_record["block_row_id"] = geo_identifier
                            
                            # Ajouter les données géographiques
                            for key, value in geo_data.items():
                                column_type = next((col["type"] for col in column_types if col["id"] == key), "Text")
                                geo_record[key] = format_value_for_grist(value, column_type)
                            
                            # Générer différentes clés de recherche
                            search_keys = [
                                f"{dossier_number}_{block_label}_{geo_identifier}".lower(),
                                f"{dossier_number}_{block_label}_{row_id}_geo{geo_index+1}".lower()
                            ]
                            
                            field_name = geo_data.get("field_name", "")
                            geo_id = geo_data.get("geo_id", "")
                            if field_name and geo_id:
                                search_keys.append(f"{dossier_number}_{block_label}_{field_name}_{geo_id}".lower())
                            
                            # Chercher si l'enregistrement existe déjà
                            found_id = None
                            for key in search_keys:
                                if key in existing_rows:
                                    found_id = existing_rows[key]
                                    break
                            
                            if found_id:
                                # Mise à jour
                                rows_to_update.append({"id": found_id, "fields": geo_record})
                            else:
                                # Création
                                rows_to_create.append({"fields": geo_record})
                    else:
                        # Cas sans données géographiques
                        record = base_record.copy()
                        record.update(row_data)
                        
                        # Générer différentes clés de recherche
                        search_keys = [
                            f"{dossier_number}_{block_label}_{row_id}".lower(),
                            f"{dossier_number}_{block_label}_index_{row_index+1}".lower(),
                            row_id
                        ]
                        
                        # Chercher si l'enregistrement existe déjà
                        found_id = None
                        for key in search_keys:
                            if key in existing_rows:
                                found_id = existing_rows[key]
                                break
                        
                        if found_id:
                            # Mise à jour
                            rows_to_update.append({"id": found_id, "fields": record})
                        else:
                            # Création
                            rows_to_create.append({"fields": record})
                
                except Exception as e:
                    log_error(f"Exception lors du traitement d'une ligne répétable: {str(e)}")
        
        # Explorer les champs du dossier
        for champ in dossier_data.get("champs", []):
            # Vérifier aussi l'ID du champ principal
            if problematic_ids and champ.get("id") in problematic_ids:
                continue
            if champ["__typename"] == "RepetitionChamp":
                process_repetable_field(champ)
        
        # Explorer les annotations (si présentes)
        for annotation in dossier_data.get("annotations", []):
            # Vérifier aussi l'ID de l'annotation
            if problematic_ids and annotation.get("id") in problematic_ids:
                continue
            if annotation["__typename"] == "RepetitionChamp":
                process_repetable_field(annotation, is_annotation=True)
                
        return rows_to_update, rows_to_create
    
    # Traiter tous les dossiers
    for dossier_data in dossiers_data:
        try:
            dossier_number = dossier_data["number"]
            rows_to_update, rows_to_create = extract_repetable_rows(dossier_data)
            
            all_rows_to_update.extend(rows_to_update)
            all_rows_to_create.extend(rows_to_create)
            
            log_verbose(f"  Dossier {dossier_number}: {len(rows_to_update)} mises à jour, {len(rows_to_create)} créations")
        except Exception as e:
            log_error(f"Erreur lors de l'extraction des blocs répétables pour le dossier {dossier_data.get('number')}: {str(e)}")
            total_errors += 1
    
    # Traiter par lots - Normaliser d'abord tous les enregistrements
    if all_rows_to_update:
        # D'abord, collecter toutes les clés possibles
        all_keys = set()
        for record in all_rows_to_update:
            all_keys.update(record["fields"].keys())
        
        # Normaliser tous les enregistrements
        normalized_updates = []
        for record in all_rows_to_update:
            normalized_fields = {}
            for key in all_keys:
                normalized_fields[key] = record["fields"].get(key, None)
            normalized_updates.append({"id": record["id"], "fields": normalized_fields})
        
        # Maintenant traiter par lots
        for i in range(0, len(normalized_updates), batch_size):
            batch = normalized_updates[i:i+batch_size]
            log(f"  Traitement du lot de mise à jour {i // batch_size + 1}/{len(normalized_updates) // batch_size + 1} ({len(batch)} lignes)")
            
            update_payload = {"records": batch}
            url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
            response = requests.patch(url, headers=client.headers, json=update_payload)
            
            if response.status_code in [200, 201]:
                total_success += len(batch)
            else:
                log_error(f"  Erreur lors de la mise à jour par lot: {response.status_code} - {response.text}")
                
                # En cas d'échec, essayer individuellement
                log("  Tentative de mise à jour individuelle...")
                for individual_record in batch:
                    individual_payload = {"records": [individual_record]}
                    individual_response = requests.patch(url, headers=client.headers, json=individual_payload)
                    
                    if individual_response.status_code in [200, 201]:
                        total_success += 1
                    else:
                        total_errors += 1
    
    if all_rows_to_create:
        for i in range(0, len(all_rows_to_create), batch_size):
            batch = all_rows_to_create[i:i+batch_size]
            log(f"  Traitement du lot de création {i // batch_size + 1}/{len(all_rows_to_create) // batch_size + 1} ({len(batch)} lignes)")
            
            create_payload = {"records": batch}
            url = f"{client.base_url}/docs/{client.doc_id}/tables/{table_id}/records"
            response = requests.post(url, headers=client.headers, json=create_payload)
            
            if response.status_code in [200, 201]:
                total_success += len(batch)
            else:
                log_error(f"  Erreur lors de la création par lot: {response.status_code} - {response.text}")
                total_errors += len(batch)
    
    return total_success, total_errors
    
# Fonctions utilitaires pour la détection de colonnes dans les blocs répétables

def detect_repetable_columns_in_dossier(dossier_data):
    """
    Détecte les colonnes potentielles pour les blocs répétables dans un dossier.
    
    Args:
        dossier_data: Données du dossier
        
    Returns:
        list: Liste des définitions de colonnes
    """
    columns = [
        {"id": "dossier_number", "type": "Int"},
        {"id": "block_label", "type": "Text"},
        {"id": "block_row_index", "type": "Int"},
        {"id": "block_row_id", "type": "Text"},
        # Colonnes pour les données géographiques (renommées avec préfixe geo_)
        {"id": "field_name", "type": "Text"},
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
    
    # Fonction pour explorer récursivement les champs et détecter les colonnes
    def explore_champs(champs, found_columns=None):
        if found_columns is None:
            found_columns = {}
        
        for champ in champs:
            # Ignorer les champs HeaderSectionChamp et ExplicationChamp
            if champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"]:
                continue
                
            if champ["__typename"] == "RepetitionChamp":
                # Explorer les lignes répétables pour détecter leurs champs
                for row in champ.get("rows", []):
                    if "champs" in row:
                        for field in row["champs"]:
                            # NOUVEAU : Utiliser should_skip_field pour la cohérence
                            if should_skip_field(field):
                                log_verbose(f"Champ ignoré dans la détection: {field.get('label', 'sans label')}")
                                continue
                                
                            field_label = field["label"]
                            normalized_label = normalize_column_name(field_label)
                            
                            # NOUVEAU : Double vérification sur le label normalisé
                            if normalized_label.lower() in ["attention", "titre", "explication", "header", "section"]:
                                log_verbose(f"Label normalisé ignoré: {normalized_label}")
                                continue
                            
                            # Déterminer le type de colonne
                            column_type = "Text"  # Type par défaut
                            if field["__typename"] in ["DateChamp", "DatetimeChamp"]:
                                column_type = "DateTime"
                            elif field["__typename"] in ["DecimalNumberChamp"]:
                                column_type = "Numeric"
                            elif field["__typename"] in ["IntegerNumberChamp"]:
                                column_type = "Int"
                            elif field["__typename"] in ["CheckboxChamp", "YesNoChamp"]:
                                column_type = "Bool"
                            
                            # Ajouter la colonne si elle n'existe pas déjà
                            if normalized_label not in found_columns:
                                found_columns[normalized_label] = column_type
                            
                            # Pour les types complexes, ajouter aussi une colonne JSON
                            if field["__typename"] in ["CarteChamp", "AddressChamp", "SiretChamp", 
                                                    "LinkedDropDownListChamp", "MultipleDropDownListChamp",
                                                    "PieceJustificativeChamp", "CommuneChamp", "RNFChamp"]:
                                json_column = f"{normalized_label}_json"
                                if json_column not in found_columns:
                                    found_columns[json_column] = "Text"
        
        return found_columns
    
    # Explorer tous les champs du dossier
    found_columns = explore_champs(dossier_data.get("champs", []))
    
    # Explorer également les annotations
    if "annotations" in dossier_data:
        found_columns = explore_champs(dossier_data.get("annotations", []), found_columns)
    
    # Convertir le dictionnaire en liste de définitions de colonnes
    for col_id, col_type in found_columns.items():
        # Ne pas ajouter les colonnes qui existent déjà
        if not any(col["id"] == col_id for col in columns):
            columns.append({"id": col_id, "type": col_type})
    
    return columns


def detect_repetable_columns_from_multiple_dossiers(dossiers_data):
    """
    Fusionne les définitions de colonnes à partir de plusieurs dossiers.
    
    Args:
        dossiers_data: Liste des données de dossiers
        
    Returns:
        list: Liste fusionnée des définitions de colonnes
    """
    all_columns = {}
    
    # Collecter toutes les colonnes de tous les dossiers
    for dossier_data in dossiers_data:
        columns = detect_repetable_columns_in_dossier(dossier_data)
        for col in columns:
            col_id = col["id"]
            col_type = col["type"]
            
            # NOUVEAU : Ignorer les colonnes qui correspondent aux champs problématiques
            if col_id.lower() in ["attention", "titre", "explication", "header", "section"]:
                log_verbose(f"Colonne ignorée lors de la détection: {col_id}")
                continue
            
            if col_id in all_columns:
                # Si le type est différent, prioriser certains types
                existing_type = all_columns[col_id]
                if existing_type == "Text" and col_type != "Text":
                    all_columns[col_id] = col_type
                elif existing_type == "Int" and col_type in ["Numeric", "DateTime"]:
                    all_columns[col_id] = col_type
            else:
                all_columns[col_id] = col_type
    
    # Convertir le dictionnaire en liste
    result = []
    for col_id, col_type in all_columns.items():
        result.append({"id": col_id, "type": col_type})
    
    # Ajouter explicitement les colonnes géographiques pour s'assurer qu'elles sont présentes
    geo_columns = [
        {"id": "field_name", "type": "Text"},
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
        if not any(col["id"] == geo_col["id"] for col in result):
            result.append(geo_col)
    
    return result