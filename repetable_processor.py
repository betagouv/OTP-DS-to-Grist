"""
Module spécialisé pour le traitement
des blocs répétables dans les formulaires Démarches Simplifiées.
Ce module extrait, transforme et stocke les données des blocs répétables dans Grist.
"""
import unicodedata
import hashlib
import re
import json
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

try:
    from utils.log import log, log_verbose, log_error
except ImportError:
    # Définitions de secours en cas d'échec de l'import
    def log(message, level=1):
        print(message)

    def log_verbose(message):
        print(message)

    def log_error(message):
        print(f"ERREUR: {message}")


def auto_fix_missing_columns_optimized(client, table_id, records_payload):
    """
    Version unique et optimisée pour corriger automatiquement toutes les colonnes manquantes.
    Remplace les 3 fonctions précédentes.

    Args:
        client: Instance GristClient
        table_id: ID de la table
        records_payload: Payload original

    Returns:
        tuple: (success: bool, response)
    """
    try:
        # 1. Récupérer les colonnes existantes
        existing_columns = set(client.get_columns(table_id))

        if not existing_columns:
            log_error(f"    [AUTO-FIX] Impossible de recuperer les colonnes existantes")
            return False, None

        # 2. Analyser toutes les colonnes nécessaires dans le payload
        required_columns = set()
        column_types = {}

        if "records" in records_payload:
            for record in records_payload["records"]:
                if "fields" in record:
                    for field_name, value in record["fields"].items():
                        required_columns.add(field_name)

                        # Déterminer le type de colonne
                        if field_name not in column_types:
                            if isinstance(value, bool):
                                column_types[field_name] = "Bool"

                            elif isinstance(value, int):
                                column_types[field_name] = "Int"

                            elif isinstance(value, float):
                                column_types[field_name] = "Numeric"

                            elif isinstance(value, str) and value:
                                try:
                                    datetime.fromisoformat(value.replace('Z', '+00:00'))
                                    column_types[field_name] = "DateTime"
                                except Exception:
                                    column_types[field_name] = "Text"
                            else:
                                column_types[field_name] = "Text"

        # 3. Identifier les colonnes manquantes
        missing_columns = required_columns - existing_columns

        # 4. Ajouter toutes les colonnes manquantes en une seule requête si nécessaire
        if missing_columns:
            log(f"    [AUTO-FIX] Ajout de {len(missing_columns)} colonnes: {list(missing_columns)}")

            columns_to_add = []
            for col_name in missing_columns:
                col_type = column_types.get(col_name, "Text")
                columns_to_add.append({"id": col_name, "type": col_type})

            add_response = client.add_columns(table_id, columns_to_add)

            if add_response.status_code != 200:
                log_error(f"    [AUTO-FIX] ECHEC ajout colonnes: {add_response.text}")
                return False, add_response

            log(f"    [AUTO-FIX] SUCCES: {len(missing_columns)} colonnes ajoutees")

        # 5. Tenter l'insertion des données
        response = client.post_records(table_id, records_payload["records"])

        if response.status_code in [200, 201]:
            log(f"    [AUTO-FIX] SUCCES: Donnees inserees")
            return True, response
        else:
            log_error(f"    [AUTO-FIX] ECHEC insertion: {response.status_code} - {response.text}")
            return False, response

    except Exception as e:
        log_error(f"    [AUTO-FIX] Exception: {str(e)}")
        return False, None


def should_skip_field_unified(field, problematic_ids=None):
    """
    Version unifiée du filtrage qui respecte exactement la logique de schema_utils.
    Cette fonction remplace should_skip_field pour garantir la cohérence.
    """
    # Filtrage par typename (même logique que schema_utils)
    if field.get("__typename") in [
        "HeaderSectionChampDescriptor",
        "ExplicationChampDescriptor",
        "HeaderSectionChamp",
        "ExplicationChamp"
    ]:
        return True

    # Filtrage par type (même logique que schema_utils)
    if field.get("type") in [
        "header_section",
        "explication",
        "piece_justificative"
    ]:
        return True

    # Filtrage par ID problématique (transmission depuis schema_utils)
    if problematic_ids and field.get("champDescriptorId") in problematic_ids:
        return True

    return False


