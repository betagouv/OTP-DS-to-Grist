import json
from collections.abc import Iterator
from typing import Any, Dict, List

from dn.client import DISPLAY_CHAMP_TYPES
from dn.formatter import decode_base64_id
from grist.utils import normalize_column_name
from utils.formatter import format_json_value, unwrap_json_list


# Clé portant la valeur de chaque type de sous-colonne OCR d'une pièce
# justificative, telle que demandée par ChampFragment (alias pour les types
# non textuels). Les autres types, dont AttachmentsColumn (les fichiers), sont
# ignorés : seuls les noms de fichiers sont synchronisés.
PJ_OCR_VALUE_KEYS = {
    "TextColumn": "value",
    "EnumColumn": "value",
    "DateColumn": "dateValue",
    "IntegerColumn": "integerValue",
    "DecimalColumn": "decimalValue",
}


# Clé portant la valeur des types de champ à valeur simple, telle que demandée
# par ChampFragment (alias pour la plupart d'entre eux)
SCALAR_VALUE_KEYS = {
    "DateChamp": "date",
    "DatetimeChamp": "datetime",
    "CheckboxChamp": "checked",
    "YesNoChamp": "selected",
    "DecimalNumberChamp": "decimalNumber",
    "IntegerNumberChamp": "integerNumber",
    "CiviliteChamp": "civilite",
}

# Clé portant l'objet des champs territoriaux à nom et code (ex. `pays`)
TERRITORY_KEYS = {
    "PaysChamp": "pays",
    "RegionChamp": "region",
    "DepartementChamp": "departement",
}


