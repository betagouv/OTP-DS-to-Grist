from unittest.mock import patch

from schema_utils import (
    create_columns_from_schema,
    get_problematic_descriptor_ids_from_schema,
    auto_clean_schema_descriptors,
)


class TestSchemaUtils:
    """Tests unitaires pour les utilitaires de schéma"""

    def test_get_problematic_descriptor_ids_from_schema(self):
        """Test l'extraction des IDs problématiques"""
        schema = {
            "activeRevision": {
                "champDescriptors": [
                    {
                        "id": "1",
                        "__typename": "TextChampDescriptor",
                        "type": "text"
                    },
                    {
                        "id": "2",
                        "__typename": "HeaderSectionChampDescriptor",
                        "type": "header_section"
                    },
                    {
                        "id": "3",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication"
                    },
                    {
                        "__typename": "RepetitionChampDescriptor",
                        "champDescriptors": [
                            {
                                "id": "4",
                                "__typename": "TextChampDescriptor",
                                "type": "text"
                            },
                            {
                                "id": "5",
                                "__typename": "HeaderSectionChampDescriptor",
                                "type": "header_section"
                            }
                        ]
                    }
                ],
                "annotationDescriptors": [
                    {
                        "id": "6",
                        "__typename": "TextChampDescriptor",
                        "type": "text"
                    },
                    {
                        "id": "7",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication"
                    }
                ]
            }
        }

        problematic_ids = get_problematic_descriptor_ids_from_schema(schema)

        expected_ids = {"2", "3", "5", "7"}
        assert problematic_ids == expected_ids

    def test_get_problematic_descriptor_ids_empty_schema(self):
        """Test avec un schéma vide"""
        schema = {
            "activeRevision": {
                "champDescriptors": [],
                "annotationDescriptors": []
            }
        }
        problematic_ids = get_problematic_descriptor_ids_from_schema(schema)
        assert problematic_ids == set()

    def test_get_problematic_descriptor_ids_no_active_revision(self):
        """Test sans révision active"""
        schema = {}
        problematic_ids = get_problematic_descriptor_ids_from_schema(schema)
        assert problematic_ids == set()

    def test_auto_clean_schema_descriptors(self):
        """Test le nettoyage automatique des descripteurs"""
        schema = {
            "activeRevision": {
                "champDescriptors": [
                    {
                        "id": "1",
                        "__typename": "TextChampDescriptor",
                        "type": "text",
                        "label": "Text"
                    },
                    {
                        "id": "2",
                        "__typename": "HeaderSectionChampDescriptor",
                        "type": "header_section",
                        "label": "Header"
                    },
                    {
                        "id": "3",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication",
                        "label": "Explication"
                    },
                    {
                        "__typename": "RepetitionChampDescriptor",
                        "champDescriptors": [
                            {
                                "id": "4",
                                "__typename": "TextChampDescriptor",
                                "type": "text",
                                "label": "Inner Text"
                            },
                            {
                                "id": "5",
                                "__typename": "HeaderSectionChampDescriptor",
                                "type": "header_section",
                                "label": "Inner Header"
                            }
                        ]
                    }
                ],
                "annotationDescriptors": [
                    {
                        "id": "6",
                        "__typename": "TextChampDescriptor",
                        "type": "text",
                        "label": "Annotation"
                    },
                    {
                        "id": "7",
                        "__typename": "ExplicationChampDescriptor",
                        "type": "explication",
                        "label": "Annotation Expl"
                    }
                ]
            }
        }

        cleaned = auto_clean_schema_descriptors(schema)

        # Vérifier que les champs problématiques sont filtrés
        champ_descriptors = cleaned["activeRevision"]["champDescriptors"]
        assert len(champ_descriptors) == 2  # Text + Repetition nettoyé

        # Le bloc répétable devrait avoir un sous-champ nettoyé
        repetition = next(
            d for d in champ_descriptors
            if d.get("__typename") == "RepetitionChampDescriptor"
        )
        assert len(repetition["champDescriptors"]) == 1  # Seulement le Text

        # Annotations nettoyées
        annotation_descriptors = cleaned[
            "activeRevision"
        ]["annotationDescriptors"]
        assert len(annotation_descriptors) == 1  # Seulement le Text

    def test_auto_clean_schema_descriptors_empty(self):
        """Test avec un schéma vide"""
        schema = {
            "activeRevision": {
                "champDescriptors": [],
                "annotationDescriptors": []
            }
        }
        cleaned = auto_clean_schema_descriptors(schema)
        assert cleaned == schema


# ========================================
# Helpers pour les tests de create_columns_from_schema
# ========================================


def _make_descriptor(typename, label, type_="text", desc_id="desc_001", extra=None):
    d = {
        "__typename": typename,
        "id": desc_id,
        "type": type_,
        "label": label,
        "description": "",
        "required": False,
    }
    if extra:
        d.update(extra)
    return d


def _make_schema(champ_descriptors=None, annotation_descriptors=None):
    return {
        "activeRevision": {
            "champDescriptors": champ_descriptors or [],
            "annotationDescriptors": annotation_descriptors or [],
        }
    }


