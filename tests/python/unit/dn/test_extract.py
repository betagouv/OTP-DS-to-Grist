import json

import pytest

from dn.extract import (
    build_label_fields,
    dossier_to_flat_data,
    extract_champ_values,
    extract_demandeur_info,
    iter_pj_ocr_columns,
)
from grist.utils import normalize_column_name
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


def make_carte_champ(geo_areas, label="Localisation"):
    """Fabrique un champ DS CarteChamp minimal."""
    return {
        "__typename": "CarteChamp",
        "id": "Q2FydGVDaGFtcC0xMjM0NQ==",
        "label": label,
        "champDescriptorId": "Q2hhbXBEZXNjcmlwdG9yLTk5",
        "updatedAt": "2026-01-01T00:00:00Z",
        "prefilled": False,
        "geoAreas": geo_areas,
    }


RIB_OCR_VALUES = {
    "Titulaire": "Jean Dupont",
    "IBAN": "FR7630006000011234567890189",
    "BIC": "AGRIFRPP",
    "Nom de la Banque": "Crédit Agricole",
}


def make_rib_champ(label, descriptor_id="desc_rib"):
    """Fabrique un PieceJustificativeChamp de nature RIB avec ses sous-colonnes OCR,
    libellées comme DN : "<libellé du champ> – <sous-libellé>"."""
    columns = [
        {
            "__typename": "AttachmentsColumn",
            "id": "col_pj",
            "label": label,
            "value": [{"filename": "rib.pdf"}],
        }
    ]
    columns += [
        {
            "__typename": "TextColumn",
            "id": f"col_{sub_label}",
            "label": f"{label} – {sub_label}",
            "value": value,
        }
        for sub_label, value in RIB_OCR_VALUES.items()
    ]
    return {
        "__typename": "PieceJustificativeChamp",
        "id": f"id_{descriptor_id}",
        "champDescriptorId": descriptor_id,
        "label": label,
        "updatedAt": "2026-01-01T00:00:00Z",
        "prefilled": False,
        "files": [{"filename": "rib.pdf"}],
        "columns": columns,
    }


def make_schema_with_pj(label, descriptor_id="desc_rib"):
    """Fabrique un schéma DS minimal avec une pièce justificative."""
    return {
        "title": "Test démarche",
        "activeRevision": {
            "champDescriptors": [
                {
                    "__typename": "PieceJustificativeChampDescriptor",
                    "id": descriptor_id,
                    "type": "piece_justificative",
                    "label": label,
                    "description": "",
                    "required": False,
                }
            ],
            "annotationDescriptors": [],
        },
    }


def make_geo_zone(zone_id, source="selection_utilisateur", description="zone", **extra):
    """Fabrique une zone géographique (geoArea) minimale pour un CarteChamp."""
    zone = {
        "id": zone_id,
        "source": source,
        "description": description,
        "geometry": {"type": "Point", "coordinates": [2.88, 42.69]},
    }
    zone.update(extra)
    return zone


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


class TestBuildLabelFields:
    """Tests unitaires pour la fonction build_label_fields"""

    def test_build_label_fields_empty(self):
        """Test sans label"""
        assert build_label_fields([]) == {"label_names": "", "labels_json": ""}
        assert build_label_fields(None) == {"label_names": "", "labels_json": ""}

    def test_build_label_fields_nominal(self):
        """Test avec deux labels complets"""
        labels = [
            {"id": "l1", "name": "Urgent", "color": "red"},
            {"id": "l2", "name": "À relancer", "color": "blue"},
        ]

        result = build_label_fields(labels)

        assert result["label_names"] == "Urgent, À relancer"
        assert len(json.loads(result["labels_json"])) == 2

    def test_build_label_fields_label_without_color(self):
        """Test qu'un label sans couleur est dans label_names mais pas dans labels_json.

        Comportement hérité de dossier_to_flat_data, à préserver à l'identique.
        """
        labels = [
            {"id": "l1", "name": "Urgent", "color": "red"},
            {"id": "l2", "name": "Sans couleur"},
        ]

        result = build_label_fields(labels)

        assert result["label_names"] == "Urgent, Sans couleur"
        parsed = json.loads(result["labels_json"])
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Urgent"

    def test_build_label_fields_label_without_name(self):
        """Test qu'un label sans nom est ignoré partout"""
        labels = [{"id": "l1", "color": "red"}]

        result = build_label_fields(labels)

        assert result["label_names"] == ""
        assert result["labels_json"] == ""

    def test_build_label_fields_preserves_accents(self):
        """Test que les accents ne sont pas échappés dans le JSON"""
        labels = [{"id": "l1", "name": "Contrôlé", "color": "green"}]

        result = build_label_fields(labels)

        assert "Contrôlé" in result["labels_json"]