def normalize_column_name(name, max_length=150):
    """
    Normalise un nom de colonne pour Grist en garantissant des identifiants valides.
    Gère correctement les apostrophes et autres caractères spéciaux.

    Args:
        name: Le nom original de la colonne
        max_length: Longueur maximale autorisée (défaut: 150)

    Returns:
        str: Nom de colonne normalisé pour Grist
    """
    if not name:
        return "column"

    # Supprimer les espaces en début et fin, et remplacer les espaces consécutifs par un seul espace

    name = name.strip()
    name = re.sub(r'\s+', ' ', name)

    # ÉTAPE CRITIQUE: Remplacer les apostrophes par des underscores AVANT de supprimer les accents
    # Cela évite que "l'enseignant" devienne "lenseignant" au lieu de "l_enseignant"
    name = name.replace("'", "_")
    name = name.replace("'", "_")  # Apostrophe typographique
    name = name.replace("`", "_")  # Accent grave utilisé comme apostrophe

    # Supprimer les accents
    name = unicodedata.normalize('NFKD', name)
    name = ''.join([c for c in name if not unicodedata.combining(c)])

    # Convertir en minuscules et remplacer les caractères non alphanumériques par des underscores
    name = name.lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)

    # Éliminer les underscores multiples consécutifs
    name = re.sub(r'_+', '_', name)

    # Éliminer les underscores en début et fin
    name = name.strip('_')

    # S'assurer que le nom commence par une lettre
    if not name or not name[0].isalpha():
        name = "col_" + (name or "")

    # Tronquer si nécessaire à max_length caractères
    if len(name) > max_length:
        # Générer un hash pour garantir l'unicité
        hash_part = hashlib.md5(name.encode()).hexdigest()[:6]
        name = f"{name[:max_length-7]}_{hash_part}"

    return name


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
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
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


def extract_field_value(
    champ: Dict[str, Any]
) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """
    Extrait la valeur d'un champ selon son type.
    Gère correctement le cas des valeurs None.

    Args:
        champ: Dictionnaire contenant les données du champ

    Returns:
        tuple: (valeur texte, valeur JSON)
    """
    # Utiliser la fonction commune de filtrage
    if should_skip_field_unified(champ):
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

    elif typename == "DropDownListChamp":
        value = champ.get("stringValue")

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


def get_existing_repetable_rows_improved_no_filter(
    client,
    table_id,
    dossier_number=None
):
    """
    Version améliorée qui évite d'utiliser le filtre côté serveur,
    récupère toutes les lignes et filtre côté client.
    """
    if not client.doc_id:
        raise ValueError("Document ID is required")

    # Récupérer tous les enregistrements sans filtre
    log_verbose(f"Récupération de tous les enregistrements de la table {table_id}")

    response = client.get_records(table_id)

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
                if 'dossier_number' in fields:
                    # Filtrer par dossier si un dossier_number est spécifié
                    if dossier_number is not None and str(fields['dossier_number']) != str(dossier_number):
                        continue

                    current_dossier_number = str(fields['dossier_number'])
                    block_label = fields.get('block_label', '')  # ✅ Optionnel

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

        # Afficher des statistiques détaillées sur les lignes trouvées
        if dossier_number is not None:
            filtered_count = sum(1 for key in records_dict.keys() if key.startswith(f"{dossier_number}_"))
            log(f"  {filtered_count} clés d'identification trouvées pour les lignes de blocs répétables du dossier {dossier_number}")
        else:
            log(f"  {len(records_dict)} clés d'identification trouvées pour tous les blocs répétables")
            return records_dict


