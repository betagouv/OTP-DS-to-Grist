import base64
import json
from typing import Dict, Any, List

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

def extract_champ_values(champ: Dict[str, Any], prefix: str = "", original_id: str = None) -> List[Dict[str, Any]]:
    """
    Extrait les valeurs d'un champ, y compris les champs répétables.
    Gère tous les types de champs spécifiques de l'API Démarches Simplifiées.
    
    Args:
        champ: Dictionnaire contenant les données du champ
        prefix: Préfixe pour les noms de champ (utilisé pour les champs répétables)
        original_id: ID original du champ (pour les blocs répétables)
        
    Returns:
        Liste de dictionnaires contenant les valeurs extraites
    """
    # Ignorer immédiatement les types HeaderSectionChamp et ExplicationChamp
    if champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"]:
        return []
        
    result = []
    
    # Si l'ID original n'est pas fourni, utiliser l'ID du champ
    if original_id is None:
        original_id = champ["id"]
    
    # Décodage de l'ID du descripteur pour correspondance
    decoded_descriptor_id = decode_base64_id(champ.get("champDescriptorId", "")) if "champDescriptorId" in champ else None
    
    # Traitement spécial pour les champs répétables
    if champ["__typename"] == "RepetitionChamp":
        for i, row in enumerate(champ.get("rows", [])):
            row_prefix = f"{prefix}{champ['label']}_{i+1}_"
            
            # Pour chaque champ dans la rangée
            for row_champ in row.get("champs", []):
                # Ignorer les types HeaderSectionChamp et ExplicationChamp dans les rangées
                if row_champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"]:
                    continue
                    
                # Passage de l'ID du champ répétable comme contexte
                row_results = extract_champ_values(row_champ, row_prefix, row.get("id", original_id))
                result.extend(row_results)
    else:
        # Préparation de la valeur selon le type de champ
        value = None
        json_value = None
        
        # Traitement pour différents types de champs
        if champ["__typename"] == "DateChamp":
            value = champ.get("date")
        elif champ["__typename"] == "DatetimeChamp":
            value = champ.get("datetime")
        elif champ["__typename"] == "CheckboxChamp":
            value = champ.get("checked")
        elif champ["__typename"] == "YesNoChamp":
            value = champ.get("selected")
        elif champ["__typename"] == "DecimalNumberChamp":
            value = champ.get("decimalNumber")
        elif champ["__typename"] == "IntegerNumberChamp":
            value = champ.get("integerNumber")
        elif champ["__typename"] == "CiviliteChamp":
            value = champ.get("civilite")
        elif champ["__typename"] == "LinkedDropDownListChamp":
            primary = champ.get('primaryValue', '')
            secondary = champ.get('secondaryValue', '')
            value = f"{primary} - {secondary}" if primary and secondary else primary or secondary
            json_value = {"primaryValue": primary, "secondaryValue": secondary}
        elif champ["__typename"] == "MultipleDropDownListChamp":
            values_list = champ.get("values", [])
            value = ", ".join(values_list) if values_list else None
            json_value = values_list
        elif champ["__typename"] == "DropDownListChamp":
            value = champ.get("stringValue")
        elif champ["__typename"] == "PieceJustificativeChamp":
            files = champ.get("files", [])
            value = ", ".join([f['filename'] for f in files]) if files else None
            json_value = files
        elif champ["__typename"] == "AddressChamp" and champ.get("address"):
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
        elif champ["__typename"] == "SiretChamp" and champ.get("etablissement"):
            etablissement = champ.get("etablissement", {})
            raison_sociale = etablissement.get("entreprise", {}).get("raisonSociale", "")
            siret = etablissement.get("siret", "")
            value = f"{siret} - {raison_sociale}" if siret and raison_sociale else siret or raison_sociale
            json_value = etablissement
        elif champ["__typename"] == "CarteChamp":
            # Traitement détaillé pour les champs Carte
            geo_areas = champ.get("geoAreas", [])
            
            # Si pas de zones géographiques, retourner un résultat minimal
            if not geo_areas:
                result.append({
                    "id": champ["id"],
                    "numeric_id": decode_base64_id(champ["id"]),
                    "descriptor_id": champ.get("champDescriptorId"),
                    "decoded_descriptor_id": decoded_descriptor_id,
                    "label": f"{prefix}{champ['label']}",
                    "base_label": champ['label'],
                    "type": champ["__typename"],
                    "value": "Aucune zone géographique définie",
                    "json_value": None,
                    "updated_at": champ.get("updatedAt"),
                    "prefilled": champ.get("prefilled", False),
                    "row_id": original_id if original_id != champ["id"] else None
                })
            else:
                # Créer des entrées séparées pour chaque zone géographique
                for j, geo_area in enumerate(geo_areas):
                    geo_result = {
                        "id": champ["id"],
                        "numeric_id": decode_base64_id(champ["id"]),
                        "descriptor_id": champ.get("champDescriptorId"),
                        "decoded_descriptor_id": decoded_descriptor_id,
                        "label": f"{prefix}{champ['label']}",
                        "base_label": champ['label'],
                        "type": champ["__typename"],
                        
                        # Champs spécifiques à la zone géographique
                        "geo_area_id": geo_area.get("id"),
                        "geo_area_source": geo_area.get("source"),
                        "geo_area_description": geo_area.get("description"),
                        "geo_area_geometry_type": geo_area.get("geometry", {}).get("type"),
                        "geo_area_geometry_coordinates": json.dumps(geo_area.get("geometry", {}).get("coordinates")) if geo_area.get("geometry") else None,
                        
                        # Informations supplémentaires pour les parcelles cadastrales
                        "parcelle_commune": geo_area.get("commune"),
                        "parcelle_numero": geo_area.get("numero"),
                        "parcelle_section": geo_area.get("section"),
                        "parcelle_prefixe": geo_area.get("prefixe"),
                        "parcelle_surface": geo_area.get("surface"),
                        
                        # Valeur textuelle pour compatibilité
                        "value": f"Zone {j+1}: {geo_area.get('source', '')} - {geo_area.get('description', 'Sans description')}",
                        "json_value": geo_area,
                        "updated_at": champ.get("updatedAt"),
                        "prefilled": champ.get("prefilled", False),
                        "row_id": original_id if original_id != champ["id"] else None
                    }
                    result.append(geo_result)
        elif champ["__typename"] == "DossierLinkChamp" and champ.get("dossier"):
            # Traitement pour les liens vers d'autres dossiers
            linked_dossier = champ.get("dossier", {})
            dossier_number = linked_dossier.get("number", "")
            dossier_state = linked_dossier.get("state", "")
            value = f"Dossier #{dossier_number} ({dossier_state})" if dossier_number else "Aucun dossier lié"
            json_value = linked_dossier
        elif champ["__typename"] == "PaysChamp" and champ.get("pays"):
            # Traitement pour les pays
            pays = champ.get("pays", {})
            name = pays.get("name", "")
            code = pays.get("code", "")
            value = f"{name} ({code})" if name and code else name or code
            json_value = pays
        elif champ["__typename"] == "RegionChamp" and champ.get("region"):
            # Traitement pour les régions
            region = champ.get("region", {})
            name = region.get("name", "")
            code = region.get("code", "")
            value = f"{name} ({code})" if name and code else name or code
            json_value = region
        elif champ["__typename"] == "DepartementChamp" and champ.get("departement"):
            # Traitement pour les départements
            departement = champ.get("departement", {})
            name = departement.get("name", "")
            code = departement.get("code", "")
            value = f"{name} ({code})" if name and code else name or code
            json_value = departement
        elif champ["__typename"] == "CommuneChamp" and champ.get("commune"):
            # Traitement pour les communes
            commune = champ.get("commune", {})
            name = commune.get("name", "")
            code = commune.get("code", "")
            postal_code = commune.get("postalCode", "")
            value = f"{name} ({postal_code or code})" if name else ""
            
            # Ajouter le département si disponible
            departement = champ.get("departement")
            if departement:
                dept_name = departement.get("name", "")
                value = f"{value}, {dept_name}" if value and dept_name else value or dept_name
                
            json_value = {"commune": commune}
            if departement:
                json_value["departement"] = departement
        elif champ["__typename"] == "EpciChamp" and champ.get("epci"):
            # Traitement pour les EPCI
            epci = champ.get("epci", {})
            name = epci.get("name", "")
            code = epci.get("code", "")
            value = f"{name} ({code})" if name and code else name or code
            
            # Ajouter le département si disponible
            departement = champ.get("departement")
            if departement:
                dept_name = departement.get("name", "")
                value = f"{value}, {dept_name}" if value and dept_name else value or dept_name
                
            json_value = {"epci": epci}
            if departement:
                json_value["departement"] = departement
        elif champ["__typename"] == "RNFChamp" and champ.get("rnf"):
            # Traitement pour les RNF
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
                
            # Ajouter commune et département si disponibles
            commune = champ.get("commune")
            departement = champ.get("departement")
            
            json_value = {"rnf": rnf}
            if commune:
                json_value["commune"] = commune
            if departement:
                json_value["departement"] = departement
        elif champ["__typename"] == "EngagementJuridiqueChamp" and champ.get("engagementJuridique"):
            # Traitement pour les engagements juridiques
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
        
        # Ne pas ajouter de résultat pour les types HeaderSectionChamp et ExplicationChamp 
        # (redondant car déjà filtré au début, mais mieux vaut être prudent)
        if champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"]:
            return result
            
        # Extraction des identifiants pour correspondance
        raw_id = champ["id"]
        numeric_id = None
        
        # Tentative d'extraction d'un ID numérique
        if "/" in raw_id:
            parts = raw_id.split("/")
            if len(parts) >= 4 and parts[-2] == "Champ":
                numeric_id = parts[-1]
        else:
            numeric_id = decode_base64_id(raw_id)
        
        # Ajout du résultat
        result.append({
            "id": raw_id,
            "numeric_id": numeric_id,
            "descriptor_id": champ.get("champDescriptorId"),
            "decoded_descriptor_id": decoded_descriptor_id,
            "label": f"{prefix}{champ['label']}",
            "base_label": champ['label'],  # Label sans préfixe de bloc répétable
            "type": champ["__typename"],
            "value": value,
            "json_value": json_value,
            "updated_at": champ.get("updatedAt"),
            "prefilled": champ.get("prefilled", False),
            "row_id": original_id if original_id != champ["id"] else None  # ID de la rangée pour les blocs répétables
        })
    
    return result