def extract_champ_values(
    champ: Dict[str, Any], prefix: str = "", original_id: str = None
) -> List[Dict[str, Any]]:
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
    if champ["__typename"] in DISPLAY_CHAMP_TYPES:
        return []

    result = []

    # Si l'ID original n'est pas fourni, utiliser l'ID du champ
    if original_id is None:
        original_id = champ["id"]

    # Traitement spécial pour les champs répétables
    if champ["__typename"] == "RepetitionChamp":
        for i, row in enumerate(champ.get("rows", [])):
            row_prefix = f"{prefix}{champ['label']}_{i + 1}_"

            # Passage de l'ID du champ répétable comme contexte
            for row_champ in row.get("champs", []):
                result.extend(
                    extract_champ_values(
                        row_champ, row_prefix, row.get("id", original_id)
                    )
                )
        return result

    # Préparation de la valeur selon le type de champ
    value = None
    json_value = None

    # Traitement pour différents types de champs
    if champ["__typename"] in SCALAR_VALUE_KEYS:
        value = champ.get(SCALAR_VALUE_KEYS[champ["__typename"]])
    elif champ["__typename"] == "LinkedDropDownListChamp":
        primary = champ.get("primaryValue", "")
        secondary = champ.get("secondaryValue", "")
        value = (
            f"{primary} - {secondary}"
            if primary and secondary
            else primary or secondary
        )
        json_value = {"primaryValue": primary, "secondaryValue": secondary}
    elif champ["__typename"] == "MultipleDropDownListChamp":
        values_list = champ.get("values", [])
        if values_list:
            value = ", ".join(values_list)
        else:
            value = unwrap_json_list(champ.get("stringValue") or champ.get("value"))
        json_value = values_list
    elif champ["__typename"] == "DropDownListChamp":
        raw = champ.get("stringValue") or champ.get("value")
        value = unwrap_json_list(raw)
    elif champ["__typename"] == "PieceJustificativeChamp":
        files = champ.get("files", [])
        value = ", ".join([f["filename"] for f in files]) if files else None

        for col, full_label, col_value in iter_pj_ocr_columns(champ):
            result.append(
                _champ_entry(
                    champ,
                    prefix,
                    original_id,
                    entry_id=col.get("id"),
                    base_label=full_label,
                    entry_type=col["__typename"],
                    value=col_value,
                )
            )

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
        value = (
            f"{siret} - {raison_sociale}"
            if siret and raison_sociale
            else siret or raison_sociale
        )
        json_value = etablissement
    elif champ["__typename"] == "CarteChamp":
        # Traitement détaillé pour les champs Carte
        geo_areas = champ.get("geoAreas", [])
        if not geo_areas:
            value = "Aucune zone géographique définie"
            json_value = None
        else:
            # Une seule entrée pour TOUTES les zones : évite l'écrasement
            # (les entrées multiples partageaient le même label de colonne).
            # json_value porte la liste complète, pas une zone isolée.
            value = "; ".join(
                f"Zone {j + 1}: {geo_area.get('source', '')} - {geo_area.get('description', 'Sans description')}"
                for j, geo_area in enumerate(geo_areas)
            )
            json_value = geo_areas
    elif champ["__typename"] == "DossierLinkChamp" and champ.get("dossier"):
        # Traitement pour les liens vers d'autres dossiers
        linked_dossier = champ.get("dossier", {})
        dossier_number = linked_dossier.get("number", "")
        dossier_state = linked_dossier.get("state", "")
        value = (
            f"Dossier #{dossier_number} ({dossier_state})"
            if dossier_number
            else "Aucun dossier lié"
        )
        json_value = linked_dossier
    elif champ["__typename"] in TERRITORY_KEYS and champ.get(
        TERRITORY_KEYS[champ["__typename"]]
    ):
        # Traitement pour les pays, régions et départements
        territory = champ[TERRITORY_KEYS[champ["__typename"]]]
        name = territory.get("name", "")
        code = territory.get("code", "")
        value = f"{name} ({code})" if name and code else name or code
        json_value = territory

        # Ajouter le nom et le code comme champs séparés
        for suffix, sub_value in (("nom", name), ("code", code)):
            if sub_value:
                result.append(
                    _sub_column_entry(champ, prefix, original_id, suffix, sub_value)
                )

    elif champ["__typename"] == "CommuneChamp" and champ.get("commune"):
        commune = champ.get("commune", {})
        name = commune.get("name", "")
        code_insee = commune.get("code", "")
        postal_code = commune.get("postalCode", "")
        value = f"{name} ({postal_code})" if name and postal_code else name

        departement = champ.get("departement")
        dept_name = None
        dept_code = None
        if departement:
            dept_name = departement.get("name", "")
            dept_code = departement.get("code", "")
            value = (
                f"{value}, {dept_name}" if value and dept_name else value or dept_name
            )

        json_value = {"commune": commune}
        if departement:
            json_value["departement"] = departement

        # Sous-colonnes, dans l'ordre des colonnes déclarées par schema_utils
        for suffix, sub_value in (
            ("nom", name),
            ("code_postal", postal_code),
            ("departement", dept_name),
            ("code_insee", code_insee),
            ("code_departement", dept_code),
        ):
            if sub_value:
                result.append(
                    _sub_column_entry(champ, prefix, original_id, suffix, sub_value)
                )

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
            value = (
                f"{value}, {dept_name}" if value and dept_name else value or dept_name
            )

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
    elif champ["__typename"] == "EngagementJuridiqueChamp" and champ.get(
        "engagementJuridique"
    ):
        # Traitement pour les engagements juridiques
        engagement = champ.get("engagementJuridique", {})
        montant_engage = engagement.get("montantEngage")
        montant_paye = engagement.get("montantPaye")

        value = ""
        if montant_engage is not None:
            value = f"Montant engagé: {montant_engage}"
        if montant_paye is not None:
            value = (
                f"{value}, Montant payé: {montant_paye}"
                if value
                else f"Montant payé: {montant_paye}"
            )

        json_value = engagement
    else:
        # Pour les autres types, utiliser la valeur textuelle
        value = champ.get("stringValue")

    # Entrée principale, après les éventuelles sous-colonnes
    result.append(
        _champ_entry(
            champ,
            prefix,
            original_id,
            entry_id=champ["id"],
            base_label=champ["label"],
            entry_type=champ["__typename"],
            value=value,
            json_value=json_value,
            numeric_id=_numeric_id(champ["id"]),
        )
    )

    return result