class TestDossierToFlatDataLabels:
    """Tests sur les colonnes label_names / labels_json de dossier_to_flat_data."""

    def _flatten_with_labels(self, labels):
        dossier = make_dossier([])
        dossier["labels"] = labels
        return dossier_to_flat_data(dossier)["dossier"]

    def test_empty_or_missing_labels(self):
        """Sans labels, les deux colonnes sont vides."""
        for labels in ([], None):
            flat = self._flatten_with_labels(labels)
            assert flat["label_names"] == ""
            assert flat["labels_json"] == ""

        dossier = make_dossier([])
        del dossier["labels"]
        flat = dossier_to_flat_data(dossier)["dossier"]
        assert flat["label_names"] == ""
        assert flat["labels_json"] == ""

    def test_nominal(self):
        """Les noms sont joints par des virgules, les labels sérialisés en JSON."""
        labels = [
            {"id": "l1", "name": "Urgent", "color": "red"},
            {"id": "l2", "name": "À relancer", "color": "blue"},
        ]
        flat = self._flatten_with_labels(labels)

        assert flat["label_names"] == "Urgent, À relancer"
        assert json.loads(flat["labels_json"]) == labels

    def test_label_without_color(self):
        """Un label sans couleur est dans label_names mais pas dans labels_json."""
        flat = self._flatten_with_labels(
            [
                {"id": "l1", "name": "Urgent", "color": "red"},
                {"id": "l2", "name": "Sans couleur"},
            ]
        )

        assert flat["label_names"] == "Urgent, Sans couleur"
        assert json.loads(flat["labels_json"]) == [
            {"id": "l1", "name": "Urgent", "color": "red"}
        ]

    def test_only_labels_without_color(self):
        """Si aucun label n'a de couleur, labels_json est vide."""
        flat = self._flatten_with_labels([{"id": "l1", "name": "Sans couleur"}])

        assert flat["label_names"] == "Sans couleur"
        assert flat["labels_json"] == ""

    def test_label_without_name(self):
        """Un label sans nom est absent des deux colonnes."""
        flat = self._flatten_with_labels([{"id": "l1", "color": "red"}])

        assert flat["label_names"] == ""
        assert flat["labels_json"] == ""

    def test_preserves_accents(self):
        """Les accents sont conservés tels quels dans labels_json."""
        flat = self._flatten_with_labels(
            [{"id": "l1", "name": "Contrôlé", "color": "green"}]
        )

        assert "Contrôlé" in flat["labels_json"]


# ---------------------------------------------------------------------------
# Tests de caractérisation de extract_champ_values, type par type
#
# Figent le comportement actuel avant remaniement, bizarreries comprises.
# ---------------------------------------------------------------------------

CHAMP_ID = "Q2hhbXAtMQ=="  # base64 de "Champ-1"
DESCRIPTOR_ID = "Q2hhbXAtMTA="  # base64 de "Champ-10"


def make_typed_champ(typename, label="Champ", **fields):
    """Fabrique un champ DN minimal du type donné, complété par fields."""
    return {
        "__typename": typename,
        "id": CHAMP_ID,
        "champDescriptorId": DESCRIPTOR_ID,
        "label": label,
        "stringValue": "valeur texte",
        "updatedAt": "2024-01-01T00:00:00Z",
        "prefilled": False,
        **fields,
    }


def expected_entry(champ, value, json_value, prefix=""):
    """Entrée principale attendue pour un champ de premier niveau."""
    return {
        "id": champ["id"],
        "numeric_id": "1",
        "descriptor_id": DESCRIPTOR_ID,
        "decoded_descriptor_id": "10",
        "label": f"{prefix}{champ['label']}",
        "base_label": champ["label"],
        "type": champ["__typename"],
        "value": value,
        "json_value": json_value,
        "updated_at": champ["updatedAt"],
        "prefilled": False,
        "row_id": None,
    }


def expected_sub_column(champ, suffix, value):
    """Sous-colonne texte attendue (ex. `_nom`, `_code`) d'un champ."""
    return {
        "id": f"{champ['id']}_{suffix}",
        "numeric_id": None,
        "descriptor_id": DESCRIPTOR_ID,
        "decoded_descriptor_id": "10",
        "label": f"{champ['label']}_{suffix}",
        "base_label": f"{champ['label']}_{suffix}",
        "type": "TextColumn",
        "value": value,
        "json_value": None,
        "updated_at": champ["updatedAt"],
        "prefilled": False,
        "row_id": None,
    }


