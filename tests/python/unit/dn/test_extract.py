import pytest

from dn.extract import decode_base64_id, dossier_to_flat_data, extract_repetable_blocks
from schema_utils import create_columns_from_schema


def test_decode_base64_id_valid():
    encoded = "Q2hhbXAtMTIz"
    assert decode_base64_id(encoded) == "123"


def test_decode_base64_id_invalid():
    assert decode_base64_id("invalid") == "invalid"


def test_decode_base64_id_graphql():
    encoded = "Q2hhbXA6MTIz"
    assert decode_base64_id(encoded) == "123"


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


class TestNumberedLabelCoherence:
    """
    Vérifie la cohérence des IDs de colonnes entre la création de schéma
    et l'extraction de données, notamment pour les labels numérotés.

    Le schéma utilise label_to_column_id (sans stripping des numéros),
    tandis que le fallback de dossier_to_flat_data produit le label brut.
    La cohérence est assurée via descriptor_to_column_id.
    """

    def _make_numbered_schema(self):
        """Schéma avec labels numérotés typiques DS."""
        return {
            "title": "Démarche test",
            "activeRevision": {
                "champDescriptors": [
                    {
                        "__typename": "TextChampDescriptor",
                        "id": "desc_1",
                        "type": "text",
                        "label": "1. Nom du champ",
                        "description": "",
                        "required": False,
                    },
                    {
                        "__typename": "TextChampDescriptor",
                        "id": "desc_2",
                        "type": "text",
                        "label": "2) Prénom",
                        "description": "",
                        "required": False,
                    },
                ],
                "annotationDescriptors": [],
            },
        }

    def test_schema_creates_prefixed_column_ids(self):
        """create_columns_from_schema préserve les numéros → col_ préfixé."""
        schema = self._make_numbered_schema()
        column_types, _ = create_columns_from_schema(schema)

        champ_ids = {c["id"] for c in column_types["champs"]}
        assert "col_1_nom_du_champ" in champ_ids
        assert "col_2_prenom" in champ_ids

    def test_flat_data_uses_descriptor_mapping(self):
        """dossier_to_flat_data utilise descriptor_to_column_id → cohérent avec le schéma."""
        schema = self._make_numbered_schema()
        column_types, _ = create_columns_from_schema(schema)
        descriptor_to_column_id = column_types["descriptor_to_column_id"]

        dossier = make_dossier(
            [
                make_champ("1. Nom du champ", "TextChamp", "desc_1", value="Martin"),
                make_champ("2) Prénom", "TextChamp", "desc_2", value="Jean"),
            ]
        )
        flat = dossier_to_flat_data(
            dossier,
            exclude_repetition_champs=True,
            descriptor_to_column_id=descriptor_to_column_id,
        )

        labels = {item["label"]: item["value"] for item in flat["champs"]}
        assert labels.get("col_1_nom_du_champ") == "Martin"
        assert labels.get("col_2_prenom") == "Jean"

    @pytest.mark.xfail(
        reason="Fallback produit le label brut (base_label), pas l'ID normalisé — problème de conception séparé de 6a.6"
    )
    def test_fallback_normalization_incohérent_avec_schema(self):
        """Le fallback de dossier_to_flat_data produit des labels incohérents avec le schéma.

        Sans descriptor_to_column_id, dossier_to_flat_data utilise
        ds_label_to_column_id pour la détection de doublons, mais utilise
        le base_label brut comme clé de label.

        Le schéma crée la colonne "col_1_nom_du_champ" (via label_to_column_id)
        mais le flat_data produit le label "1. Nom du champ" (base_label brut).
        """
        schema = self._make_numbered_schema()
        column_types, _ = create_columns_from_schema(schema)
        champ_ids = {c["id"] for c in column_types["champs"]}

        dossier = make_dossier(
            [
                make_champ("1. Nom du champ", "TextChamp", "desc_1", value="Martin"),
                make_champ("2) Prénom", "TextChamp", "desc_2", value="Jean"),
            ]
        )

        # Sans descriptor_to_column_id → fallback qui utilise le label brut
        flat = dossier_to_flat_data(dossier, exclude_repetition_champs=True)

        flat_labels = {item["label"] for item in flat["champs"]}

        # Le schéma crée col_1_nom_du_champ
        assert "col_1_nom_du_champ" in champ_ids
        # Le fallback produit le label brut "1. Nom du champ" au lieu de "col_1_nom_du_champ"
        assert "col_1_nom_du_champ" in flat_labels, (
            f"Le schéma crée la colonne 'col_1_nom_du_champ' mais le fallback "
            f"de dossier_to_flat_data produit {flat_labels} — attendu 'col_1_nom_du_champ'"
        )
