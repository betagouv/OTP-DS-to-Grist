"""
Tests unitaires pour les fonctions de récupération de schéma dans dn/schema.py:
- get_demarche_schema
- get_demarche_schema_robust
- get_demarche_schema_enhanced
"""

from unittest.mock import MagicMock, patch

import pytest

from dn.schema import (
    create_columns_from_schema,
    get_demarche_schema,
    get_demarche_schema_enhanced,
    get_demarche_schema_robust,
    get_problematic_descriptor_ids_from_schema,
    auto_clean_schema_descriptors,
)


def _make_demarche_response(champs=None, annotations=None):
    """Construit une réponse GraphQL simulée pour get_demarche_schema."""
    champs = champs or [{"__typename": "TextChampDescriptor", "id": "champ-1", "type": "text", "label": "Nom"}]
    annotations = annotations or []
    return {
        "data": {
            "demarche": {
                "id": "demarche-1",
                "number": 42,
                "title": "Test",
                "activeRevision": {
                    "id": "rev-1",
                    "datePublication": "2024-01-15T10:00:00Z",
                    "champDescriptors": champs,
                    "annotationDescriptors": annotations,
                },
            }
        }
    }


def _mock_response(json_data=None, status_code=200, raise_for_status=None):
    """Crée un mock de réponse requests."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if raise_for_status:
        resp.raise_for_status.side_effect = raise_for_status
    else:
        resp.raise_for_status.return_value = None
    return resp


# ============================================================
# get_demarche_schema
# ============================================================


class TestGetDemarcheSchema:
    """Tests pour get_demarche_schema"""

    @patch("dn.schema.API_TOKEN", "")
    def test_no_token_raises(self):
        with pytest.raises(ValueError, match="token"):
            get_demarche_schema(42)

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_response(
            json_data=_make_demarche_response()
        )

        result = get_demarche_schema(42)

        assert result["number"] == 42
        assert result["title"] == "Test"
        assert "activeRevision" in result
        mock_post.assert_called_once()

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_success_converts_demarche_number_to_int(self, mock_post):
        mock_post.return_value = _mock_response(
            json_data=_make_demarche_response()
        )

        get_demarche_schema("42")

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["variables"]["demarcheNumber"] == 42

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_http_error(self, mock_post):
        mock_post.return_value = _mock_response(
            raise_for_status=Exception("HTTP 403")
        )

        with pytest.raises(Exception, match="HTTP 403"):
            get_demarche_schema(42)

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_graphql_errors_raised(self, mock_post):
        mock_post.return_value = _mock_response(
            json_data={"errors": [{"message": "Démarche introuvable"}]}
        )

        with pytest.raises(Exception, match="Démarche introuvable"):
            get_demarche_schema(42)

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_permission_errors_filtered(self, mock_post):
        """Les erreurs de permissions sont silencieusement ignorées."""
        mock_post.return_value = _mock_response(
            json_data={
                "errors": [
                    {"message": "hidden due to permissions"},
                    {"message": "some other error"},
                ],
                "data": {"demarche": None},
            }
        )

        with pytest.raises(Exception, match="some other error"):
            get_demarche_schema(42)

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_permission_errors_only_still_raises_if_no_data(self, mock_post):
        """Si toutes les erreurs sont des permissions et pas de data → erreur."""
        mock_post.return_value = _mock_response(
            json_data={
                "errors": [{"message": "hidden due to permissions"}],
                "data": {"demarche": None},
            }
        )

        with pytest.raises(Exception, match="Aucune donnée de démarche"):
            get_demarche_schema(42)

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_no_data_raises(self, mock_post):
        mock_post.return_value = _mock_response(json_data={"data": None})

        with pytest.raises(Exception, match="Aucune donnée de démarche"):
            get_demarche_schema(42)

    @patch("dn.schema.requests.post")
    @patch("dn.schema.API_TOKEN", "test-token")
    def test_no_active_revision_raises(self, mock_post):
        mock_post.return_value = _mock_response(
            json_data={
                "data": {
                    "demarche": {
                        "id": "d-1",
                        "number": 42,
                        "title": "Test",
                        "activeRevision": None,
                    }
                }
            }
        )

        with pytest.raises(Exception, match="Aucune révision active"):
            get_demarche_schema(42)


# ============================================================
# get_demarche_schema_robust
# ============================================================


class TestGetDemarcheSchemaRobust:
    """Tests pour get_demarche_schema_robust"""

    @patch("dn.schema.auto_clean_schema_descriptors")
    @patch("dn.schema.get_problematic_descriptor_ids_from_schema")
    @patch("dn.schema.get_demarche_schema")
    def test_success(self, mock_base, mock_ids, mock_clean):
        demarche = {
            "id": "d-1",
            "number": 42,
            "activeRevision": {
                "id": "rev-1",
                "datePublication": "2024-01-15T10:00:00Z",
                "champDescriptors": [{"__typename": "TextChampDescriptor", "id": "c1", "type": "text", "label": "Nom"}],
                "annotationDescriptors": [],
            },
        }
        mock_base.return_value = demarche
        mock_ids.return_value = set()
        mock_clean.return_value = {
            **demarche,
            "activeRevision": demarche["activeRevision"],
        }

        result = get_demarche_schema_robust(42)

        assert "metadata" in result
        assert result["metadata"]["optimized"] is True
        assert result["metadata"]["revision_id"] == "rev-1"
        assert result["metadata"]["problematic_ids"] == set()
        mock_clean.assert_called_once()

    @patch("dn.schema.get_demarche_schema")
    def test_no_active_revision_raises(self, mock_base):
        mock_base.return_value = {
            "id": "d-1",
            "number": 42,
            "activeRevision": None,
        }

        with pytest.raises(Exception, match="Aucune révision active"):
            get_demarche_schema_robust(42)

    @patch("dn.schema.get_demarche_schema")
    def test_base_failure_wraps_exception(self, mock_base):
        mock_base.side_effect = Exception("API down")

        with pytest.raises(Exception, match="Erreur lors de la récupération"):
            get_demarche_schema_robust(42)

    @patch("dn.schema.auto_clean_schema_descriptors")
    @patch("dn.schema.get_problematic_descriptor_ids_from_schema")
    @patch("dn.schema.get_demarche_schema")
    def test_problematic_ids_stored_in_metadata(self, mock_base, mock_ids, mock_clean):
        demarche = {
            "id": "d-1",
            "number": 42,
            "activeRevision": {
                "id": "rev-1",
                "champDescriptors": [],
                "annotationDescriptors": [],
            },
        }
        mock_base.return_value = demarche
        mock_ids.return_value = {"header-1", "explication-2"}
        mock_clean.return_value = {**demarche, "activeRevision": demarche["activeRevision"]}

        result = get_demarche_schema_robust(42)

        assert result["metadata"]["problematic_ids"] == {"header-1", "explication-2"}


# ============================================================
# get_demarche_schema_enhanced
# ============================================================


class TestGetDemarcheSchemaEnhanced:
    """Tests pour get_demarche_schema_enhanced"""

    @patch("dn.schema.get_demarche_schema_robust")
    def test_prefer_robust_success(self, mock_robust):
        expected = {"number": 42, "metadata": {}}
        mock_robust.return_value = expected

        result = get_demarche_schema_enhanced(42, prefer_robust=True)

        assert result == expected
        mock_robust.assert_called_once_with(42)

    @patch("dn.schema.get_demarche_schema")
    @patch("dn.schema.get_demarche_schema_robust")
    def test_prefer_robust_fallback_on_error(self, mock_robust, mock_classic):
        mock_robust.side_effect = Exception("Robust failed")
        expected = {"number": 42}
        mock_classic.return_value = expected

        result = get_demarche_schema_enhanced(42, prefer_robust=True)

        assert result == expected
        mock_classic.assert_called_once_with(42)

    @patch("dn.schema.get_demarche_schema")
    def test_prefer_classic(self, mock_classic):
        expected = {"number": 42}
        mock_classic.return_value = expected

        result = get_demarche_schema_enhanced(42, prefer_robust=False)

        assert result == expected
        mock_classic.assert_called_once_with(42)


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

        champ_descriptors = cleaned["activeRevision"]["champDescriptors"]
        assert len(champ_descriptors) == 2

        repetition = next(
            d for d in champ_descriptors
            if d.get("__typename") == "RepetitionChampDescriptor"
        )
        assert len(repetition["champDescriptors"]) == 1

        annotation_descriptors = cleaned[
            "activeRevision"
        ]["annotationDescriptors"]
        assert len(annotation_descriptors) == 1

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
        with patch("dn.schema.log") as mock_log:
            create_columns_from_schema(schema, demarche_number=42)
        mock_log.assert_any_call("Création des colonnes pour la démarche 42")

    def test_no_log_when_no_demarche_number(self):
        schema = _make_schema(champ_descriptors=[
            _make_descriptor("TextChampDescriptor", "Nom", desc_id="d1"),
        ])
        with patch("dn.schema.log") as mock_log:
            create_columns_from_schema(schema)
        for call_args in mock_log.call_args_list:
            assert "Création des colonnes" not in call_args.args[0]