ADDRESS = {"streetAddress": "1 rue Haute", "postalCode": "30000", "cityName": "Nîmes"}
COMMUNE = {"name": "Nîmes", "code": "30189", "postalCode": "30000"}
DEPARTEMENT = {"name": "Gard", "code": "30"}
ETABLISSEMENT = {"siret": "12345678900011", "entreprise": {"raisonSociale": "ACME"}}
EPCI = {"name": "Nîmes Métropole", "code": "243000643"}
RNF = {
    "title": "Fondation X",
    "address": {"cityName": "Lyon", "postalCode": "69001"},
}


class TestExtractChampValuesSimpleTypes:
    """Types de champ produisant une seule entrée : valeur et valeur JSON."""

    @pytest.mark.parametrize(
        "typename, fields, expected_value, expected_json",
        [
            ("TextChamp", {}, "valeur texte", None),
            ("DateChamp", {"date": "2024-05-01"}, "2024-05-01", None),
            (
                "DatetimeChamp",
                {"datetime": "2024-05-01T10:00:00+02:00"},
                "2024-05-01T10:00:00+02:00",
                None,
            ),
            ("CheckboxChamp", {"checked": True}, True, None),
            ("YesNoChamp", {"selected": False}, False, None),
            ("DecimalNumberChamp", {"decimalNumber": 3.5}, 3.5, None),
            ("IntegerNumberChamp", {"integerNumber": 42}, 42, None),
            ("CiviliteChamp", {"civilite": "Mme"}, "Mme", None),
            # Listes déroulantes
            ("DropDownListChamp", {"stringValue": "Option A"}, "Option A", None),
            ("DropDownListChamp", {"stringValue": '["A", "B"]'}, "A, B", None),
            (
                "DropDownListChamp",
                {"stringValue": None, "value": "Option B"},
                "Option B",
                None,
            ),
            (
                "MultipleDropDownListChamp",
                {"values": ["A", "B"]},
                "A, B",
                ["A", "B"],
            ),
            (
                "MultipleDropDownListChamp",
                {"values": [], "stringValue": '["A", "B"]'},
                "A, B",
                [],
            ),
            (
                "LinkedDropDownListChamp",
                {"primaryValue": "P", "secondaryValue": "S"},
                "P - S",
                {"primaryValue": "P", "secondaryValue": "S"},
            ),
            (
                "LinkedDropDownListChamp",
                {"primaryValue": "P"},
                "P",
                {"primaryValue": "P", "secondaryValue": ""},
            ),
            # Adresse
            (
                "AddressChamp",
                {"address": ADDRESS},
                "1 rue Haute, 30000 Nîmes",
                ADDRESS,
            ),
            (
                "AddressChamp",
                {"address": ADDRESS, "commune": COMMUNE, "departement": DEPARTEMENT},
                "1 rue Haute, 30000 Nîmes",
                {"address": ADDRESS, "commune": COMMUNE, "departement": DEPARTEMENT},
            ),
            # Bizarrerie : séparateurs conservés quand la voie est absente
            (
                "AddressChamp",
                {"address": {"cityName": "Nîmes"}},
                ",  Nîmes",
                {"cityName": "Nîmes"},
            ),
            # SIRET
            (
                "SiretChamp",
                {"etablissement": ETABLISSEMENT},
                "12345678900011 - ACME",
                ETABLISSEMENT,
            ),
            (
                "SiretChamp",
                {"etablissement": {"siret": "12345678900011"}},
                "12345678900011",
                {"siret": "12345678900011"},
            ),
            # Lien vers un dossier
            (
                "DossierLinkChamp",
                {"dossier": {"number": 12, "state": "en_construction"}},
                "Dossier #12 (en_construction)",
                {"number": 12, "state": "en_construction"},
            ),
            (
                "DossierLinkChamp",
                {"dossier": {"id": "D1"}},
                "Aucun dossier lié",
                {"id": "D1"},
            ),
            # EPCI
            (
                "EpciChamp",
                {"epci": EPCI},
                "Nîmes Métropole (243000643)",
                {"epci": EPCI},
            ),
            (
                "EpciChamp",
                {"epci": EPCI, "departement": DEPARTEMENT},
                "Nîmes Métropole (243000643), Gard",
                {"epci": EPCI, "departement": DEPARTEMENT},
            ),
            # RNF
            ("RNFChamp", {"rnf": RNF}, "Fondation X - Lyon (69001)", {"rnf": RNF}),
            (
                "RNFChamp",
                {"rnf": RNF, "commune": COMMUNE, "departement": DEPARTEMENT},
                "Fondation X - Lyon (69001)",
                {"rnf": RNF, "commune": COMMUNE, "departement": DEPARTEMENT},
            ),
            (
                "RNFChamp",
                {"rnf": {"title": "Fondation X"}},
                "Fondation X",
                {"rnf": {"title": "Fondation X"}},
            ),
            (
                "RNFChamp",
                {"rnf": {"id": "R1"}},
                "",
                {"rnf": {"id": "R1"}},
            ),
            # Engagement juridique
            (
                "EngagementJuridiqueChamp",
                {"engagementJuridique": {"montantEngage": 100, "montantPaye": 50}},
                "Montant engagé: 100, Montant payé: 50",
                {"montantEngage": 100, "montantPaye": 50},
            ),
            (
                "EngagementJuridiqueChamp",
                {"engagementJuridique": {"montantEngage": None, "montantPaye": 50}},
                "Montant payé: 50",
                {"montantEngage": None, "montantPaye": 50},
            ),
            (
                "EngagementJuridiqueChamp",
                {"engagementJuridique": {"montantEngage": None, "montantPaye": None}},
                "",
                {"montantEngage": None, "montantPaye": None},
            ),
        ],
    )
    def test_value_and_json_value(
        self, typename, fields, expected_value, expected_json
    ):
        champ = make_typed_champ(typename, **fields)

        result = extract_champ_values(champ)

        assert len(result) == 1
        assert result[0]["value"] == expected_value
        assert result[0]["json_value"] == expected_json

    def test_full_entry(self):
        """Une entrée porte les identifiants, libellés et métadonnées du champ."""
        champ = make_typed_champ("DateChamp", label="Date", date="2024-05-01")

        assert extract_champ_values(champ) == [
            expected_entry(champ, "2024-05-01", None)
        ]