def iter_pj_ocr_columns(
    champ: dict[str, Any],
) -> Iterator[tuple[dict[str, Any], str, Any]]:
    """
    Sous-colonnes OCR renseignées d'une pièce justificative :
    (colonne DN, libellé complet, valeur).

    DN libelle les sous-colonnes "<libellé du champ> – <sous-libellé>"
    (ex. "RIB – Nom de la Banque"). Le libellé complet repart du libellé du
    champ, pour que son nom normalisé corresponde à la colonne créée par
    schema_utils.
    """
    for col in champ.get("columns") or []:
        value_key = PJ_OCR_VALUE_KEYS.get(col.get("__typename"))
        if value_key is None:
            continue

        value = col.get(value_key)
        if value is None or value == "":
            continue

        yield col, f"{champ['label']} {pj_ocr_sub_label(col.get('label'))}", value


def pj_ocr_sub_label(column_label: str | None) -> str:
    """
    Sous-libellé d'une sous-colonne OCR : DN libelle les sous-colonnes
    "<libellé du champ> – <sous-libellé>" (ex. "RIB – Nom de la Banque").
    Partagé avec schema_utils pour que l'extraction et le schéma produisent
    le même id de colonne.
    """
    return (column_label or "").rsplit(" – ", 1)[-1]


def extract_repetable_blocks(
    dossier_data: Dict[str, Any], problematic_ids=None
) -> List[Dict[str, Any]]:
    """
    Extrait les données des blocs répétables dans un format de tableau.

    Args:
        dossier_data: Données du dossier récupérées via l'API
        problematic_ids: Set des IDs de descripteurs problématiques à filtrer

    Returns:
        Liste de dictionnaires représentant chaque ligne de bloc répétable
    """
    repetable_rows = []

    def process_repetable_champ(
        champ: Dict[str, Any], dossier_number: int, block_label: str
    ):
        """
        Traite un champ répétable et extrait ses données.
        """
        if champ["__typename"] == "RepetitionChamp":
            for row_index, row in enumerate(champ.get("rows", [])):
                row_data = {
                    "dossier_number": dossier_number,
                    "block_id": champ.get("id"),
                    "block_label": block_label,
                    "block_row_index": row_index + 1,
                    "block_row_id": row.get("id"),
                }

                # Compteur pour les doublons dans cette ligne
                row_label_counters = {}

                # Traiter chaque champ dans la rangée
                for row_champ in row.get("champs", []):
                    # ✅ FIX : Filtrer les champs problématiques dans les blocs répétables
                    if row_champ["__typename"] in [
                        "HeaderSectionChamp",
                        "ExplicationChamp",
                    ] or (
                        problematic_ids
                        and row_champ.get("champDescriptorId") in problematic_ids
                    ):
                        continue

                    # Extraire les valeurs du champ
                    champ_values = extract_champ_values(row_champ, "", row.get("id"))

                    # Ajouter chaque valeur de champ à la ligne avec gestion des doublons
                    for champ_value in champ_values:
                        base_label = champ_value["base_label"]
                        normalized = normalize_column_name(base_label)

                        # Gérer les doublons
                        if normalized in row_label_counters:
                            row_label_counters[normalized] += 1
                            final_label = (
                                f"{base_label}_{row_label_counters[normalized]}"
                            )
                        else:
                            row_label_counters[normalized] = 0
                            final_label = base_label

                        row_data[final_label] = champ_value["value"]

                        # Ajouter la valeur JSON si elle existe
                        if champ_value["json_value"] is not None:
                            row_data[f"{final_label}_json"] = (
                                format_json_value(champ_value["json_value"])
                            )

                repetable_rows.append(row_data)

    # Parcourir les champs du dossier
    for champ in dossier_data.get("champs", []):
        process_repetable_champ(champ, dossier_data["number"], champ["label"])

    # Parcourir les annotations (si nécessaire)
    for annotation in dossier_data.get("annotations", []):
        process_repetable_champ(
            annotation, dossier_data["number"], f"annotation_{annotation['label']}"
        )

    return repetable_rows