def process_repetables_batch(
    client,
    dossiers_data,
    table_ids_dict,
    column_types_dict,
    problematic_ids=None,
    batch_size=50
):
    """
    Traite les blocs répétables par lot pour plusieurs dossiers.
    ✅ VERSION ADAPTÉE : Supporte les tables séparées par bloc

    Args:
        client: Instance de GristClient
        dossiers_data: Liste des données de dossiers
        table_ids_dict: Dict {block_label_normalized: table_id}
        column_types_dict: Dict {block_label_normalized: {"columns": [...]}}
        problematic_ids: IDs à filtrer
        batch_size: Taille du lot

    Returns:
        tuple: (success_count, error_count)
    """
    total_success = 0
    total_errors = 0

    # ✅ NOUVEAU : Récupérer TOUTES les lignes existantes AVANT la boucle
    existing_rows_by_block = {}
    for block_key, table_id in table_ids_dict.items():
        existing_rows_by_block[block_key] = get_existing_repetable_rows_improved_no_filter(
            client,
            table_id,
            None  # ✅ None = récupérer TOUTES les lignes de tous les dossiers
        )

    # Grouper les dossiers et extraire les lignes par bloc
    rows_by_block = {}  # {block_label_normalized: {"to_update": [], "to_create": [], "existing_rows": {}}}

    for dossier_data in dossiers_data:
        try:
            dossier_number = dossier_data["number"]

            # Extraire les blocs répétables de ce dossier (champs + annotations)
            all_champs = dossier_data.get("champs", []) + dossier_data.get("annotations", [])

            for champ in all_champs:
                # Filtrer les blocs non répétables
                if champ["__typename"] != "RepetitionChamp":
                    continue

                # Filtrer les champs problématiques
                if problematic_ids and champ.get("champDescriptorId") in problematic_ids:
                    continue


                # Détecter si c'est une annotation en vérifiant si le champ vient de la liste annotations
                is_annotation = champ in dossier_data.get("annotations", [])
                block_label = f"annotation_{champ['label']}" if is_annotation else champ["label"]
                normalized_block = normalize_column_name(block_label)

                # Vérifier que ce bloc a une table
                if normalized_block not in table_ids_dict:
                    log_verbose(f"Bloc '{block_label}' ignoré (pas de table)")
                    continue

                # ✅ MODIFIÉ : Utiliser le dictionnaire pré-chargé
                if normalized_block not in rows_by_block:
                    rows_by_block[normalized_block] = {
                        "to_update": [],
                        "to_create": [],
                        "existing_rows": existing_rows_by_block.get(normalized_block, {})  # ✅ Utiliser le cache
                    }

                # Obtenir les types de colonnes pour ce bloc
                block_column_types = {col["id"]: col["type"] for col in column_types_dict[normalized_block]["columns"]}

                # Traiter chaque ligne du bloc répétable
                for row_index, row in enumerate(champ.get("rows", [])):
                    try:
                        # Collecter les données de la ligne
                        row_data = {}
                        geo_data_list = []

                        if "champs" in row:
                            for field in row["champs"]:
                                # Filtrer les champs problématiques
                                if should_skip_field_unified(field, problematic_ids):
                                    continue

                                field_label = field["label"]
                                normalized_label = normalize_column_name(field_label)

                                # Extraire la valeur
                                value, json_value = extract_field_value(field)

                                if value is None and json_value is None:
                                    continue

                                # Ajouter au dictionnaire
                                column_type = block_column_types.get(normalized_label, "Text")
                                row_data[normalized_label] = format_value_for_grist(value, column_type)

                                # Traitement des champs cartographiques
                                if field["__typename"] == "CarteChamp" and field.get("geoAreas"):
                                    for geo_area in field.get("geoAreas", []):
                                        geo_data = extract_geo_data(geo_area)
                                        geo_data["field_name"] = normalized_label
                                        geo_data_list.append(geo_data)

                        # ID de la ligne
                        row_id = row.get("id", f"row_{row_index}")

                        # Enregistrement de base
                        base_record = {
                            "dossier_number": dossier_number,
                            "block_id": champ.get("id"),
                            "block_row_index": row_index + 1,
                            "block_row_id": row_id
                        }

                        # Traiter les géométries ou la ligne simple
                        if geo_data_list:
                            # Créer un enregistrement par géométrie
                            for geo_index, geo_data in enumerate(geo_data_list):
                                geo_record = base_record.copy()
                                geo_record.update(row_data)

                                geo_identifier = f"{row_id}_geo{geo_index+1}"
                                geo_record["block_row_id"] = geo_identifier

                                # Ajouter les données géographiques
                                for key, value in geo_data.items():
                                    column_type = block_column_types.get(key, "Text")
                                    geo_record[key] = format_value_for_grist(value, column_type)

                                # Clés de recherche
                                search_keys = [
                                    f"{dossier_number}_{block_label}_{geo_identifier}".lower(),
                                    f"{dossier_number}_{block_label}_{row_id}_geo{geo_index+1}".lower()
                                ]

                                field_name = geo_data.get("field_name", "")
                                geo_id = geo_data.get("geo_id", "")
                                if field_name and geo_id:
                                    search_keys.append(f"{dossier_number}_{block_label}_{field_name}_{geo_id}".lower())

                                # Chercher si existe
                                found_id = None
                                for key in search_keys:
                                    if key in rows_by_block[normalized_block]["existing_rows"]:
                                        found_id = rows_by_block[normalized_block]["existing_rows"][key]
                                        break

                                if found_id:
                                    rows_by_block[normalized_block]["to_update"].append({"id": found_id, "fields": geo_record})
                                else:
                                    rows_by_block[normalized_block]["to_create"].append({"fields": geo_record})
                        else:
                            # Ligne simple sans géométrie
                            record = base_record.copy()
                            record.update(row_data)

                            # Clés de recherche
                            search_keys = [
                                f"{dossier_number}_{block_label}_{row_id}".lower(),
                                f"{dossier_number}_{block_label}_index_{row_index+1}".lower(),
                                row_id
                            ]

                            # Chercher si existe
                            found_id = None
                            for key in search_keys:
                                if key in rows_by_block[normalized_block]["existing_rows"]:
                                    found_id = rows_by_block[normalized_block]["existing_rows"][key]
                                    break

                            if found_id:
                                rows_by_block[normalized_block]["to_update"].append({"id": found_id, "fields": record})
                            else:
                                rows_by_block[normalized_block]["to_create"].append({"fields": record})

                    except Exception as e:
                        log_error(f"Erreur extraction ligne {row_index+1} du bloc '{block_label}': {str(e)}")
                        total_errors += 1

        except Exception as e:
            log_error(f"Erreur extraction dossier {dossier_data.get('number')}: {str(e)}")
            total_errors += 1

    # Traiter chaque bloc séparément
    for block_key, data in rows_by_block.items():
        table_id = table_ids_dict[block_key]

        log(f"Traitement du bloc '{block_key}': {len(data['to_update'])} MAJ, {len(data['to_create'])} créations")

        # Traiter les mises à jour par lot
        if data["to_update"]:
            # Normaliser tous les enregistrements
            all_keys = set()
            for record in data["to_update"]:
                all_keys.update(record["fields"].keys())

            normalized_updates = []
            for record in data["to_update"]:
                normalized_fields = {}
                for key in all_keys:
                    normalized_fields[key] = record["fields"].get(key, None)
                normalized_updates.append({
                    "id": record["id"],
                    "fields": normalized_fields
                })

            # Traiter par lots
            for i in range(0, len(normalized_updates), batch_size):
                batch = normalized_updates[i:i+batch_size]

                response = client.patch_records(table_id, batch)

                if response.status_code in [200, 201]:
                    total_success += len(batch)
                else:
                    log_error(f"Erreur MAJ lot: {response.status_code}")
                    # Fallback individuel
                    for individual in batch:
                        individual_response = client.patch_records(table_id, [individual])

                        if individual_response.status_code in [200, 201]:
                            total_success += 1
                        else:
                            total_errors += 1

        # Traiter les créations par lot
        if data["to_create"]:
            for i in range(0, len(data["to_create"]), batch_size):
                batch = data["to_create"][i:i+batch_size]

                create_payload = {"records": batch}
                response = client.post_records(table_id, batch)

                if response.status_code in [200, 201]:
                    total_success += len(batch)
                else:
                    # AUTO-FIX pour colonnes manquantes
                    if (
                        response.status_code == 400
                        and "Invalid column" in response.text
                    ):
                        log("[AUTO-FIX] Correction colonnes manquantes...")
                        success, _ = auto_fix_missing_columns_optimized(
                            client,
                            table_id,
                            create_payload
                        )

                        if success:
                            total_success += len(batch)
                        else:
                            total_errors += len(batch)
                    else:
                        total_errors += len(batch)

    return total_success, total_errors

