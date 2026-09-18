from unittest.mock import MagicMock, patch

from dn.client import get_groups


class TestGetGroups:
    """Tests pour get_groups"""

    def test_missing_api_token_returns_empty(self):
        """Token manquant → retourne []"""
        assert get_groups(None, "123") == []
        assert get_groups("", "123") == []

    def test_missing_demarche_number_returns_empty(self):
        """Numéro de démarche manquant → retourne []"""
        assert get_groups("token", None) == []
        assert get_groups("token", "") == []

    @patch("dn.client.get_session_with_retries")
    def test_success_returns_groups(self, mock_session_factory):
        """Appel réussi → retourne liste de tuples (number, label)"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "demarche": {
                    "groupeInstructeurs": [
                        {"number": 1, "label": "Groupe A"},
                        {"number": 2, "label": "Groupe B"},
                    ]
                }
            }
        }
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        result = get_groups("token123", "456")

        assert result == [(1, "Groupe A"), (2, "Groupe B")]
        mock_session.post.assert_called_once()

    @patch("dn.client.get_session_with_retries")
    def test_api_error_status_returns_empty(self, mock_session_factory):
        """Statut HTTP != 200 → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_groups("token", "123") == []

    @patch("dn.client.get_session_with_retries")
    def test_graphql_errors_returns_empty(self, mock_session_factory):
        """Erreurs GraphQL dans la réponse → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "Unauthorized"}]}
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_groups("token", "123") == []

    @patch("dn.client.get_session_with_retries")
    def test_empty_demarche_returns_empty(self, mock_session_factory):
        """Démarche sans groupe instructeur → retourne []"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"demarche": {"groupeInstructeurs": []}}
        }
        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session_factory.return_value = mock_session

        assert get_groups("token", "123") == []

    @patch("dn.client.get_session_with_retries", side_effect=Exception("Network error"))
    def test_exception_returns_empty(self, mock_session_factory):
        """Exception quelconque → retourne []"""
        assert get_groups("token", "123") == []