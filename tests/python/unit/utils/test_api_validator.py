"""
Tests unitaires pour api_validator.py
"""

import requests
from unittest.mock import patch, MagicMock

from grist.base_url import GristBaseUrlNotAllowedError
from utils.api_validator import (
    test_demarches_api as demarches_api_tester,
    test_grist_api as grist_api_tester,
    verify_api_connections,
)


class TestTestDemarchesApi:
    """Tests pour test_demarches_api"""

    @patch("utils.api_validator.requests.post")
    def test_success_with_demarche_number(self, mock_post):
        """Test réussi avec numéro de démarche"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"demarche": {"id": "123", "number": 123, "title": "Test Démarche"}}
        }
        mock_post.return_value = mock_response

        success, message, title = demarches_api_tester("token123", 123)

        assert success is True
        assert "Connexion réussie" in message
        assert "Test Démarche" in message
        assert title == "Test Démarche"

    @patch("utils.api_validator.requests.post")
    def test_api_error(self, mock_post):
        """Test avec erreur API"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "Token invalide"}]}
        mock_post.return_value = mock_response

        success, message, title = demarches_api_tester("invalid-token", "123")

        assert success is False
        assert "Erreur API" in message
        assert "Token invalide" in message
        assert title is None

    @patch("utils.api_validator.requests.post")
    def test_http_error(self, mock_post):
        """Test avec erreur HTTP"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        success, message, title = demarches_api_tester("token123", "123")

        assert success is False
        assert "401" in message
        assert title is None

    @patch("utils.api_validator.requests.post")
    def test_timeout(self, mock_post):
        """Test avec timeout"""
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout("Connection timed out")

        success, message, title = demarches_api_tester("token123", "123")

        assert success is False
        assert "Timeout" in message
        assert title is None

    @patch("utils.api_validator.requests.post")
    def test_exception(self, mock_post):
        """Test avec exception générique"""
        mock_post.side_effect = Exception("Network error")

        success, message, title = demarches_api_tester("token123", "123")

        assert success is False
        assert "Erreur de connexion" in message
        assert title is None

    @patch("utils.api_validator.requests.post")
    def test_expired_token(self, mock_post):
        """Test avec token expiré"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"errors": [{"message": "Token expired"}]}
        mock_post.return_value = mock_response
        success, message, title = demarches_api_tester("expired-token", "123")
        assert success is False
        assert "Token expiré" in message
        assert title is None


class TestTestGristApi:
    """Tests pour test_grist_api"""

    def test_success(self):
        """Test réussi"""
        mock_client = MagicMock()
        mock_client.get_document_info.return_value = {"name": "Mon Document"}

        with patch("utils.api_validator.GristClient", return_value=mock_client):
            success, message = grist_api_tester(
                "https://grist.example.com", "api-key", "doc123"
            )

        assert success is True
        assert "Connexion à Grist réussie" in message
        assert "Mon Document" in message

    def test_success_without_name(self):
        """Test réussi sans nom de document"""
        mock_client = MagicMock()
        mock_client.get_document_info.return_value = {}

        with patch("utils.api_validator.GristClient", return_value=mock_client):
            success, message = grist_api_tester(
                "https://grist.example.com", "api-key", "doc123"
            )

        assert success is True
        assert "doc123" in message

    def test_http_error(self):
        """Test avec erreur HTTP"""
        mock_client = MagicMock()
        mock_client.get_document_info.side_effect = requests.exceptions.HTTPError(
            response=MagicMock(status_code=404, text="Not Found")
        )

        with patch("utils.api_validator.GristClient", return_value=mock_client):
            success, message = grist_api_tester(
                "https://grist.example.com", "api-key", "doc123"
            )

        assert success is False
        assert "404" in message

    def test_timeout(self):
        """Test avec timeout"""
        mock_client = MagicMock()
        mock_client.get_document_info.side_effect = requests.exceptions.Timeout(
            "Connection timed out"
        )

        with patch("utils.api_validator.GristClient", return_value=mock_client):
            success, message = grist_api_tester(
                "https://grist.example.com", "api-key", "doc123"
            )

        assert success is False
        assert "Timeout" in message

    def test_client_built_with_parameters(self):
        """GristClient reçoit base_url, api_key et doc_id"""
        with patch("utils.api_validator.GristClient") as mock_class:
            mock_class.return_value.get_document_info.return_value = {"name": "Doc"}
            grist_api_tester("https://grist.example.com", "api-key", "doc123")

        mock_class.assert_called_once_with(
            "https://grist.example.com", "api-key", "doc123"
        )

    def test_base_url_outside_whitelist(self):
        """URL hors liste blanche → (False, message), aucune requête émise"""
        refusal = GristBaseUrlNotAllowedError(
            "URL de base Grist non autorisée : grist.evil.example "
            "(liste des instances autorisées définie par GRIST_BASE_URL_WHITELIST)"
        )
        mock_class = MagicMock(side_effect=refusal)

        with patch("utils.api_validator.GristClient", mock_class):
            success, message = grist_api_tester(
                "https://grist.evil.example", "api-key", "doc123"
            )

        assert success is False
        assert "grist.evil.example" in message
        mock_class.assert_called_once_with(
            "https://grist.evil.example", "api-key", "doc123"
        )

    def test_unparseable_json_returns_success(self):
        """Réponse 200 illisible en JSON → succès avec l'ID du document"""
        mock_client = MagicMock()
        mock_client.get_document_info.side_effect = (
            requests.exceptions.JSONDecodeError("Expecting value", "doc", 0)
        )

        with patch("utils.api_validator.GristClient", return_value=mock_client):
            success, message = grist_api_tester(
                "https://grist.example.com", "api-key", "doc123"
            )

        assert success is True
        assert "doc123" in message


class TestVerifyApiConnections:
    """Tests pour verify_api_connections"""

    @patch("utils.api_validator.test_demarches_api")
    @patch("utils.api_validator.test_grist_api")
    def test_both_success(self, mock_grist, mock_demarches):
        """Test avec succès des deux APIs"""
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
        mock_grist.return_value = (True, "Grist OK")

        success, results = verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        assert success is True
        assert len(results) == 2
        assert results[0]["type"] == "demarches"
        assert results[0]["success"] is True
        assert results[1]["type"] == "grist"
        assert results[1]["success"] is True

    @patch("utils.api_validator.test_demarches_api")
    @patch("utils.api_validator.test_grist_api")
    def test_partial_failure(self, mock_grist, mock_demarches):
        """Test avec échec partiel"""
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
        mock_grist.return_value = (False, "Grist Error")

        success, results = verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        assert success is False
        assert results[0]["success"] is True
        assert results[1]["success"] is False

    @patch("utils.api_validator.test_demarches_api")
    @patch("utils.api_validator.test_grist_api")
    def test_both_failure(self, mock_grist, mock_demarches):
        """Test avec échec des deux APIs"""
        mock_demarches.return_value = (False, "DS Error", None)
        mock_grist.return_value = (False, "Grist Error")

        success, results = verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        assert success is False
        assert all(not r["success"] for r in results)

    @patch("utils.api_validator.test_demarches_api")
    @patch("utils.api_validator.test_grist_api")
    def test_calls_with_correct_params(self, mock_grist, mock_demarches):
        """Test que les fonctions sont appelées avec les bons paramètres"""
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
        mock_grist.return_value = (True, "Grist OK")

        verify_api_connections(
            "ds-token", "123", "https://grist.example.com", "grist-key", "doc123"
        )

        mock_demarches.assert_called_once_with("ds-token", "123")
        mock_grist.assert_called_once_with(
            "https://grist.example.com", "grist-key", "doc123"
        )