def extract_demandeur_info(dossier_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait les informations du demandeur dans un format structuré
    pour la table demandeurs séparée.

    Returns:
        Dictionnaire avec toutes les infos du demandeur
    """
    demandeur_info = {"dossier_number": dossier_data["number"]}

    # Informations communes à tous les types de demandeurs
    demandeur_info["usager_email"] = dossier_data.get("usager", {}).get("email", "")
    demandeur_info["prenom_mandataire"] = dossier_data.get("prenomMandataire", "")
    demandeur_info["nom_mandataire"] = dossier_data.get("nomMandataire", "")
    demandeur_info["depose_par_un_tiers"] = dossier_data.get("deposeParUnTiers", False)

    demandeur = dossier_data.get("demandeur", {})
    if not demandeur:
        return demandeur_info

    demandeur_type = demandeur.get("__typename", "")
    demandeur_info["type"] = demandeur_type

    # Extraction selon le type
    if demandeur_type == "PersonnePhysique":
        demandeur_info.update(
            {
                "civilite": demandeur.get("civilite"),
                "nom": demandeur.get("nom"),
                "prenom": demandeur.get("prenom"),
                "email": demandeur.get("email"),
            }
        )

    elif demandeur_type in ["PersonneMorale", "PersonneMoraleIncomplete"]:
        # Déjà géré dans grist_processor_working_all.py
        # On retourne juste le type et les infos communes
        pass

    return demandeur_info


def build_label_fields(labels: list[dict] | None) -> dict[str, str]:
    """Construit les colonnes label_names / labels_json à partir des labels d'un dossier.

    Un label sans couleur figure dans label_names mais pas dans labels_json.
    """
    if not labels:
        return {"label_names": "", "labels_json": ""}

    label_names = [label.get("name", "") for label in labels if label.get("name")]

    labels_with_colors = [
        {
            "id": label.get("id", ""),
            "name": label.get("name", ""),
            "color": label.get("color", ""),
        }
        for label in labels
        if label.get("name") and label.get("color")
    ]

    return {
        "label_names": ", ".join(label_names) if label_names else "",
        "labels_json": (
            json.dumps(labels_with_colors, ensure_ascii=False)
            if labels_with_colors
            else ""
        ),
    }


def dossier_to_flat_data(
    dossier_data: Dict[str, Any],
    exclude_repetition_champs=True,
    problematic_ids=None,
    descriptor_to_column_id=None,
) -> Dict[str, Any]:
    """
    Transforme les données d'un dossier en un format plat pour faciliter l'intégration.
    Version modifiée pour exclure les blocs répétables si demandé.

    Args:
        dossier_data: Données du dossier récupérées via l'API
        exclude_repetition_champs: Si True, exclut les blocs répétables des champs standards
        problematic_ids: Set des IDs de descripteurs problématiques à filtrer

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
        "date_derniere_modification_champs": dossier_data.get(
            "dateDerniereModificationChamps"
        ),
        "date_derniere_modification_annotations": dossier_data.get(
            "dateDerniereModificationAnnotations"
        ),
        "date_passage_en_construction": dossier_data.get("datePassageEnConstruction"),
        "date_passage_en_instruction": dossier_data.get("datePassageEnInstruction"),
        "date_expiration": dossier_data.get("dateExpiration"),
        "date_traitement": dossier_data.get("dateTraitement"),
        "date_suppression_par_usager": dossier_data.get("dateSuppressionParUsager"),
        "date_accuse_lecture": dossier_data.get("dateAccuseLectureAgreement"),
        "date_derniere_correction_en_attente": dossier_data.get(
            "dateDerniereCorrectionEnAttente"
        ),
    }

    # Email de l'instructeur ayant demandé la dernière correction
    correction_instructeur = None
    for traitement in dossier_data.get("traitements", []):
        if traitement.get("event") == "depose_correction_instructeur":
            correction_instructeur = traitement.get("emailAgentTraitant")
    flat_data["correction_instructeur"] = correction_instructeur

    # Ajouter les informations sur les labels (étiquettes)
    flat_data.update(build_label_fields(dossier_data.get("labels")))

    # Compteur pour gérer les doublons de labels
    label_counters = {}

    # Extraction des valeurs des champs, en filtrant les blocs répétables si demandé
    champ_values = []
    for champ in dossier_data.get("champs", []):
        # Ignorer les blocs répétables si exclude_repetition_champs est True
        if exclude_repetition_champs and champ["__typename"] == "RepetitionChamp":
            continue

        # ✅ FIX PRINCIPAL : Vérifier champDescriptorId au lieu de id
        # Ignorer les champs problématiques par type et par champDescriptorId
        if champ["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"] or (
            problematic_ids and champ.get("champDescriptorId") in problematic_ids
        ):
            continue

        # Extraire les valeurs
        extracted = extract_champ_values(champ)

        # Appliquer les suffixes pour les doublons
        for item in extracted:
            descriptor_id = item.get("descriptor_id")
            # N'utiliser le mapping que si un seul item correspond à ce descriptor_id
            # (les types multi-items comme CommuneChamp ont des base_label déjà distincts)
            if (
                descriptor_to_column_id
                and descriptor_id in descriptor_to_column_id
                and sum(1 for i in extracted if i.get("descriptor_id") == descriptor_id)
                == 1
            ):
                item["label"] = descriptor_to_column_id[descriptor_id]
            else:
                base_label = item["base_label"]
                normalized = normalize_column_name(base_label)
                if normalized not in label_counters:
                    label_counters[normalized] = {}
                descriptor_map = label_counters[normalized]
                if descriptor_id not in descriptor_map:
                    descriptor_map[descriptor_id] = len(descriptor_map)
                suffix = descriptor_map[descriptor_id]
                item["label"] = base_label if suffix == 0 else f"{base_label}_{suffix}"

        champ_values.extend(extracted)

    # Ajouter les annotations, également en filtrant les blocs répétables si demandé
    annotation_values = []
    annotation_label_counters = {}  # Compteur séparé pour les annotations

    for annotation in dossier_data.get("annotations", []):
        # Ignorer les blocs répétables si exclude_repetition_champs est True
        if exclude_repetition_champs and annotation["__typename"] == "RepetitionChamp":
            continue

        # ✅ FIX PRINCIPAL : Vérifier champDescriptorId au lieu de id
        # Ignorer explicitement les annotations de type HeaderSectionChamp et ExplicationChamp
        if annotation["__typename"] in ["HeaderSectionChamp", "ExplicationChamp"] or (
            problematic_ids and annotation.get("champDescriptorId") in problematic_ids
        ):
            continue

        # Extraire les valeurs
        extracted = extract_champ_values(annotation, prefix="annotation_")

        # Appliquer les suffixes pour les doublons
        for item in extracted:
            descriptor_id = item.get("descriptor_id")
            if descriptor_to_column_id and descriptor_id in descriptor_to_column_id:
                item["label"] = f"annotation_{descriptor_to_column_id[descriptor_id]}"
            else:
                base_label = item["base_label"]
                label_for_normalization = base_label
                if label_for_normalization.startswith("annotation_"):
                    label_for_normalization = label_for_normalization[11:]
                normalized = normalize_column_name(label_for_normalization)
                if normalized not in annotation_label_counters:
                    annotation_label_counters[normalized] = {}
                descriptor_map = annotation_label_counters[normalized]
                if descriptor_id not in descriptor_map:
                    descriptor_map[descriptor_id] = len(descriptor_map)
                suffix = descriptor_map[descriptor_id]
                base_with_prefix = (
                    base_label
                    if base_label.startswith("annotation_")
                    else f"annotation_{base_label}"
                )
                item["label"] = (
                    base_with_prefix if suffix == 0 else f"{base_with_prefix}_{suffix}"
                )

        annotation_values.extend(extracted)

    # Extraction des blocs répétables
    # ✅ FIX : Passer problematic_ids à extract_repetable_blocks
    repetable_rows = extract_repetable_blocks(
        dossier_data, problematic_ids=problematic_ids
    )
    # ✅ NOUVELLE LIGNE
    demandeur_info = extract_demandeur_info(dossier_data)

    return {
        "dossier": flat_data,
        "champs": champ_values,
        "annotations": annotation_values,
        "repetable_rows": repetable_rows,
        "demandeur": demandeur_info,
        "avis": extract_avis_from_dossier(dossier_data),
    }