class TestExtractChampValuesFallback:
    """Sans son objet, un champ composé retombe sur stringValue."""

    @pytest.mark.parametrize(
        "typename, object_key",
        [
            ("AddressChamp", "address"),
            ("SiretChamp", "etablissement"),
            ("DossierLinkChamp", "dossier"),
            ("PaysChamp", "pays"),
            ("RegionChamp", "region"),
            ("DepartementChamp", "departement"),
            ("CommuneChamp", "commune"),
            ("EpciChamp", "epci"),
            ("RNFChamp", "rnf"),
            ("EngagementJuridiqueChamp", "engagementJuridique"),
        ],
    )
    def test_missing_object_falls_back_to_string_value(self, typename, object_key):
        champ = make_typed_champ(typename, **{object_key: None})

        assert extract_champ_values(champ) == [
            expected_entry(champ, "valeur texte", None)
        ]


class TestExtractChampValuesSubColumns:
    """Champs territoriaux : sous-colonnes texte produites avant l'entrée principale."""

    @pytest.mark.parametrize(
        "typename, object_key",
        [
            ("PaysChamp", "pays"),
            ("RegionChamp", "region"),
            ("DepartementChamp", "departement"),
        ],
    )
    def test_name_and_code(self, typename, object_key):
        territoire = {"name": "Gard", "code": "30"}
        champ = make_typed_champ(typename, label="Lieu", **{object_key: territoire})

        assert extract_champ_values(champ) == [
            expected_sub_column(champ, "nom", "Gard"),
            expected_sub_column(champ, "code", "30"),
            expected_entry(champ, "Gard (30)", territoire),
        ]

    @pytest.mark.parametrize(
        "typename, object_key",
        [
            ("PaysChamp", "pays"),
            ("RegionChamp", "region"),
            ("DepartementChamp", "departement"),
        ],
    )
    def test_name_only(self, typename, object_key):
        """Sans code, la sous-colonne `_code` n'est pas produite."""
        territoire = {"name": "Gard"}
        champ = make_typed_champ(typename, label="Lieu", **{object_key: territoire})

        assert extract_champ_values(champ) == [
            expected_sub_column(champ, "nom", "Gard"),
            expected_entry(champ, "Gard", territoire),
        ]

    def test_commune_complete(self):
        """Commune avec département : 5 sous-colonnes, dans l'ordre déclaré par le schéma."""
        champ = make_typed_champ(
            "CommuneChamp", label="Commune", commune=COMMUNE, departement=DEPARTEMENT
        )

        assert extract_champ_values(champ) == [
            expected_sub_column(champ, "nom", "Nîmes"),
            expected_sub_column(champ, "code_postal", "30000"),
            expected_sub_column(champ, "departement", "Gard"),
            expected_sub_column(champ, "code_insee", "30189"),
            expected_sub_column(champ, "code_departement", "30"),
            expected_entry(
                champ,
                "Nîmes (30000), Gard",
                {"commune": COMMUNE, "departement": DEPARTEMENT},
            ),
        ]

    def test_commune_without_departement_nor_postal_code(self):
        """Sans département ni code postal, seules `_nom` et `_code_insee` restent."""
        commune = {"name": "Nîmes", "code": "30189"}
        champ = make_typed_champ("CommuneChamp", label="Commune", commune=commune)

        assert extract_champ_values(champ) == [
            expected_sub_column(champ, "nom", "Nîmes"),
            expected_sub_column(champ, "code_insee", "30189"),
            expected_entry(champ, "Nîmes", {"commune": commune}),
        ]


