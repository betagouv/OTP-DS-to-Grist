import base64
import json
from typing import Dict, Any

def decode_base64_id(base64_id: str) -> str:
    """
    Décode un ID en Base64 utilisé par l'API GraphQL.
    
    Args:
        base64_id: ID en format Base64
        
    Returns:
        ID décodé
    """
    try:
        # Décodage Base64
        decoded = base64.b64decode(base64_id).decode('utf-8')
        
        # Les IDs GraphQL sont souvent de la forme "TypeName:id"
        if ':' in decoded:
            return decoded.split(':')[-1]
        
        # Extrait juste le nombre si le format est "Champ-123456"
        if '-' in decoded:
            return decoded.split('-')[-1]
        
        return decoded
    except:
        # Si le décodage échoue, retourne l'ID original
        return base64_id

def format_complex_json_for_grist(json_value, max_length=10000):
    """
    Formate une valeur JSON complexe pour l'insertion dans Grist.
    Tronque si nécessaire et s'assure que la valeur est une chaîne.
    
    Args:
        json_value: Valeur JSON à formater
        max_length: Longueur maximale de la chaîne résultante
        
    Returns:
        Chaîne formatée pour Grist
    """
    if json_value is None:
        return None
        
    try:
        json_str = json.dumps(json_value, ensure_ascii=False)
        # Tronquer si la chaîne est trop longue
        if len(json_str) > max_length:
            json_str = json_str[:max_length] + "..."
        return json_str
    except (TypeError, ValueError):
        # Si la sérialisation échoue, convertir en chaîne simple
        str_value = str(json_value)
        if len(str_value) > max_length:
            str_value = str_value[:max_length] + "..."
        return str_value

def associate_geojson_with_champs(geojson_data, champs):
    """
    Associe les données GeoJSON aux champs par différentes méthodes de correspondance.
    """
    # Dictionnaire pour stocker les associations
    associations = {}
    
    # Dictionnaire pour indexer les champs par différents critères
    champs_by_numeric_id = {}
    champs_by_descriptor_id = {}
    champs_by_label = {}
    
    # Indexer les champs
    for champ in champs:
        if champ["numeric_id"]:
            champs_by_numeric_id[champ["numeric_id"]] = champ
        
        if champ["decoded_descriptor_id"]:
            champs_by_descriptor_id[champ["decoded_descriptor_id"]] = champ
        
        champs_by_label[champ["base_label"]] = champ
    
    # Parcourir les features GeoJSON
    for feature in geojson_data.get("features", []):
        properties = feature.get("properties", {})
        
        # Extraire les identifiants
        champ_id = properties.get("champ_id")
        champ_label = properties.get("champ_label")
        champ_row = properties.get("champ_row", "")
        
        # Priorité 1: Essayer de faire correspondre par ID numérique
        matched_champ = None
        if champ_id and str(champ_id) in champs_by_numeric_id:
            matched_champ = champs_by_numeric_id[str(champ_id)]
        
        # Priorité 2: Essayer de faire correspondre par ID de descripteur
        if not matched_champ and champ_id:
            for c in champs:
                if c["decoded_descriptor_id"] == str(champ_id):
                    matched_champ = c
                    break
        
        # Priorité 3: Essayer de faire correspondre par label
        if not matched_champ and champ_label:
            for c in champs:
                # Vérifier si le label du champ contient le label GeoJSON
                if champ_label in c["label"] or c["base_label"] == champ_label:
                    # Pour les blocs répétables, vérifier aussi l'ID de la rangée
                    if champ_row and c["row_id"]:
                        if champ_row == c["row_id"]:
                            matched_champ = c
                            break
                    else:
                        matched_champ = c
                        break
        
        # Si une correspondance a été trouvée, ajouter la feature à l'association
        if matched_champ:
            champ_key = matched_champ["id"]
            if champ_key not in associations:
                associations[champ_key] = []
            
            associations[champ_key].append(feature)
    
    return associations