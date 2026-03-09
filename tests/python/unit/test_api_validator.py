"""
Tests unitaires pour api_validator.py
"""

from unittest.mock import patch, MagicMock
from api_validator import (
    test_demarches_api as demarches_api_tester,
    test_grist_api as grist_api_tester,
    verify_api_connections
)


class TestTestDemarchesApi:
    """Tests pour test_demarches_api"""

    @patch('api_validator.requests.post')
    def test_success_with_demarche_number(self, mock_post):
        """Test réussi avec numéro de démarche"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {
                'demarche': {
                    'id': '123',
                    'number': 123,
                    'title': 'Test Démarche'
                }
            }
        }
        mock_post.return_value = mock_response

        success, message = demarches_api_tester('token123', 123)

        assert success is True
        assert 'Connexion réussie' in message
        assert 'Test Démarche' in message

    @patch('api_validator.requests.post')
    def test_api_error(self, mock_post):
        """Test avec erreur API"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'errors': [{'message': 'Token invalide'}]
        }
        mock_post.return_value = mock_response

        success, message = demarches_api_tester('invalid-token', '123')

        assert success is False
        assert 'Erreur API' in message
        assert 'Token invalide' in message

    @patch('api_validator.requests.post')
    def test_http_error(self, mock_post):
        """Test avec erreur HTTP"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = 'Unauthorized'
        mock_post.return_value = mock_response

        success, message = demarches_api_tester('token123', '123')

        assert success is False
        assert '401' in message

    @patch('api_validator.requests.post')
    def test_timeout(self, mock_post):
        """Test avec timeout"""
        from requests.exceptions import Timeout
        mock_post.side_effect = Timeout('Connection timed out')

        success, message = demarches_api_tester('token123', '123')

        assert success is False
        assert 'Timeout' in message

    @patch('api_validator.requests.post')
    def test_exception(self, mock_post):
        """Test avec exception générique"""
        mock_post.side_effect = Exception('Network error')

        success, message = demarches_api_tester('token123', '123')

        assert success is False
        assert 'Erreur de connexion' in message

    @patch('api_validator.requests.post')
    def test_expired_token(self, mock_post):
        """Test avec token expiré"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            'errors': [{'message': 'Token expired'}]
        }
        mock_post.return_value = mock_response
        success, message = demarches_api_tester('expired-token', '123')
        assert success is False
        assert 'Token expiré' in message


class TestTestGristApi:
    """Tests pour test_grist_api"""

    @patch('api_validator.requests.get')
    def test_success(self, mock_get):
        """Test réussi"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'name': 'Mon Document'}
        mock_get.return_value = mock_response

        success, message = grist_api_tester(
            'https://grist.example.com',
            'api-key',
            'doc123'
        )

        assert success is True
        assert 'Connexion à Grist réussie' in message
        assert 'Mon Document' in message

    @patch('api_validator.requests.get')
    def test_success_without_name(self, mock_get):
        """Test réussi sans nom de document"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Pas de champ 'name'
        mock_get.return_value = mock_response

        success, message = grist_api_tester(
            'https://grist.example.com',
            'api-key',
            'doc123'
        )

        assert success is True
        assert 'doc123' in message

    @patch('api_validator.requests.get')
    def test_http_error(self, mock_get):
        """Test avec erreur HTTP"""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = 'Not Found'
        mock_get.return_value = mock_response

        success, message = grist_api_tester(
            'https://grist.example.com',
            'api-key',
            'doc123'
        )

        assert success is False
        assert '404' in message

    @patch('api_validator.requests.get')
    def test_timeout(self, mock_get):
        """Test avec timeout"""
        from requests.exceptions import Timeout
        mock_get.side_effect = Timeout('Connection timed out')

        success, message = grist_api_tester(
            'https://grist.example.com',
            'api-key',
            'doc123'
        )

        assert success is False
        assert 'Timeout' in message


class TestVerifyApiConnections:
    """Tests pour verify_api_connections"""

    @patch('api_validator.test_demarches_api')
    @patch('api_validator.test_grist_api')
    def test_both_success(self, mock_grist, mock_demarches):
        """Test avec succès des deux APIs"""
        mock_demarches.return_value = (True, 'DS OK')
        mock_grist.return_value = (True, 'Grist OK')

        success, results = verify_api_connections(
            'ds-token',
            '123',
            'https://grist.example.com',
            'grist-key',
            'doc123'
        )

        assert success is True
        assert len(results) == 2
        assert results[0]['type'] == 'demarches'
        assert results[0]['success'] is True
        assert results[1]['type'] == 'grist'
        assert results[1]['success'] is True

    @patch('api_validator.test_demarches_api')
    @patch('api_validator.test_grist_api')
    def test_partial_failure(self, mock_grist, mock_demarches):
        """Test avec échec partiel"""
        mock_demarches.return_value = (True, 'DS OK')
        mock_grist.return_value = (False, 'Grist Error')

        success, results = verify_api_connections(
            'ds-token',
            '123',
            'https://grist.example.com',
            'grist-key',
            'doc123'
        )

        assert success is False
        assert results[0]['success'] is True
        assert results[1]['success'] is False

    @patch('api_validator.test_demarches_api')
    @patch('api_validator.test_grist_api')
    def test_both_failure(self, mock_grist, mock_demarches):
        """Test avec échec des deux APIs"""
        mock_demarches.return_value = (False, 'DS Error')
        mock_grist.return_value = (False, 'Grist Error')

        success, results = verify_api_connections(
            'ds-token',
            '123',
            'https://grist.example.com',
            'grist-key',
            'doc123'
        )

        assert success is False
        assert all(not r['success'] for r in results)

    @patch('api_validator.test_demarches_api')
    @patch('api_validator.test_grist_api')
    def test_calls_with_correct_params(self, mock_grist, mock_demarches):
        """Test que les fonctions sont appelées avec les bons paramètres"""
        mock_demarches.return_value = (True, 'DS OK')
        mock_grist.return_value = (True, 'Grist OK')

        verify_api_connections(
            'ds-token',
            '123',
            'https://grist.example.com',
            'grist-key',
            'doc123'
        )

        mock_demarches.assert_called_once_with('ds-token', '123')
        mock_grist.assert_called_once_with(
            'https://grist.example.com',
            'grist-key',
            'doc123'
        )