# Fonctions utilitaires pour la détection de colonnes dans les blocs répétables


def detect_repetable_columns_in_dossier(dossier_data):
    """
    Détecte les colonnes potentielles pour les blocs répétables dans un dossier

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
            if champ["__typename"] in [
                "HeaderSectionChamp",
                "ExplicationChamp"
            ]:
                continue

            if champ["__typename"] == "RepetitionChamp":
                # Explorer les lignes répétables pour détecter leurs champs
                for row in champ.get("rows", []):
                    if "champs" in row:
                        for field in row["champs"]:
                            # NOUVEAU : Utiliser should_skip_field pour la cohérence
                            if should_skip_field_unified(field):
                                log_verbose(f"Champ ignoré dans la détection: {field.get('label', 'sans label')}")
                                continue

                            field_label = field["label"]
                            normalized_label = normalize_column_name(field_label)

                            # Déterminer le type de colonne
                            column_type = "Text"  # Type par défaut
                            if field["__typename"] in [
                                "DateChamp",
                                "DatetimeChamp"
                            ]:
                                column_type = "DateTime"
                            elif field["__typename"] in ["DecimalNumberChamp"]:
                                column_type = "Numeric"
                            elif field["__typename"] in ["IntegerNumberChamp"]:
                                column_type = "Int"
                            elif field["__typename"] in [
                                "CheckboxChamp",
                                "YesNoChamp"
                            ]:
                                column_type = "Bool"

                            # Ajouter la colonne si elle n'existe pas déjà
                            if normalized_label not in found_columns:
                                found_columns[normalized_label] = column_type

                            # Pour les types complexes, ajouter aussi une colonne JSON
                            if field["__typename"] in [
                                "CarteChamp",
                                "AddressChamp",
                                "SiretChamp",
                                "LinkedDropDownListChamp",
                                "MultipleDropDownListChamp",
                                "PieceJustificativeChamp",
                                "CommuneChamp",
                                "RNFChamp"
                            ]:
                                json_column = f"{normalized_label}_json"
                                if json_column not in found_columns:
                                    found_columns[json_column] = "Text"

        return found_columns

    # Explorer tous les champs du dossier
    found_columns = explore_champs(dossier_data.get("champs", []))

    # Explorer également les annotations
    if "annotations" in dossier_data:
        found_columns = explore_champs(
            dossier_data.get("annotations", []),
            found_columns
        )

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

            if col_id in all_columns:
                # Si le type est différent, prioriser certains types
                existing_type = all_columns[col_id]
                if existing_type == "Text" and col_type != "Text":
                    all_columns[col_id] = col_type
                elif existing_type == "Int" and col_type in [
                    "Numeric",
                    "DateTime"
                ]:
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