def extract_avis_from_dossier(dossier_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrait les avis experts d'un dossier pour insertion dans Grist.
    """
    avis_list = dossier_data.get("avis", [])
    dossier_number = dossier_data.get("number")
    records = []

    for avis in avis_list:
        records.append(
            {
                "dossier_number": dossier_number,
                "avis_id": avis.get("id", ""),
                "instructeur_email": avis.get("claimant", {}).get("email", ""),
                "expert_email": avis.get("expert", {}).get("email", ""),
                "date_question": avis.get("dateQuestion", ""),
                "date_reponse": avis.get("dateReponse", "")
                if avis.get("reponse")
                else "",
                "question": avis.get("question", "") or "",
                "reponse": avis.get("reponse", "") or "",
            }
        )

    return records


# --- Helpers privés (module) ---


def _champ_entry(
    champ: dict[str, Any],
    prefix: str,
    original_id: str,
    *,
    entry_id: str,
    base_label: str,
    entry_type: str,
    value: Any,
    json_value: Any = None,
    numeric_id: str | None = None,
) -> dict[str, Any]:
    """Entrée extraite d'un champ : sa valeur principale ou l'une de ses sous-colonnes."""
    return {
        "id": entry_id,
        "numeric_id": numeric_id,
        "descriptor_id": champ.get("champDescriptorId"),
        "decoded_descriptor_id": (
            decode_base64_id(champ.get("champDescriptorId", ""))
            if "champDescriptorId" in champ
            else None
        ),
        "label": f"{prefix}{base_label}",
        "base_label": base_label,  # Label sans préfixe de bloc répétable
        "type": entry_type,
        "value": value,
        "json_value": json_value,
        "updated_at": champ.get("updatedAt"),
        "prefilled": champ.get("prefilled", False),
        # ID de la rangée pour les blocs répétables
        "row_id": original_id if original_id != champ["id"] else None,
    }


def _sub_column_entry(
    champ: dict[str, Any], prefix: str, original_id: str, suffix: str, value: str
) -> dict[str, Any]:
    """Sous-colonne texte d'un champ, suffixée à son libellé (ex. `Commune_nom`)."""
    return _champ_entry(
        champ,
        prefix,
        original_id,
        entry_id=f"{champ['id']}_{suffix}",
        base_label=f"{champ['label']}_{suffix}",
        entry_type="TextColumn",
        value=value,
    )


def _numeric_id(raw_id: str) -> str | None:
    """ID numérique d'un champ, extrait d'un ID au format chemin ou base64."""
    if "/" in raw_id:
        parts = raw_id.split("/")
        if len(parts) >= 4 and parts[-2] == "Champ":
            return parts[-1]
        return None
    return decode_base64_id(raw_id)