class TestExtractChampValuesRepetition:
    """Blocs répétables : une entrée par champ de chaque rangée."""

    def _bloc(self):
        def row_champ(value, champ_id):
            return {
                **make_typed_champ("TextChamp", label="Nom", stringValue=value),
                "id": champ_id,
            }

        header = make_typed_champ("HeaderSectionChamp", label="Titre")
        return make_typed_champ(
            "RepetitionChamp",
            label="Bloc",
            rows=[
                {"id": "row1", "champs": [header, row_champ("A", "Q2hhbXAtMg==")]},
                {"id": "row2", "champs": [row_champ("B", "Q2hhbXAtMw==")]},
            ],
        )

    def test_rows_are_prefixed_and_linked(self):
        """Libellé préfixé par bloc et rang, row_id portant l'id de la rangée."""
        result = extract_champ_values(self._bloc())

        assert [
            (item["label"], item["base_label"], item["value"], item["row_id"])
            for item in result
        ] == [
            ("Bloc_1_Nom", "Nom", "A", "row1"),
            ("Bloc_2_Nom", "Nom", "B", "row2"),
        ]
        assert [item["numeric_id"] for item in result] == ["2", "3"]

    def test_prefix_is_kept_before_bloc_label(self):
        result = extract_champ_values(self._bloc(), prefix="annotation_")

        assert [item["label"] for item in result] == [
            "annotation_Bloc_1_Nom",
            "annotation_Bloc_2_Nom",
        ]

    def test_empty_bloc_produces_nothing(self):
        assert extract_champ_values(make_typed_champ("RepetitionChamp", rows=[])) == []


class TestExtractChampValuesCommon:
    """Règles communes à tous les types : identifiants, préfixe, champs ignorés."""

    @pytest.mark.parametrize("typename", ["HeaderSectionChamp", "ExplicationChamp"])
    def test_display_champs_are_ignored(self, typename):
        assert extract_champ_values(make_typed_champ(typename)) == []

    @pytest.mark.parametrize(
        "champ_id, expected_numeric_id",
        [
            (CHAMP_ID, "1"),
            ("gid://app/Champ/123", "123"),
            ("gid://app/Autre/123", None),
            ("a/b", None),
        ],
    )
    def test_numeric_id(self, champ_id, expected_numeric_id):
        champ = {**make_typed_champ("TextChamp"), "id": champ_id}

        assert extract_champ_values(champ)[0]["numeric_id"] == expected_numeric_id

    def test_prefix_applies_to_label_only(self):
        champ = make_typed_champ("TextChamp", label="Avis")

        assert extract_champ_values(champ, prefix="annotation_") == [
            expected_entry(champ, "valeur texte", None, prefix="annotation_")
        ]

    def test_without_descriptor_id(self):
        champ = make_typed_champ("TextChamp")
        del champ["champDescriptorId"]

        result = extract_champ_values(champ)

        assert result[0]["descriptor_id"] is None
        assert result[0]["decoded_descriptor_id"] is None


# ---------------------------------------------------------------------------
# Tests CarteChamp (champs carto top-level)
#
# Bug corrigé : un append inconditionnel en fin de extract_champ_values
# ajoutait une entrée fantôme (value=None, json_value=None) après chaque
# champ CarteChamp top-level, écrasant systématiquement la colonne dans
# Grist lors du sync, quel que soit le nombre de zones dessinées.
# ---------------------------------------------------------------------------


