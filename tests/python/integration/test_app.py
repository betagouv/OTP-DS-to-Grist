import pytest
import json
from unittest.mock import patch
from app import app, ConfigManager, task_manager


@pytest.fixture
def client():
    """Fixture pour le client de test Flask"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_config():
    """Fixture pour mocker la configuration"""
    with patch.object(ConfigManager, 'load_config') as mock_load:
        mock_load.return_value = {
            'ds_api_token': 'test-token',
            'ds_api_url': 'https://api.test.com',
            'demarche_number': '123',
            'grist_base_url': 'https://grist.test.com',
            'grist_api_key': 'test-key',
            'grist_doc_id': 'test-doc',
            'grist_user_id': 'test-user'
        }
        yield mock_load


class TestEndpoints:
    """Tests d'intégration pour les endpoints Flask"""

    def test_index_route(self, client):
        """Test de la route d'accueil"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'One Trick Pony' in response.data

    def test_execution_route(self, client):
        """Test de la route d'exécution"""
        response = client.get('/execution')
        assert response.status_code == 200
        assert b'Synchronisation' in response.data

    def test_debug_route(self, client):
        """Test de la route de débogage"""
        response = client.get('/debug')
        assert response.status_code == 200
        assert b'debug' in response.data

    def test_use_otp_route(self, client):
        """Test de la route d'utilisation"""
        response = client.get('/utiliser-le-connecteur')
        assert response.status_code == 200
        assert b'utiliser' in response.data

    @patch.object(ConfigManager, 'load_config')
    def test_api_config_get(self, mock_load, client):
        """Test de récupération de la configuration"""
        mock_load.return_value = {
            'ds_api_token': 'secret-token',
            'ds_api_url': 'https://api.test.com',
            'demarche_number': '123',
            'grist_base_url': 'https://grist.test.com',
            'grist_api_key': 'secret-key',
            'grist_doc_id': 'doc123',
            'grist_user_id': 'user123'
        }

        response = client.get('/api/config')
        assert response.status_code == 200

        data = json.loads(response.data)
        # Vérifier que les tokens sont masqués
        assert data['ds_api_token_masked'] == '***'
        assert data['grist_api_key_masked'] == '***'
        assert data['ds_api_token_exists'] is True
        assert data['grist_api_key_exists'] is True

    @patch.object(ConfigManager, 'save_config')
    def test_api_config_post_success(self, mock_save, client):
        """Test de sauvegarde de configuration réussie"""
        mock_save.return_value = True

        config_data = {
            'ds_api_token': 'token',
            'ds_api_url': 'url',
            'demarche_number': '123',
            'grist_base_url': 'base',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }

        response = client.post(
            '/api/config',
            data=json.dumps(config_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert 'sauvegardée' in data['message']

    def test_api_config_post_missing_field(self, client):
        """Test de sauvegarde avec champ manquant"""
        config_data = {
            'ds_api_token': '',
            'ds_api_url': 'url',
            'demarche_number': '123'
            # Champs manquants
        }

        response = client.post(
            '/api/config',
            data=json.dumps(config_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'requis' in data['message']

    @patch('app.test_demarches_api')
    def test_api_test_connection_demarches(self, mock_test, client):
        """Test du endpoint de test de connexion Démarches"""
        mock_test.return_value = (True, 'Connexion réussie')

        test_data = {
            'type': 'demarches',
            'api_token': 'token',
            'demarche_number': '123'
        }

        response = client.post(
            '/api/test-connection',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['message'] == 'Connexion réussie'

    @patch('app.test_grist_api')
    def test_api_test_connection_grist(self, mock_test, client):
        """Test du endpoint de test de connexion Grist"""
        mock_test.return_value = (False, 'Erreur de connexion')

        test_data = {
            'type': 'grist',
            'base_url': 'https://grist.test.com',
            'api_key': 'key',
            'doc_id': 'doc123'
        }

        response = client.post(
            '/api/test-connection',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Erreur' in data['message']

    def test_api_test_connection_invalid_type(self, client):
        """Test avec type de connexion invalide"""
        test_data = {'type': 'invalid'}

        response = client.post(
            '/api/test-connection',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'invalide' in data['message']

    @patch.object(ConfigManager, 'load_config')
    @patch('app.get_available_groups')
    def test_api_groups(self, mock_groups, mock_load, client):
        """Test de récupération des groupes"""
        mock_load.return_value = {
            'ds_api_token': 'token',
            'demarche_number': '123'
        }
        mock_groups.return_value = [{'id': '1', 'label': 'Groupe 1'}]

        response = client.get('/api/groups')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['label'] == 'Groupe 1'

    @patch.object(task_manager, 'start_task')
    @patch.object(ConfigManager, 'load_config')
    def test_api_start_sync_success(self, mock_load, mock_start, client):
        """Test de démarrage de synchronisation réussi"""
        mock_load.return_value = {
            'ds_api_token': 'token',
            'demarche_number': '123',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }
        mock_start.return_value = 'task_123'

        sync_data = {
            'grist_user_id': 'user',
            'grist_doc_id': 'doc',
            'filters': {}
        }

        response = client.post(
            '/api/start-sync',
            data=json.dumps(sync_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['task_id'] == 'task_123'

    @patch.object(ConfigManager, 'load_config')
    def test_api_start_sync_missing_config(self, mock_load, client):
        """Test de démarrage avec configuration manquante"""
        mock_load.return_value = {
            'ds_api_token': '',
            'demarche_number': '123'
            # Champs manquants
        }

        sync_data = {'filters': {}}

        response = client.post(
            '/api/start-sync',
            data=json.dumps(sync_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'manquants' in data['message']

    @patch.object(task_manager, 'get_task')
    def test_api_task_status_found(self, mock_get, client):
        """Test de récupération du statut d'une tâche existante"""
        mock_get.return_value = {'status': 'running', 'progress': 50}

        response = client.get('/api/task/task_123')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'running'
        assert data['progress'] == 50

    @patch.object(task_manager, 'get_task')
    def test_api_task_status_not_found(self, mock_get, client):
        """Test de récupération du statut d'une tâche inexistante"""
        mock_get.return_value = None

        response = client.get('/api/task/task_999')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert 'non trouvée' in data['error']


class TestErrorHandling:
    """Tests d'intégration pour la gestion d'erreurs"""

    @patch('app.test_demarches_api')
    def test_api_test_connection_demarches_timeout(self, mock_test, client):
        """Test timeout API Démarches"""
        mock_test.return_value = (
            False,
            "Timeout: L'API met trop de temps à répondre"
        )

        test_data = {
            'type': 'demarches',
            'api_token': 'token',
            'demarche_number': '123'
        }

        response = client.post(
            '/api/test-connection',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Timeout' in data['message']

    @patch('app.test_demarches_api')
    def test_api_test_connection_demarches_invalid_token(
            self,
            mock_test,
            client
    ):
        """Test token invalide Démarches"""
        mock_test.return_value = (False, "Erreur API: Unauthorized")

        test_data = {
            'type': 'demarches',
            'api_token': 'invalid-token',
            'demarche_number': '123'
        }

        response = client.post(
            '/api/test-connection',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Unauthorized' in data['message']

    @patch('app.test_grist_api')
    def test_api_test_connection_grist_network_error(self, mock_test, client):
        """Test erreur réseau Grist"""
        mock_test.return_value = (
            False,
            "Erreur de connexion: Network is unreachable"
        )

        test_data = {
            'type': 'grist',
            'base_url': 'https://grist.test.com',
            'api_key': 'key',
            'doc_id': 'doc123'
        }

        response = client.post(
            '/api/test-connection',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Network' in data['message']

    @patch('app.test_grist_api')
    def test_api_test_connection_grist_invalid_key(self, mock_test, client):
        """Test clé API invalide Grist"""
        mock_test.return_value = (
            False,
            "Erreur de connexion à Grist: 401 - Unauthorized"
        )

        test_data = {
            'type': 'grist',
            'base_url': 'https://grist.test.com',
            'api_key': 'invalid-key',
            'doc_id': 'doc123'
        }

        response = client.post(
            '/api/test-connection',
            data=json.dumps(test_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is False
        assert '401' in data['message']

    @patch.object(ConfigManager, 'load_config')
    def test_api_start_sync_missing_demarche_token(self, mock_load, client):
        """Test démarrage sync avec token manquant"""
        mock_load.return_value = {
            'ds_api_token': '',  # Manquant
            'demarche_number': '123',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }

        sync_data = {
            'grist_user_id': 'user',
            'grist_doc_id': 'doc',
            'filters': {}
        }

        response = client.post(
            '/api/start-sync',
            data=json.dumps(sync_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'manquants' in data['message']
        assert 'ds_api_token' in data['missing_fields']

    @patch.object(ConfigManager, 'load_config')
    def test_api_start_sync_missing_demarche_number(self, mock_load, client):
        """Test démarrage sync avec numéro démarche manquant"""
        mock_load.return_value = {
            'ds_api_token': 'token',
            'demarche_number': '',  # Manquant
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }

        sync_data = {
            'grist_user_id': 'user',
            'grist_doc_id': 'doc',
            'filters': {}
        }

        response = client.post(
            '/api/start-sync',
            data=json.dumps(sync_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'manquants' in data['message']
        assert 'demarche_number' in data['missing_fields']

    @patch('app.run_synchronization_task')
    @patch.object(ConfigManager, 'load_config')
    def test_api_start_sync_task_failure(self, mock_load, mock_run, client):
        """Test échec de tâche de synchronisation"""
        mock_load.return_value = {
            'ds_api_token': 'token',
            'demarche_number': '123',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }
        mock_run.return_value = {
            "success": False,
            "message": "Erreur lors du traitement"
        }

        sync_data = {
            'grist_user_id': 'user',
            'grist_doc_id': 'doc',
            'filters': {}
        }

        response = client.post(
            '/api/start-sync',
            data=json.dumps(sync_data),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] is True  # Tâche démarrée, même si elle échoue
        assert 'task_id' in data

    @patch.object(ConfigManager, 'save_config')
    def test_api_config_post_save_failure(self, mock_save, client):
        """Test échec de sauvegarde configuration"""
        mock_save.return_value = False

        config_data = {
            'ds_api_token': 'token',
            'ds_api_url': 'url',
            'demarche_number': '123',
            'grist_base_url': 'base',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }

        response = client.post(
            '/api/config',
            data=json.dumps(config_data),
            content_type='application/json'
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'Erreur lors de la sauvegarde' in data['message']
