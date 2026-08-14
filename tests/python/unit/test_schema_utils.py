from unittest.mock import MagicMock, patch

from schema_utils import (
    get_problematic_descriptor_ids_from_schema,
    auto_clean_schema_descriptors,
    update_grist_tables_from_schema,
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


class TestUpdateGristTablesFromSchema:
    """Tests unitaires pour la fonction imbriquée add_missing_columns
    via update_grist_tables_from_schema"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"
        self.client.headers = {}
        self.client.list_tables = MagicMock(
            return_value={"tables": [{"id": "Demarche_123_dossiers"}]}
        )
        self.client.create_table = MagicMock(
            return_value={"tables": [{"id": "creee", "columns": []}]}
        )

    def _column_types(self):
        return {
            "dossier": [{"id": "nouveau_col", "type": "Text"}],
            "champs": [{"id": "existant", "type": "Text"}],
            "annotations": [{"id": "dossier_number", "type": "Int"}],
        }

    def _mock_get(self, status=200, columns=None):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = {"columns": columns or []}
        return response

    def test_adds_only_missing_columns(self):
        """seules les colonnes manquantes de la table dossiers sont POSTées"""
        get_response = self._mock_get(columns=[{"id": "existant", "type": "Text"}])
        post_response = MagicMock()
        post_response.status_code = 200
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.get", return_value=get_response),
            patch("schema_utils.requests.post", return_value=post_response) as mock_post,
        ):
            result = update_grist_tables_from_schema(
                self.client, 123, self._column_types()
            )
        assert result["dossiers"] == "Demarche_123_dossiers"
        column_posts = [
            c
            for c in mock_post.call_args_list
            if "columns" in c.kwargs.get("json", {})
        ]
        assert len(column_posts) == 1
        payload = column_posts[0].kwargs["json"]
        assert payload == {"columns": [{"id": "nouveau_col", "type": "Text"}]}
        assert column_posts[0].args[0].endswith(
            "/tables/Demarche_123_dossiers/columns"
        )

    def test_get_error_no_post(self):
        """GET en échec -> aucun POST de colonnes"""
        get_response = self._mock_get(status=500)
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.get", return_value=get_response),
            patch("schema_utils.requests.post") as mock_post,
        ):
            result = update_grist_tables_from_schema(
                self.client, 123, self._column_types()
            )
        assert result["dossiers"] == "Demarche_123_dossiers"
        column_posts = [
            c
            for c in mock_post.call_args_list
            if "columns" in c.kwargs.get("json", {})
        ]
        assert column_posts == []