class TestExtractChampValuesCarteChamp:
    """Tests pour extract_champ_values - traitement des champs CarteChamp (top-level)."""

    def test_sans_zone_une_seule_entree(self):
        champ = make_carte_champ([])
        result = extract_champ_values(champ)
        assert len(result) == 1

    def test_sans_zone_valeur_par_defaut(self):
        champ = make_carte_champ([])
        result = extract_champ_values(champ)
        assert result[0]["value"] == "Aucune zone géographique définie"
        assert result[0]["json_value"] is None

    def test_une_zone_une_seule_entree(self):
        champ = make_carte_champ([make_geo_zone("GeoArea-1", description="Parcelle A")])
        result = extract_champ_values(champ)
        assert len(result) == 1

    def test_une_zone_json_value_est_une_liste(self):
        # Point d'attention : même avec 1 seule zone, json_value est une
        # liste d'un élément (et non le dict de la zone directement), pour
        # rester cohérent avec le cas multi-zones.
        zone = make_geo_zone("GeoArea-1", description="Parcelle A")
        champ = make_carte_champ([zone])
        result = extract_champ_values(champ)
        assert result[0]["json_value"] == [zone]

    def test_une_zone_value_contient_la_description(self):
        champ = make_carte_champ(
            [make_geo_zone("GeoArea-1", source="cadastre", description="Parcelle A")]
        )
        result = extract_champ_values(champ)
        assert "Parcelle A" in result[0]["value"]
        assert "cadastre" in result[0]["value"]

    def test_plusieurs_zones_une_seule_entree_pas_ecrasement(self):
        # Régression : avant le fix, 3 zones produisaient 3 entrées (+1
        # fantôme) partageant le même label -> la dernière écrasait tout
        # dans Grist. On vérifie qu'il n'y a plus qu'une seule entrée.
        zones = [
            make_geo_zone("GeoArea-1", description="Point"),
            make_geo_zone("GeoArea-2", description="Ligne"),
            make_geo_zone("GeoArea-3", description="Polygone"),
        ]
        champ = make_carte_champ(zones)
        result = extract_champ_values(champ)
        assert len(result) == 1

    def test_plusieurs_zones_json_value_contient_toutes_les_zones(self):
        zones = [
            make_geo_zone("GeoArea-1", description="Point"),
            make_geo_zone("GeoArea-2", description="Ligne"),
            make_geo_zone("GeoArea-3", description="Polygone"),
        ]
        champ = make_carte_champ(zones)
        result = extract_champ_values(champ)
        assert result[0]["json_value"] == zones
        assert len(result[0]["json_value"]) == 3

    def test_plusieurs_zones_value_resume_toutes_les_zones(self):
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

    def test_plusieurs_zones_meme_label_pour_toutes_les_entrees(self):
        zones = [make_geo_zone("GeoArea-1"), make_geo_zone("GeoArea-2")]
        champ = make_carte_champ(zones, label="Ma zone")
        result = extract_champ_values(champ)
        assert result[0]["label"] == "Ma zone"

    def test_cadastre_donnees_preservees_dans_json_value(self):
        # Les champs commune/numero/section/prefixe/surface ne sont plus
        # dupliqués en clés à plat (dead code supprimé), mais restent
        # accessibles via json_value puisqu'on garde le dict de zone complet.
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


class TestExtractChampValuesPieceJustificativeOcr:
    """Tests pour extract_champ_values - sous-colonnes OCR des pièces justificatives (RIB)."""

    def _ocr_items(self, champ):
        return [
            item for item in extract_champ_values(champ) if item["type"] == "TextColumn"
        ]

    @pytest.mark.parametrize(
        "label",
        [
            "RIB",
            "1. RIB du demandeur",
            "RIB à rattacher à la demande ci-dessous",
        ],
    )
    def test_ids_correspondent_aux_colonnes_du_schema(self, label):
        # Régression #556 : l'id généré pour "Nom de la Banque" était forcé sur le
        # libellé d'une autre démarche, et le retrait des "." cassait les
        # libellés numérotés -> valeurs ignorées silencieusement par Grist.
        column_types, _ = create_columns_from_schema(make_schema_with_pj(label))
        schema_ids = {col["id"] for col in column_types["champs"]}

        ocr_ids = {
            normalize_column_name(item["label"])
            for item in self._ocr_items(make_rib_champ(label))
        }

        assert len(ocr_ids) == 4
        assert ocr_ids <= schema_ids

    def test_libelle_avec_points(self):
        ocr_ids = {
            normalize_column_name(item["label"])
            for item in self._ocr_items(make_rib_champ("R.I.B. de l'établissement"))
        }
        assert ocr_ids == {
            "r_i_b_de_l_etablissement_titulaire",
            "r_i_b_de_l_etablissement_iban",
            "r_i_b_de_l_etablissement_bic",
            "r_i_b_de_l_etablissement_nom_de_la_banque",
        }

    def test_valeurs_associees_aux_bonnes_colonnes(self):
        values = {
            normalize_column_name(item["label"]): item["value"]
            for item in self._ocr_items(make_rib_champ("RIB"))
        }
        assert values == {
            "rib_titulaire": "Jean Dupont",
            "rib_iban": "FR7630006000011234567890189",
            "rib_bic": "AGRIFRPP",
            "rib_nom_de_la_banque": "Crédit Agricole",
        }

    def test_sous_colonne_vide_ignoree(self):
        champ = make_rib_champ("RIB")
        for col in champ["columns"]:
            if col["label"].endswith("BIC"):
                col["value"] = None
        labels = {
            normalize_column_name(item["label"]) for item in self._ocr_items(champ)
        }
        assert "rib_bic" not in labels
        assert len(labels) == 3

    def test_flat_data_passe_par_dossier_to_flat_data(self):
        dossier = make_dossier([make_rib_champ("RIB")])
        flat = dossier_to_flat_data(dossier, exclude_repetition_champs=True)
        labels = {normalize_column_name(item["label"]) for item in flat["champs"]}
        assert {
            "rib",
            "rib_titulaire",
            "rib_iban",
            "rib_bic",
            "rib_nom_de_la_banque",
        } <= labels


