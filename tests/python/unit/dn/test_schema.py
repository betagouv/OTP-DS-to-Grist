"""
Tests unitaires pour les fonctions de récupération de schéma dans schema_utils.py:
- get_demarche_schema
- get_demarche_schema_robust
- get_demarche_schema_enhanced
"""

from unittest.mock import MagicMock, patch

import pytest

from schema_utils import (
    get_demarche_schema,
    get_demarche_schema_enhanced,
    get_demarche_schema_robust,
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

    @patch("schema_utils.API_TOKEN", "")
    def test_no_token_raises(self):
        with pytest.raises(ValueError, match="token"):
            get_demarche_schema(42)

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
    def test_success(self, mock_post):
        mock_post.return_value = _mock_response(
            json_data=_make_demarche_response()
        )

        result = get_demarche_schema(42)

        assert result["number"] == 42
        assert result["title"] == "Test"
        assert "activeRevision" in result
        mock_post.assert_called_once()

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
    def test_success_converts_demarche_number_to_int(self, mock_post):
        mock_post.return_value = _mock_response(
            json_data=_make_demarche_response()
        )

        get_demarche_schema("42")

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["variables"]["demarcheNumber"] == 42

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
    def test_http_error(self, mock_post):
        mock_post.return_value = _mock_response(
            raise_for_status=Exception("HTTP 403")
        )

        with pytest.raises(Exception, match="HTTP 403"):
            get_demarche_schema(42)

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
    def test_graphql_errors_raised(self, mock_post):
        mock_post.return_value = _mock_response(
            json_data={"errors": [{"message": "Démarche introuvable"}]}
        )

        with pytest.raises(Exception, match="Démarche introuvable"):
            get_demarche_schema(42)

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
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

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
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

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
    def test_no_data_raises(self, mock_post):
        mock_post.return_value = _mock_response(json_data={"data": None})

        with pytest.raises(Exception, match="Aucune donnée de démarche"):
            get_demarche_schema(42)

    @patch("schema_utils.requests.post")
    @patch("schema_utils.API_TOKEN", "test-token")
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

    @patch("schema_utils.auto_clean_schema_descriptors")
    @patch("schema_utils.get_problematic_descriptor_ids_from_schema")
    @patch("schema_utils.get_demarche_schema")
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

    @patch("schema_utils.get_demarche_schema")
    def test_no_active_revision_raises(self, mock_base):
        mock_base.return_value = {
            "id": "d-1",
            "number": 42,
            "activeRevision": None,
        }

        with pytest.raises(Exception, match="Aucune révision active"):
            get_demarche_schema_robust(42)

    @patch("schema_utils.get_demarche_schema")
    def test_base_failure_wraps_exception(self, mock_base):
        mock_base.side_effect = Exception("API down")

        with pytest.raises(Exception, match="Erreur lors de la récupération"):
            get_demarche_schema_robust(42)

    @patch("schema_utils.auto_clean_schema_descriptors")
    @patch("schema_utils.get_problematic_descriptor_ids_from_schema")
    @patch("schema_utils.get_demarche_schema")
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

    @patch("schema_utils.get_demarche_schema_robust")
    def test_prefer_robust_success(self, mock_robust):
        expected = {"number": 42, "metadata": {}}
        mock_robust.return_value = expected

        result = get_demarche_schema_enhanced(42, prefer_robust=True)

        assert result == expected
        mock_robust.assert_called_once_with(42)

    @patch("schema_utils.get_demarche_schema")
    @patch("schema_utils.get_demarche_schema_robust")
    def test_prefer_robust_fallback_on_error(self, mock_robust, mock_classic):
        mock_robust.side_effect = Exception("Robust failed")
        expected = {"number": 42}
        mock_classic.return_value = expected

        result = get_demarche_schema_enhanced(42, prefer_robust=True)

        assert result == expected
        mock_classic.assert_called_once_with(42)

    @patch("schema_utils.get_demarche_schema")
    def test_prefer_classic(self, mock_classic):
        expected = {"number": 42}
        mock_classic.return_value = expected

        result = get_demarche_schema_enhanced(42, prefer_robust=False)

        assert result == expected
        mock_classic.assert_called_once_with(42)
