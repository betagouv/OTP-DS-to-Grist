from queries_extract import dossier_to_flat_data, extract_champ_values
from schema_utils import create_columns_from_schema


def make_champ(label, typename, descriptor_id, value=None, checked=None, selected=None):
    """Fabrique un champ DS minimal."""
    champ = {
        "__typename": typename,
        "id": f"id_{descriptor_id}",
        "champDescriptorId": descriptor_id,
        "label": label,
        "updatedAt": "2024-01-01T00:00:00Z",
        "prefilled": False,
    }
    if typename == "TextChamp":
        champ["stringValue"] = value or ""
    elif typename == "CheckboxChamp":
        champ["checked"] = checked if checked is not None else False
    elif typename == "YesNoChamp":
        champ["selected"] = selected
    return champ


def make_dossier(champs, annotations=None):
    """Fabrique un dossier DS minimal."""
    return {
        "id": "dossier_1",
        "number": 1,
        "state": "accepte",
        "dateDepot": "2024-01-01T00:00:00Z",
        "dateDerniereModification": "2024-01-01T00:00:00Z",
        "dateDerniereModificationChamps": None,
        "dateDerniereModificationAnnotations": None,
        "datePassageEnConstruction": None,
        "datePassageEnInstruction": None,
        "dateExpiration": None,
        "dateTraitement": None,
        "dateSuppressionParUsager": None,
        "dateAccuseLectureAgreement": None,
        "labels": [],
        "champs": champs,
        "annotations": annotations or [],
        "avis": [],
        "usager": {"email": "test@test.fr"},
        "demandeur": None,
        "prenomMandataire": "",
        "nomMandataire": "",
        "deposeParUnTiers": False,
    }


def make_schema_with_duplicate_labels():
    """Fabrique un schéma DS minimal avec deux champs de même label."""
    return {
        "title": "Test démarche",
        "activeRevision": {
            "champDescriptors": [
                {
                    "__typename": "TextChampDescriptor",
                    "id": "desc_001",
                    "type": "text",
                    "label": "Nom",
                    "description": "",
                    "required": False,
                },
                {
                    "__typename": "TextChampDescriptor",
                    "id": "desc_002",
                    "type": "text",
                    "label": "Nom",
                    "description": "",
                    "required": False,
                },
            ],
            "annotationDescriptors": [],
        },
    }