def make_avis_impot_champ(label="Avis"):
    """PieceJustificativeChamp de nature AVIS_IMPOT : sous-colonnes typées, avec les
    alias demandés par ChampFragment pour les types non textuels."""
    return {
        "__typename": "PieceJustificativeChamp",
        "id": "id_avis",
        "champDescriptorId": "desc_avis",
        "label": label,
        "files": [{"filename": "avis.pdf"}],
        "columns": [
            {"__typename": "AttachmentsColumn", "id": "c0", "label": label},
            {
                "__typename": "TextColumn",
                "id": "c1",
                "label": f"{label} – Déclarant 1",
                "value": "Jean Dupont",
            },
            {
                "__typename": "IntegerColumn",
                "id": "c2",
                "label": f"{label} – Revenu fiscal de référence",
                "integerValue": "45000",
            },
            {
                "__typename": "DecimalColumn",
                "id": "c3",
                "label": f"{label} – Nombre de parts",
                "decimalValue": 2.5,
            },
            {
                "__typename": "DateColumn",
                "id": "c4",
                "label": f"{label} – Date de mise en recouvrement",
                "dateValue": "2025-07-31",
            },
            {
                "__typename": "EnumColumn",
                "id": "c5",
                "label": f"{label} – Département",
                "value": "34",
            },
        ],
    }


class TestIterPjOcrColumns:
    """Tests pour iter_pj_ocr_columns"""

    def _values(self, champ):
        return {label: value for _, label, value in iter_pj_ocr_columns(champ)}

    def test_valeurs_typees(self):
        assert self._values(make_avis_impot_champ()) == {
            "Avis Déclarant 1": "Jean Dupont",
            "Avis Revenu fiscal de référence": "45000",
            "Avis Nombre de parts": 2.5,
            "Avis Date de mise en recouvrement": "2025-07-31",
            "Avis Département": "34",
        }

    def test_zero_conserve(self):
        champ = make_avis_impot_champ()
        champ["columns"][2]["integerValue"] = 0
        assert self._values(champ)["Avis Revenu fiscal de référence"] == 0

    @pytest.mark.parametrize("empty", [None, ""])
    def test_valeur_vide_ignoree(self, empty):
        champ = make_avis_impot_champ()
        champ["columns"][1]["value"] = empty
        assert "Avis Déclarant 1" not in self._values(champ)

    def test_fichiers_et_types_inconnus_ignores(self):
        champ = make_avis_impot_champ()
        champ["columns"] = [
            {"__typename": "AttachmentsColumn", "id": "a", "label": "Avis"},
            {
                "__typename": "BooleanColumn",
                "id": "b",
                "label": "Avis – Inconnue",
                "value": True,
            },
        ]
        assert self._values(champ) == {}

    def test_sans_colonnes(self):
        champ = make_avis_impot_champ()
        champ["columns"] = None
        assert self._values(champ) == {}


class TestExtractChampValuesPieceJustificativeOcrTypees:
    """Tests pour extract_champ_values - sous-colonnes OCR non textuelles."""

    def test_entrees_typees_avec_nom_de_fichier(self):
        result = extract_champ_values(make_avis_impot_champ())
        by_label = {item["label"]: item for item in result}

        assert by_label["Avis"]["value"] == "avis.pdf"
        assert by_label["Avis Nombre de parts"]["value"] == 2.5
        assert by_label["Avis Nombre de parts"]["type"] == "DecimalColumn"
        assert by_label["Avis Date de mise en recouvrement"]["type"] == "DateColumn"
        assert len(result) == 6

    def test_prefixe_de_bloc(self):
        result = extract_champ_values(make_avis_impot_champ(), prefix="Bloc_1_")
        labels = {item["label"] for item in result}
        assert "Bloc_1_Avis Nombre de parts" in labels

    def test_ids_correspondent_aux_colonnes_du_schema(self):
        champ = make_avis_impot_champ()
        schema = make_schema_with_pj("Avis", descriptor_id="desc_avis")
        # Schéma et extraction partent des mêmes colonnes DN
        schema["pj_ocr_columns"] = {
            "desc_avis": [
                (col["label"], col["__typename"])
                for col in champ["columns"]
                if col["__typename"] != "AttachmentsColumn"
            ]
        }
        column_types, _ = create_columns_from_schema(schema)
        schema_types = {
            col["id"]: col.get("type") or col["fields"]["type"]
            for col in column_types["champs"]
        }

        ocr_types = {
            normalize_column_name(item["label"]): schema_types.get(
                normalize_column_name(item["label"])
            )
            for item in extract_champ_values(champ)
        }

        assert ocr_types == {
            "avis": "Text",
            "avis_declarant_1": "Text",
            "avis_revenu_fiscal_de_reference": "Int",
            "avis_nombre_de_parts": "Numeric",
            "avis_date_de_mise_en_recouvrement": "Date",
            "avis_departement": "Text",
        }