def extract_repetable_blocks(dossier_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrait les données des blocs répétables dans un format de tableau.
    
    Args:
        dossier_data: Données du dossier récupérées via l'API
        
    Returns:
        Liste de dictionnaires représentant chaque ligne de bloc répétable
    """
    repetable_rows = []
    
    def process_repetable_champ(champ: Dict[str, Any], dossier_number: int, block_label: str):
        """
        Traite un champ répétable et extrait ses données.
        """
        if champ["__typename"] == "RepetitionChamp":
            for row_index, row in enumerate(champ.get("rows", [])):
                row_data = {
                    "dossier_number": dossier_number,
                    "block_label": block_label,
                    "block_row_index": row_index + 1,
                    "block_row_id": row.get("id")
                }
                
                # Traiter chaque champ dans la rangée
                for row_champ in row.get("champs", []):
                    # Extraire les valeurs du champ
                    champ_values = extract_champ_values(row_champ, "", row.get("id"))
                    
                    # Ajouter chaque valeur de champ à la ligne
                    for champ_value in champ_values:
                        row_data[champ_value["label"]] = champ_value["value"]
                        
                        # Ajouter la valeur JSON si elle existe
                        if champ_value["json_value"] is not None:
                            row_data[f"{champ_value['label']}_json"] = format_complex_json_for_grist(champ_value["json_value"])
                
                repetable_rows.append(row_data)
    
    # Parcourir les champs du dossier
    for champ in dossier_data.get("champs", []):
        process_repetable_champ(champ, dossier_data["number"], champ["label"])
    
    # Parcourir les annotations (si nécessaire)
    for annotation in dossier_data.get("annotations", []):
        process_repetable_champ(annotation, dossier_data["number"], f"annotation_{annotation['label']}")
    
    return repetable_rows

def dossier_to_flat_data(dossier_data: Dict[str, Any], exclude_repetition_champs=True, problematic_ids=None) -> Dict[str, Any]:
    """
    Transforme les données d'un dossier en un format plat pour faciliter l'intégration.
    Version modifiée pour exclure les blocs répétables si demandé.
    
    Args:
        dossier_data: Données du dossier récupérées via l'API
        exclude_repetition_champs: Si True, exclut les blocs répétables des champs standards
        
    Returns:
        Dictionnaire avec les données du dossier en format plat
    """
    # Informations de base du dossier
    flat_data = {
        "dossier_id": dossier_data["id"],
        "dossier_number": dossier_data["number"],
        "dossier_state": dossier_data["state"],
        "date_depot": dossier_data.get("dateDepot"),
        "date_derniere_modification": dossier_data.get("dateDerniereModification"),
        "date_traitement": dossier_data.get("dateTraitement"),
        "date_suppression_par_usager": dossier_data.get("dateSuppressionParUsager"),
        "usager_email": dossier_data.get("usager", {}).get("email"),
        "prenom_mandataire": dossier_data.get("prenomMandataire"),
        "nom_mandataire": dossier_data.get("nomMandataire"),
        "depose_par_un_tiers": dossier_data.get("deposeParUnTiers", False),
    }
    # Ajouter les informations sur les labels (étiquettes)
    if "labels" in dossier_data and dossier_data["labels"]:
        # Création d'une liste des noms de labels
        label_names = [label.get("name", "") for label in dossier_data["labels"] if label.get("name")]
        flat_data["label_names"] = ", ".join(label_names) if label_names else ""
        
        # Création d'une représentation JSON des labels avec couleurs
        labels_with_colors = []
        for label in dossier_data["labels"]:
            if label.get("name") and label.get("color"):
                labels_with_colors.append({
                    "id": label.get("id", ""),
                    "name": label.get("name", ""),
                    "color": label.get("color", "")
                })
        
        if labels_with_colors:
            import json
            flat_data["labels_json"] = json.dumps(labels_with_colors, ensure_ascii=False)
        else:
            flat_data["labels_json"] = ""

    # Ajouter les informations du groupe instructeur
    groupe_instructeur = dossier_data.get("groupeInstructeur", {})
    if groupe_instructeur:
        flat_data.update({
            "groupe_instructeur_id": groupe_instructeur.get("id"),
            "groupe_instructeur_number": groupe_instructeur.get("number"),
            "groupe_instructeur_label": groupe_instructeur.get("label"),
        })
    
    # Informations du demandeur
    demandeur = dossier_data.get("demandeur", {})
    if demandeur:
        if demandeur.get("__typename") == "PersonnePhysique":
            flat_data.update({
                "demandeur_type": "PersonnePhysique",
                "demandeur_civilite": demandeur.get("civilite"),
                "demandeur_nom": demandeur.get("nom"),
                "demandeur_prenom": demandeur.get("prenom"),
                "demandeur_email": demandeur.get("email"),
            })
    
        elif demandeur.get("__typename") in ["PersonneMorale", "PersonneMoraleIncomplete"]:
            flat_data.update({
                "demandeur_type": demandeur.get("__typename"),
                "demandeur_siret": demandeur.get("siret"),
                "demandeur_siege_social": demandeur.get("siegeSocial"),
                "demandeur_naf": demandeur.get("naf"),
                "demandeur_libelle_naf": demandeur.get("libelleNaf"),
            })
            
            # Entreprise
            entreprise = demandeur.get("entreprise", {})
            if entreprise:
                flat_data.update({
                    "entreprise_siren": entreprise.get("siren"),
                    "entreprise_raison_sociale": entreprise.get("raisonSociale"),
                    "entreprise_nom_commercial": entreprise.get("nomCommercial"),
                })
    
    # Extraction des valeurs des champs, en filtrant les blocs répétables si demandé
    champ_values = []
    for champ in dossier_data.get("champs", []):
        # Ignorer les blocs répétables si exclude_repetition_champs est True
        if exclude_repetition_champs and champ["__typename"] == "RepetitionChamp":
            continue
        # Ignorer les champs problématiques par type et par ID
        if (champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"] or 
            (problematic_ids and champ.get("id") in problematic_ids)):
            continue
        champ_values.extend(extract_champ_values(champ))
    
    # Ajouter les annotations, également en filtrant les blocs répétables si demandé
    annotation_values = []
    for annotation in dossier_data.get("annotations", []):
        # Ignorer les blocs répétables si exclude_repetition_champs est True
        if exclude_repetition_champs and annotation["__typename"] == "RepetitionChamp":
            continue
        # Ignorer explicitement les annotations de type HeaderSectionChamp et ExplicationChamp
        if annotation["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"]:
            continue
        annotation_values.extend(extract_champ_values(annotation, prefix="annotation_"))
    
    # Extraction des blocs répétables - cette partie reste inchangée
    # car nous aurons toujours besoin de ces données pour la table des blocs répétables
    repetable_rows = extract_repetable_blocks(dossier_data)
    
    return {
        "dossier": flat_data,
        "champs": champ_values,
        "annotations": annotation_values,
        "repetable_rows": repetable_rows
    }