class TestCreateColumnsFromSchemaDescriptorMapping:
    """Tests sur la construction du mapping descriptor_to_column_id."""

    def test_duplicate_labels_produce_distinct_column_ids(self):
        """Deux descripteurs de même label → colonnes distinctes dans le mapping."""
        schema = make_schema_with_duplicate_labels()
        column_types, _ = create_columns_from_schema(schema)

        mapping = column_types.get("descriptor_to_column_id", {})
        assert "desc_001" in mapping
        assert "desc_002" in mapping
        assert mapping["desc_001"] != mapping["desc_002"]

    def test_mapping_used_correctly_in_flat_data(self):
        """Le mapping produit par create_columns_from_schema est utilisé stablement."""
        schema = make_schema_with_duplicate_labels()
        column_types, _ = create_columns_from_schema(schema)
        descriptor_to_column_id = column_types["descriptor_to_column_id"]

        # Dossier A : desc_001 en premier
        dossier_a = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
            ]
        )
        flat_a = dossier_to_flat_data(
            dossier_a,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        labels_a = {item["label"]: item["value"] for item in flat_a["champs"]}

        # Dossier B : desc_002 en premier
        dossier_b = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
            ]
        )
        flat_b = dossier_to_flat_data(
            dossier_b,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        labels_b = {item["label"]: item["value"] for item in flat_b["champs"]}

        col_001 = descriptor_to_column_id["desc_001"]
        col_002 = descriptor_to_column_id["desc_002"]

        assert labels_a.get(col_001) == "Martin"
        assert labels_b.get(col_001) == "Martin"
        assert labels_a.get(col_002) == "Dupont"
        assert labels_b.get(col_002) == "Dupont"


class TestDossierToFlatDataDuplicateLabels:
    """Tests sur la gestion des champs en doublon dans dossier_to_flat_data."""

    def _get_labels(self, dossier, descriptor_to_column_id=None):
        flat = dossier_to_flat_data(
            dossier,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        return [item["label"] for item in flat["champs"]]

    def test_no_duplicate_no_suffix(self):
        """Un champ unique ne doit pas être suffixé."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Nom_1" not in labels

    def test_two_duplicates_get_suffixes(self):
        """Deux champs avec le même label → premier sans suffixe, second avec _1."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Nom_1" in labels

    def test_suffix_stable_regardless_of_order(self):
        """
        Avec le mapping du schéma DS, desc_001 → "Nom" et desc_002 → "Nom_1"
        quel que soit l'ordre d'apparition dans les dossiers.
        """
        descriptor_to_column_id = {
            "desc_001": "Nom",
            "desc_002": "Nom_1",
        }

        dossier_a = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
            ]
        )
        flat_a = dossier_to_flat_data(
            dossier_a,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        labels_a = {item["label"]: item["value"] for item in flat_a["champs"]}

        dossier_b = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_002", value="Dupont"),
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
            ]
        )
        flat_b = dossier_to_flat_data(
            dossier_b,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        labels_b = {item["label"]: item["value"] for item in flat_b["champs"]}

        assert labels_a.get("Nom") == "Martin"
        assert labels_b.get("Nom") == "Martin"
        assert labels_a.get("Nom_1") == "Dupont"
        assert labels_b.get("Nom_1") == "Dupont"

    def test_three_duplicates(self):
        """Trois champs identiques → Nom, Nom_1, Nom_2."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="A"),
                make_champ("Nom", "TextChamp", "desc_002", value="B"),
                make_champ("Nom", "TextChamp", "desc_003", value="C"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Nom_1" in labels
        assert "Nom_2" in labels

    def test_different_labels_not_affected(self):
        """Des champs avec des labels différents ne doivent pas être suffixés."""
        dossier = make_dossier(
            [
                make_champ("Nom", "TextChamp", "desc_001", value="Martin"),
                make_champ("Prénom", "TextChamp", "desc_002", value="Jean"),
            ]
        )
        labels = self._get_labels(dossier)
        assert "Nom" in labels
        assert "Prénom" in labels
        assert "Nom_1" not in labels
        assert "Prénom_1" not in labels

    def test_annotation_duplicates_fallback(self):
        """Les annotations en doublon sont gérées par le fallback (sans mapping schéma)."""
        dossier = make_dossier(
            champs=[],
            annotations=[
                make_champ("Avis", "TextChamp", "desc_010", value="OK"),
                make_champ("Avis", "TextChamp", "desc_011", value="KO"),
            ],
        )
        flat = dossier_to_flat_data(dossier, exclude_repetition_champs=True)
        labels = [item["label"] for item in flat["annotations"]]
        assert "annotation_Avis" in labels
        assert "annotation_Avis_1" in labels

    def test_annotation_duplicates_with_mapping(self):
        """Les annotations en doublon sont stables via le mapping schéma."""
        descriptor_to_column_id = {
            "desc_010": "Avis",
            "desc_011": "Avis_1",
        }
        dossier = make_dossier(
            champs=[],
            annotations=[
                make_champ("Avis", "TextChamp", "desc_011", value="KO"),
                make_champ("Avis", "TextChamp", "desc_010", value="OK"),
            ],
        )
        flat = dossier_to_flat_data(
            dossier,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )
        labels = {item["label"]: item["value"] for item in flat["annotations"]}
        assert labels.get("annotation_Avis") == "OK"
        assert labels.get("annotation_Avis_1") == "KO"


# ---------------------------------------------------------------------------
# Tests CarteChamp (champs carto top-level)
#
# Bug corrigé : un append inconditionnel en fin de extract_champ_values
# ajoutait une entrée fantôme (value=None, json_value=None) après chaque
# champ CarteChamp top-level, écrasant systématiquement la colonne dans
# Grist lors du sync, quel que soit le nombre de zones dessinées.
# ---------------------------------------------------------------------------


def make_carte_champ(geo_areas, label="Localisation"):
    return {
        "__typename": "CarteChamp",
        "id": "Q2FydGVDaGFtcC0xMjM0NQ==",
        "label": label,
        "champDescriptorId": "Q2hhbXBEZXNjcmlwdG9yLTk5",
        "updatedAt": "2026-01-01T00:00:00Z",
        "prefilled": False,
        "geoAreas": geo_areas,
    }


def make_geo_zone(zone_id, source="selection_utilisateur", description="zone", **extra):
    zone = {
        "id": zone_id,
        "source": source,
        "description": description,
        "geometry": {"type": "Point", "coordinates": [2.88, 42.69]},
    }
    zone.update(extra)
    return zone


class TestCarteChampSansZone:
    def test_une_seule_entree(self):
        champ = make_carte_champ([])
        result = extract_champ_values(champ)
        assert len(result) == 1

    def test_valeur_par_defaut(self):
        champ = make_carte_champ([])
        result = extract_champ_values(champ)
        assert result[0]["value"] == "Aucune zone géographique définie"
        assert result[0]["json_value"] is None


class TestCarteChampUneZone:
    def test_une_seule_entree(self):
        champ = make_carte_champ([make_geo_zone("GeoArea-1", description="Parcelle A")])
        result = extract_champ_values(champ)
        assert len(result) == 1

    def test_json_value_est_une_liste(self):
        zone = make_geo_zone("GeoArea-1", description="Parcelle A")
        champ = make_carte_champ([zone])
        result = extract_champ_values(champ)
        assert result[0]["json_value"] == [zone]

    def test_value_contient_la_description(self):
        champ = make_carte_champ(
            [make_geo_zone("GeoArea-1", source="cadastre", description="Parcelle A")]
        )
        result = extract_champ_values(champ)
        assert "Parcelle A" in result[0]["value"]
        assert "cadastre" in result[0]["value"]


class TestCarteChampPlusieursZones:
    def test_une_seule_entree_pas_ecrasement(self):
        zones = [
            make_geo_zone("GeoArea-1", description="Point"),
            make_geo_zone("GeoArea-2", description="Ligne"),
            make_geo_zone("GeoArea-3", description="Polygone"),
        ]
        champ = make_carte_champ(zones)
        result = extract_champ_values(champ)
        assert len(result) == 1

    def test_json_value_contient_toutes_les_zones(self):
        zones = [
            make_geo_zone("GeoArea-1", description="Point"),
            make_geo_zone("GeoArea-2", description="Ligne"),
            make_geo_zone("GeoArea-3", description="Polygone"),
        ]
        champ = make_carte_champ(zones)
        result = extract_champ_values(champ)
        assert result[0]["json_value"] == zones
        assert len(result[0]["json_value"]) == 3

    def test_value_resume_toutes_les_zones(self):
        zones = [
            make_geo_zone("GeoArea-1", description="Point"),
            make_geo_zone("GeoArea-2", description="Ligne"),
        ]
        champ = make_carte_champ(zones)
        result = extract_champ_values(champ)
        assert "Zone 1" in result[0]["value"]
        assert "Zone 2" in result[0]["value"]
        assert "Point" in result[0]["value"]
        assert "Ligne" in result[0]["value"]

    def test_meme_label_pour_toutes_les_entrees_du_champ(self):
        zones = [make_geo_zone("GeoArea-1"), make_geo_zone("GeoArea-2")]
        champ = make_carte_champ(zones, label="Ma zone")
        result = extract_champ_values(champ)
        assert result[0]["label"] == "Ma zone"


class TestCarteChampCasCadastre:
    def test_donnees_cadastrales_preservees_dans_json_value(self):
        zone = make_geo_zone(
            "GeoArea-1",
            source="cadastre",
            description="parcelle",
            commune="66136",
            numero="813",
            section="BE",
            prefixe="000",
            surface="668",
        )
        champ = make_carte_champ([zone])
        result = extract_champ_values(champ)
        zones_out = result[0]["json_value"]
        assert zones_out[0]["commune"] == "66136"
        assert zones_out[0]["numero"] == "813"
        assert zones_out[0]["surface"] == "668"
