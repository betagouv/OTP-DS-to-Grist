import pytest
from unittest.mock import MagicMock, patch

import schema_utils
from schema_utils import (
    detect_demandeur_type,
    get_demarche_schema,
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

    def test_adds_only_missing_columns(self):
        """seules les colonnes manquantes de la table dossiers sont POSTées"""
        self.client.get_columns.return_value = {"existant": "Text"}
        post_response = MagicMock()
        post_response.status_code = 200
        self.client.add_columns.return_value = post_response
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            result = update_grist_tables_from_schema(
                self.client, 123, self._column_types()
            )
        assert result["dossiers"] == "Demarche_123_dossiers"
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "Demarche_123_dossiers"
        assert self.client.add_columns.call_args.args[1] == [
            {"id": "nouveau_col", "type": "Text"}
        ]
        assert mock_post.call_count == 1
        assert "columns" not in mock_post.call_args.kwargs["json"]

    def test_get_error_no_post(self):
        """GET en échec -> aucun POST de colonnes"""
        self.client.get_columns.return_value = {}
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            result = update_grist_tables_from_schema(
                self.client, 123, self._column_types()
            )
        assert result["dossiers"] == "Demarche_123_dossiers"
        self.client.add_columns.assert_not_called()
        column_posts = [
            c
            for c in mock_post.call_args_list
            if "columns" in c.kwargs.get("json", {})
        ]
        assert column_posts == []


class TestDetectDemandeurType:
    """Tests unitaires pour schema_utils.detect_demandeur_type"""

    @staticmethod
    def _payload(demandeur_type=None, nodes=None):
        if nodes is None:
            nodes = (
                [{"demandeur": {"__typename": demandeur_type}}]
                if demandeur_type
                else []
            )
        return {"data": {"demarche": {"dossiers": {"nodes": nodes}}}}

    def test_personne_physique_detected(self):
        """Le type PersonnePhysique du premier dossier est renvoyé"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = self._payload(
                "PersonnePhysique"
            )
            result = detect_demandeur_type(12345)
        assert result == "PersonnePhysique"

    def test_personne_morale_detected(self):
        """Le type PersonneMorale du premier dossier est renvoyé"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = self._payload("PersonneMorale")
            result = detect_demandeur_type(12345)
        assert result == "PersonneMorale"

    def test_personne_morale_incomplete_mapped_to_morale(self):
        """PersonneMoraleIncomplete est traité comme PersonneMorale"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = self._payload(
                "PersonneMoraleIncomplete"
            )
            result = detect_demandeur_type(12345)
        assert result == "PersonneMorale"

    def test_no_dossier_returns_default_morale(self):
        """Aucun dossier → type par défaut PersonneMorale"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = self._payload(nodes=[])
            result = detect_demandeur_type(12345)
        assert result == "PersonneMorale"

    def test_graphql_errors_return_none(self):
        """Présence de 'errors' dans la réponse → None"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = {
                "errors": [{"message": "boom"}]
            }
            result = detect_demandeur_type(12345)
        assert result is None

    def test_http_error_returns_default_morale(self):
        """Exception HTTP (raise_for_status) → type par défaut PersonneMorale"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.raise_for_status.side_effect = Exception(
                "HTTP 500"
            )
            result = detect_demandeur_type(12345)
        assert result == "PersonneMorale"

    def test_missing_token_raises_value_error(self):
        """Token non configuré → ValueError, sans appel réseau"""
        with (
            patch("schema_utils.API_TOKEN", None),
            patch("schema_utils.requests.post") as mock_post,
        ):
            with pytest.raises(ValueError):
                detect_demandeur_type(12345)
        mock_post.assert_not_called()

    def test_request_contract(self):
        """La requête POST est bien formée (URL, headers, variables, timeout)"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = self._payload(
                "PersonnePhysique"
            )
            detect_demandeur_type(12345)
        mock_post.assert_called_once()
        call = mock_post.call_args
        assert call.args[0] == schema_utils.API_URL
        assert call.kwargs["headers"] == {
            "Authorization": "Bearer fake-token",
            "Content-Type": "application/json",
        }
        assert call.kwargs["json"]["variables"] == {"demarcheNumber": 12345}
        assert call.kwargs["timeout"] == 30


class TestGetDemarcheSchema:
    """Tests unitaires pour schema_utils.get_demarche_schema"""

    DEMARCHE = {
        "id": "D1",
        "number": 12345,
        "activeRevision": {
            "id": "R1",
            "champDescriptors": [],
            "annotationDescriptors": [],
        },
    }

    def test_nominal_returns_demarche(self):
        """Le dict demarche complet (avec activeRevision) est renvoyé"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = {
                "data": {"demarche": self.DEMARCHE}
            }
            result = get_demarche_schema(12345)
        assert result == self.DEMARCHE

    def test_non_permission_graphql_errors_raise(self):
        """Erreurs GraphQL hors permissions → Exception"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = {
                "errors": [{"message": "Access denied"}]
            }
            with pytest.raises(Exception, match="GraphQL errors"):
                get_demarche_schema(12345)

    def test_permission_errors_are_ignored(self):
        """Erreurs de permissions seules → le schéma est renvoyé"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = {
                "errors": [
                    {"message": "hidden due to permissions"},
                    {"message": "no permissions"},
                ],
                "data": {"demarche": self.DEMARCHE},
            }
            result = get_demarche_schema(12345)
        assert result == self.DEMARCHE

    def test_missing_demarche_raises(self):
        """data.demarche absent → Exception"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = {"data": {}}
            with pytest.raises(Exception, match="Aucune donnée de démarche"):
                get_demarche_schema(12345)

    def test_missing_active_revision_raises(self):
        """activeRevision absent → Exception"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = {
                "data": {"demarche": {"id": "D1"}}
            }
            with pytest.raises(Exception, match="Aucune révision active"):
                get_demarche_schema(12345)

    def test_request_contract_includes_type_in_fragment(self):
        """La requête inclut le champ 'type' dans ChampDescriptorFragment
        (dépendance de create_columns_from_schema) et un header d'authentification"""
        with (
            patch("schema_utils.API_TOKEN", "fake-token"),
            patch("schema_utils.requests.post") as mock_post,
        ):
            mock_post.return_value.json.return_value = {
                "data": {"demarche": self.DEMARCHE}
            }
            get_demarche_schema(12345)
        call = mock_post.call_args
        assert call.args[0] == schema_utils.API_URL
        assert call.kwargs["headers"]["Authorization"] == "Bearer fake-token"
        assert call.kwargs["json"]["variables"] == {"demarcheNumber": 12345}
        query = call.kwargs["json"]["query"]
        assert "fragment ChampDescriptorFragment" in query
        fragment = query.split("fragment ChampDescriptorFragment")[1]
        assert "type" in fragment
        assert "__typename" in fragment