PROBLEMATIC_DESCRIPTOR_ID = "desc_problematique"


def make_kept_champ():
    return make_typed_champ("TextChamp", label="Gardé", champDescriptorId="desc_garde")


def labels_in_champs(champs, problematic_ids):
    flat = dossier_to_flat_data(make_dossier(champs), problematic_ids=problematic_ids)
    return [item["base_label"] for item in flat["champs"]]


def labels_in_annotations(champs, problematic_ids):
    flat = dossier_to_flat_data(
        make_dossier([], annotations=champs), problematic_ids=problematic_ids
    )
    return [item["base_label"] for item in flat["annotations"]]


def labels_in_repetable_row(champs, problematic_ids):
    bloc = make_typed_champ(
        "RepetitionChamp", label="Bloc", rows=[{"id": "row1", "champs": champs}]
    )
    flat = dossier_to_flat_data(make_dossier([bloc]), problematic_ids=problematic_ids)
    assert len(flat["repetable_rows"]) == 1
    return [
        key
        for key in flat["repetable_rows"][0]
        if key != "dossier_number" and not key.startswith("block_")
    ]


@pytest.mark.parametrize(
    "labels_at_level",
    [labels_in_champs, labels_in_annotations, labels_in_repetable_row],
)
class TestDossierToFlatDataFiltering:
    """Champs ignorés dans les champs, les annotations et les rangées de bloc."""

    @pytest.mark.parametrize("typename", ["HeaderSectionChamp", "ExplicationChamp"])
    def test_display_champ_is_ignored(self, labels_at_level, typename):
        """Un champ d'affichage ne produit aucune colonne."""
        champs = [make_typed_champ(typename, label="Titre"), make_kept_champ()]

        assert labels_at_level(champs, None) == ["Gardé"]

    def test_problematic_champ_is_ignored(self, labels_at_level):
        """Un champ dont le descripteur est problématique est écarté."""
        problematic = make_typed_champ(
            "TextChamp", label="Écarté", champDescriptorId=PROBLEMATIC_DESCRIPTOR_ID
        )

        labels = labels_at_level(
            [problematic, make_kept_champ()], {PROBLEMATIC_DESCRIPTOR_ID}
        )

        assert labels == ["Gardé"]

    def test_champ_is_kept_without_problematic_ids(self, labels_at_level):
        """Sans descripteur problématique déclaré, le champ est conservé."""
        champ = make_typed_champ(
            "TextChamp", label="Conservé", champDescriptorId=PROBLEMATIC_DESCRIPTOR_ID
        )

        assert labels_at_level([champ], None) == ["Conservé"]


class TestExtractDemandeurInfo:
    """Informations du demandeur, selon son type."""

    COMMON_INFO = {
        "dossier_number": 1,
        "usager_email": "usager@example.org",
        "prenom_mandataire": "Ana",
        "nom_mandataire": "Martin",
        "depose_par_un_tiers": True,
    }

    def _dossier(self, demandeur):
        return {
            "number": 1,
            "usager": {"email": "usager@example.org"},
            "prenomMandataire": "Ana",
            "nomMandataire": "Martin",
            "deposeParUnTiers": True,
            "demandeur": demandeur,
        }

    def test_personne_physique(self):
        """Une personne physique ajoute son identité aux informations communes."""
        identity = {
            "civilite": "Mme",
            "nom": "Durand",
            "prenom": "Léa",
            "email": "lea@example.org",
        }
        demandeur = {"__typename": "PersonnePhysique", **identity}

        assert extract_demandeur_info(self._dossier(demandeur)) == {
            **self.COMMON_INFO,
            "type": "PersonnePhysique",
            **identity,
        }

    @pytest.mark.parametrize("typename", ["PersonneMorale", "PersonneMoraleIncomplete"])
    def test_personne_morale(self, typename):
        """Une personne morale n'ajoute que son type aux informations communes."""
        demandeur = {"__typename": typename, "siret": "12345678900011"}

        assert extract_demandeur_info(self._dossier(demandeur)) == {
            **self.COMMON_INFO,
            "type": typename,
        }

    @pytest.mark.parametrize("demandeur", [{}, None])
    def test_without_demandeur(self, demandeur):
        """Sans demandeur, seules les informations communes sont renvoyées."""
        assert extract_demandeur_info(self._dossier(demandeur)) == self.COMMON_INFO
