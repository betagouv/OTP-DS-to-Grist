import pytest
from unittest.mock import patch, MagicMock


def _make_dossier_response(typename):
    """Construit une réponse GraphQL simulée pour detect_demandeur_type."""
    return {
        "data": {
            "demarche": {
                "dossiers": {
                    "nodes": [{"id": 1, "demandeur": {"__typename": typename}}]
                }
            }
        }
    }


class TestDetectDemandeurType:
    """Tests unitaires pour detect_demandeur_type."""

    @patch("sync.demandeurs.requests.post")
    @patch("sync.demandeurs.API_TOKEN", "test-token")
    def test_returns_personne_physique(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=lambda: _make_dossier_response("PersonnePhysique"),
        )
        from sync.demandeurs import detect_demandeur_type

        assert detect_demandeur_type(42) == "PersonnePhysique"

    @patch("sync.demandeurs.requests.post")
    @patch("sync.demandeurs.API_TOKEN", "test-token")
    def test_returns_personne_morale(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=lambda: _make_dossier_response("PersonneMorale"),
        )
        from sync.demandeurs import detect_demandeur_type

        assert detect_demandeur_type(42) == "PersonneMorale"

    @patch("sync.demandeurs.requests.post")
    @patch("sync.demandeurs.API_TOKEN", "test-token")
    def test_personne_morale_incomplete_treated_as_morale(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=lambda: _make_dossier_response("PersonneMoraleIncomplete"),
        )
        from sync.demandeurs import detect_demandeur_type

        assert detect_demandeur_type(42) == "PersonneMorale"

    @patch("sync.demandeurs.requests.post")
    @patch("sync.demandeurs.API_TOKEN", "test-token")
    def test_no_dossiers_defaults_to_morale(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=lambda: {"data": {"demarche": {"dossiers": {"nodes": []}}}},
        )
        from sync.demandeurs import detect_demandeur_type

        assert detect_demandeur_type(42) == "PersonneMorale"

    @patch("sync.demandeurs.requests.post")
    @patch("sync.demandeurs.API_TOKEN", "test-token")
    def test_graphql_error_returns_none(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=lambda: {"errors": [{"message": "Erreur"}], "data": {"demarche": None}},
        )
        from sync.demandeurs import detect_demandeur_type

        assert detect_demandeur_type(42) is None

    @patch("sync.demandeurs.requests.post")
    @patch("sync.demandeurs.API_TOKEN", "test-token")
    def test_api_error_defaults_to_morale(self, mock_post):
        mock_post.side_effect = Exception("timeout")
        from sync.demandeurs import detect_demandeur_type

        assert detect_demandeur_type(42) == "PersonneMorale"

    @patch("sync.demandeurs.API_TOKEN", None)
    def test_missing_token_raises(self):
        from sync.demandeurs import detect_demandeur_type

        with pytest.raises(ValueError):
            detect_demandeur_type(42)

    @patch("sync.demandeurs.requests.post")
    @patch("sync.demandeurs.API_TOKEN", "test-token")
    def test_sends_correct_query(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            raise_for_status=MagicMock(),
            json=lambda: _make_dossier_response("PersonnePhysique"),
        )
        from sync.demandeurs import detect_demandeur_type

        detect_demandeur_type(42)
        payload = mock_post.call_args.kwargs["json"]
        assert payload["variables"]["demarcheNumber"] == 42
        assert "getFirstDossier" in payload["query"]


class TestCreateDemandeursColumns:
    """Tests unitaires pour create_demandeurs_columns."""

    @patch("sync.demandeurs.detect_demandeur_type", return_value="PersonnePhysique")
    def test_pp_returns_pp_columns(self, mock_detect):
        from sync.demandeurs import create_demandeurs_columns

        columns, dtype = create_demandeurs_columns(42)
        assert dtype == "PersonnePhysique"
        assert isinstance(columns, list)
        assert any(c["id"] == "nom" for c in columns)

    @patch("sync.demandeurs.detect_demandeur_type", return_value="PersonneMorale")
    def test_pm_returns_pm_columns(self, mock_detect):
        from sync.demandeurs import create_demandeurs_columns

        columns, dtype = create_demandeurs_columns(42)
        assert dtype == "PersonneMorale"
        assert isinstance(columns, list)
        assert any(c["id"] == "siret" for c in columns)