def _col_ids(columns):
    return [c["id"] for c in columns]


class TestCreateColumnsFromSchema:

    def test_simple_text_fields(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("TextChampDescriptor", "Nom", desc_id="d1"),
            _make_descriptor("TextChampDescriptor", "Prénom", desc_id="d2"),
        ])
        result, problematic = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        assert "dossier_number" in champ_ids
        assert "champ_id" in champ_ids
        assert "nom" in champ_ids
        assert "prenom" in champ_ids
        assert result["has_repetable_blocks"] is False
        assert result["has_carto_fields"] is False

    def test_filters_header_and_explication(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("TextChampDescriptor", "Nom", desc_id="d1"),
            _make_descriptor("HeaderSectionChampDescriptor", "Section",
                             type_="header_section", desc_id="d2"),
            _make_descriptor("ExplicationChampDescriptor", "Explication",
                             type_="explication", desc_id="d3"),
        ])
        result, _ = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        assert "nom" in champ_ids
        assert "section" not in champ_ids
        assert "explication" not in champ_ids

    def test_repetition_block_creates_separate_table(self):
        inner = _make_descriptor("TextChampDescriptor", "Sujet", desc_id="inner1")
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("RepetitionChampDescriptor", "Pièces",
                             type_="repetition", desc_id="rep1",
                             extra={"champDescriptors": [inner]}),
        ])
        result, _ = create_columns_from_schema(schema)
        assert result["has_repetable_blocks"] is True
        assert "repetable_blocks" in result
        block = result["repetable_blocks"]["pieces"]
        assert "sujet" in _col_ids(block["columns"])
        assert block["original_label"] == "Pièces"

    def test_piece_justificative_rib_columns(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("PieceJustificativeChampDescriptor", "RIB à rattacher",
                             type_="piece_justificative", desc_id="rib1"),
        ])
        result, _ = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        assert any("rib" in cid for cid in champ_ids)
        assert any("titulaire" in cid for cid in champ_ids)
        assert any("iban" in cid for cid in champ_ids)
        assert any("bic" in cid for cid in champ_ids)
        assert any("nom_de_la_banque" in cid for cid in champ_ids)

    def test_commune_creates_suffix_columns(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("CommuneChampDescriptor", "Commune",
                             type_="commune", desc_id="com1"),
        ])
        result, _ = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        for suffix in ["nom", "code_postal", "departement", "code_insee", "code_departement"]:
            assert any(suffix in cid for cid in champ_ids), f"Missing: {suffix}"

    def test_pays_creates_nom_code(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("PaysChampDescriptor", "Pays",
                             type_="pays", desc_id="pays1"),
        ])
        result, _ = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        assert any("nom" in cid for cid in champ_ids)
        assert any("code" in cid for cid in champ_ids)

    def test_region_creates_nom_code(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("RegionChampDescriptor", "Région",
                             type_="region", desc_id="reg1"),
        ])
        result, _ = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        assert any("nom" in cid for cid in champ_ids)
        assert any("code" in cid for cid in champ_ids)

    def test_departement_creates_nom_code(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("DepartementChampDescriptor", "Département",
                             type_="departement", desc_id="dept1"),
        ])
        result, _ = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        assert any("nom" in cid for cid in champ_ids)
        assert any("code" in cid for cid in champ_ids)

    def test_duplicate_labels_get_suffixes(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("TextChampDescriptor", "Nom", desc_id="d1"),
            _make_descriptor("TextChampDescriptor", "Nom", desc_id="d2"),
        ])
        result, _ = create_columns_from_schema(schema)
        champ_ids = _col_ids(result["champs"])
        assert "nom" in champ_ids
        assert "nom_1" in champ_ids

    def test_descriptor_to_column_id_mapping(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("TextChampDescriptor", "Email", desc_id="desc_email"),
        ])
        result, _ = create_columns_from_schema(schema)
        mapping = result["descriptor_to_column_id"]
        assert "desc_email" in mapping
        assert mapping["desc_email"] == "email"

    def test_annotations_prefixed(self):
        schema = _make_schema(annotation_descriptors=[
            _make_descriptor("TextChampDescriptor", "Avis", desc_id="ann1"),
        ])
        result, _ = create_columns_from_schema(schema)
        ann_ids = _col_ids(result["annotations"])
        assert "dossier_number" in ann_ids
        assert "avis" in ann_ids

    def test_logs_creation_message(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("TextChampDescriptor", "Nom", desc_id="d1"),
        ])
        with patch("utils.log.log") as mock_log:
            create_columns_from_schema(schema, demarche_number=42)
        mock_log.assert_any_call("Création des colonnes pour la démarche 42")

    def test_no_log_when_no_demarche_number(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("TextChampDescriptor", "Nom", desc_id="d1"),
        ])
        with patch("utils.log.log") as mock_log:
            create_columns_from_schema(schema)
        for call_args in mock_log.call_args_list:
            assert "Création des colonnes" not in call_args.args[0]
