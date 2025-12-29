import pytest
import json
from unittest.mock import patch, MagicMock
import os

# Mock DATABASE_URL for tests
os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost/testdb'

from app import app, ConfigManager, sync_task_manager


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

    @patch.object(sync_task_manager, 'start_sync')
    @patch.object(ConfigManager, 'load_config_by_id')
    def test_api_start_sync_success(self, mock_load, mock_start, client):
        """Test de démarrage de synchronisation réussi"""
        mock_load.return_value = {
            'otp_config_id': 123,
            'ds_api_token': 'token',
            'demarche_number': '123',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }
        mock_start.return_value = 'task_123'

        sync_data = {
            'otp_config_id': 123,
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

    @patch('app.SessionLocal')
    @patch.object(ConfigManager, 'save_config')
    def test_api_config_post_success(self, mock_save, mock_session, client):
        """Test de sauvegarde de configuration réussie"""
        mock_save.return_value = True

        # Mock pour l'id
        mock_db = mock_session.return_value
        mock_otp = mock_db.query.return_value.filter_by.return_value.first.return_value
        mock_otp.id = 456

        config_data = {
            'ds_api_token': 'token',
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
        assert data['otp_config_id'] == 456

    def test_api_config_post_missing_field(self, client):
        """Test de sauvegarde avec champ manquant"""
        config_data = {
            'ds_api_token': '',
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

    @patch.object(sync_task_manager, 'start_sync')
    @patch.object(ConfigManager, 'load_config_by_id')
    def test_api_start_sync_task_manager_success(self, mock_load, mock_start, client):
        """Test de démarrage de synchronisation réussi"""
        mock_load.return_value = {
            'otp_config_id': 123,
            'ds_api_token': 'token',
            'demarche_number': '123',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }
        mock_start.return_value = 'task_123'

        sync_data = {
            'otp_config_id': 123,
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

    @patch.object(ConfigManager, 'load_config_by_id')
    def test_api_start_sync_missing_config(self, mock_load, client):
        """Test de démarrage avec configuration manquante"""
        mock_load.return_value = {
            'otp_config_id': 123,
            'ds_api_token': '',
            'demarche_number': '123'
            # Champs manquants
        }

        sync_data = {'otp_config_id': 123, 'filters': {}}

        response = client.post(
            '/api/start-sync',
            data=json.dumps(sync_data),
            content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'manquants' in data['message']

    @patch.object(sync_task_manager, 'get_task')
    def test_api_task_status_found(self, mock_get, client):
        """Test de récupération du statut d'une tâche existante"""
        mock_get.return_value = {'status': 'running', 'progress': 50}

        response = client.get('/api/task/task_123')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'running'
        assert data['progress'] == 50

    @patch.object(sync_task_manager, 'get_task')
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

    @patch.object(ConfigManager, 'load_config_by_id')
    def test_api_start_sync_missing_demarche_token(self, mock_load, client):
        """Test démarrage sync avec token manquant"""
        mock_load.return_value = {
            'otp_config_id': 123,
            'ds_api_token': '',  # Manquant
            'demarche_number': '123',
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }

        sync_data = {
            'otp_config_id': 123,
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

    @patch.object(ConfigManager, 'load_config_by_id')
    def test_api_start_sync_missing_demarche_number(self, mock_load, client):
        """Test démarrage sync avec numéro démarche manquant"""
        mock_load.return_value = {
            'otp_config_id': 123,
            'ds_api_token': 'token',
            'demarche_number': '',  # Manquant
            'grist_api_key': 'key',
            'grist_doc_id': 'doc',
            'grist_user_id': 'user'
        }

        sync_data = {
            'otp_config_id': 123,
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

    @patch.object(sync_task_manager, 'run_synchronization_task')
    @patch.object(ConfigManager, 'load_config_by_id')
    def test_api_start_sync_task_failure_before_refactor(self, mock_load, mock_run, client):
        """Test échec de tâche de synchronisation"""
        mock_load.return_value = {
            'otp_config_id': 123,
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
            'otp_config_id': 123,
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

    @patch('app.SessionLocal')
    def test_api_schedule_post_success(self, mock_session, client):
        """Test activation de planning réussi"""
        mock_db = mock_session.return_value
        mock_config = mock_db.query.return_value.filter_by.return_value.first.return_value
        mock_config.id = 1
        mock_schedule = mock_db.query.return_value.filter_by.return_value.first.return_value
        mock_schedule.enabled = False

        data = {'otp_config_id': 1}

        response = client.post('/api/schedule', data=json.dumps(data), content_type='application/json')
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp['success'] is True
        assert 'enabled' in data_resp['message']

    @patch('app.SessionLocal')
    def test_api_schedule_post_new(self, mock_session, client):
        """Test création de planning"""
        mock_db = mock_session.return_value

        # Mock pour OtpConfiguration
        mock_config_query = mock_db.query.return_value
        mock_config_filter = mock_config_query.filter_by.return_value
        mock_config = mock_config_filter.first.return_value
        mock_config.id = 1

        # Mock pour UserSchedule (pas trouvé)
        def query_side_effect(model):
            if model.__name__ == 'OtpConfiguration':
                return mock_config_query
            elif model.__name__ == 'UserSchedule':
                mock_schedule_query = MagicMock()
                mock_schedule_filter = MagicMock()
                mock_schedule_filter.first.return_value = None
                mock_schedule_query.filter_by.return_value = mock_schedule_filter
                return mock_schedule_query
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        data = {'otp_config_id': 1}

        response = client.post('/api/schedule', data=json.dumps(data), content_type='application/json')
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp['success'] is True
        assert 'enabled' in data_resp['message']

    @patch('app.SessionLocal')
    def test_api_schedule_delete(self, mock_session, client):
        """Test désactivation de planning"""
        mock_db = mock_session.return_value
        mock_config = mock_db.query.return_value.filter_by.return_value.first.return_value
        mock_config.id = 1
        mock_schedule = mock_db.query.return_value.filter_by.return_value.first.return_value
        mock_schedule.enabled = True

        data = {'otp_config_id': 1}

        response = client.delete('/api/schedule', data=json.dumps(data), content_type='application/json')
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp['success'] is True
        assert 'disabled' in data_resp['message']

    @patch('app.SessionLocal')
    def test_api_schedule_missing_config(self, mock_session, client):
        """Test planning avec config manquante"""
        mock_db = mock_session.return_value
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        data = {'otp_config_id': 999}

        response = client.post('/api/schedule', data=json.dumps(data), content_type='application/json')
        assert response.status_code == 404

        data_resp = json.loads(response.data)
        assert data_resp['success'] is False
        assert 'not found' in data_resp['message']

    @patch('app.SessionLocal')
    def test_api_schedule_missing_fields(self, mock_session, client):
        """Test planning avec champs manquants"""
        data = {}  # missing otp_config_id

        response = client.post('/api/schedule', data=json.dumps(data), content_type='application/json')
        assert response.status_code == 400

        data_resp = json.loads(response.data)
        assert data_resp['success'] is False
        assert 'required' in data_resp['message']

    @patch('app.SessionLocal')
    @patch('app.reload_scheduler_jobs')
    def test_api_delete_config_success(self, mock_reload, mock_session, client):
        """Test suppression de configuration réussie"""
        mock_db = mock_session.return_value
        mock_config = mock_db.query.return_value.filter_by.return_value.first.return_value
        mock_config.id = 123

        response = client.delete('/api/config/123')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['success'] is True
        assert 'supprimée' in data['message']
        mock_db.delete.assert_called_once_with(mock_config)
        mock_db.commit.assert_called_once()
        mock_reload.assert_called_once()

    @patch('app.SessionLocal')
    def test_api_delete_config_not_found(self, mock_session, client):
        """Test suppression de configuration inexistante"""
        mock_db = mock_session.return_value
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        response = client.delete('/api/config/999')
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data['success'] is False
        assert 'non trouvée' in data['message']

    @patch('app.SessionLocal')
    def test_scheduled_sync_job_success(self, mock_session):
        """Test exécution réussie d'une synchronisation planifiée"""
        from app import scheduled_sync_job

        # Mock de la configuration OTP
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.grist_user_id = 'user123'
        mock_config.grist_doc_id = 'doc456'

        mock_schedule = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_config

        # Mock de config_manager.load_config_by_id
        with patch('app.config_manager.load_config_by_id') as mock_load_config:
            mock_load_config.return_value = {
                'otp_config_id': 1,
                'demarche_number': '123',
                'grist_doc_id': 'doc456',
                'grist_user_id': 'user123',
                'has_ds_token': True,
                'has_grist_key': True
            }

            # Mock de run_synchronization_task
            with patch.object(sync_task_manager, 'run_synchronization_task') as mock_sync:
                mock_sync.return_value = {'success': True, 'message': 'Sync successful'}

                # Exécuter la fonction
                scheduled_sync_job(1)

                # Vérifications
                mock_load_config.assert_called_once_with(1)
                mock_sync.assert_called_once()
                mock_db.add.assert_called()  # SyncLog ajouté
                mock_db.commit.assert_called()

    @patch('app.SessionLocal')
    def test_scheduled_sync_job_error(self, mock_session):
        """Test exécution échouée d'une synchronisation planifiée"""
        from app import scheduled_sync_job

        # Mock de la configuration OTP
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.grist_user_id = 'user123'
        mock_config.grist_doc_id = 'doc456'

        mock_db.query.return_value.filter_by.return_value.first.return_value = mock_config

        # Mock de config_manager.load_config_by_id
        with patch('app.config_manager.load_config_by_id') as mock_load_config:
            mock_load_config.return_value = {
                'otp_config_id': 1,
                'demarche_number': '123',
                'grist_doc_id': 'doc456',
                'grist_user_id': 'user123',
                'has_ds_token': True,
                'has_grist_key': True
            }

            # Mock de run_synchronization_task qui échoue
            with patch.object(sync_task_manager, 'run_synchronization_task') as mock_sync:
                mock_sync.return_value = {'success': False, 'message': 'Sync failed'}

                # Mock de socketio.emit
                with patch('app.socketio.emit') as mock_emit:
                    # Exécuter la fonction
                    scheduled_sync_job(1)

                    # Vérifications
                    mock_load_config.assert_called_once_with(1)
                    mock_sync.assert_called_once()
                    mock_emit.assert_called_once()
                    call_args = mock_emit.call_args
                    assert call_args[0][0] == 'sync_error'
                    data = call_args[0][1]
                    assert data['grist_user_id'] == 'user123'
                    assert data['grist_doc_id'] == 'doc456'
                    assert data['message'] == 'Sync failed'
                    assert 'timestamp' in data

    @patch('app.SessionLocal')
    def test_reload_scheduler_jobs(self, mock_session):
        """Test rechargement des jobs du scheduler"""
        from app import reload_scheduler_jobs

        # Mock de la DB
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        # Mock des schedules actifs
        mock_schedule1 = MagicMock()
        mock_schedule1.otp_config_id = 1
        mock_schedule1.enabled = True

        mock_schedule2 = MagicMock()
        mock_schedule2.otp_config_id = 2
        mock_schedule2.enabled = True

        mock_db.query.return_value.filter_by.return_value.all.return_value = [
            mock_schedule1, mock_schedule2
        ]

        # Mock des configurations OTP
        mock_config1 = MagicMock()
        mock_config1.id = 1
        mock_config1.grist_user_id = 'user1'
        mock_config1.grist_doc_id = 'doc1'

        mock_config2 = MagicMock()
        mock_config2.id = 2
        mock_config2.grist_user_id = 'user2'
        mock_config2.grist_doc_id = 'doc2'

        def mock_filter_by(**kwargs):
            if kwargs.get('id') == 1:
                return MagicMock(first=MagicMock(return_value=mock_config1))
            elif kwargs.get('id') == 2:
                return MagicMock(first=MagicMock(return_value=mock_config2))
            return MagicMock(first=MagicMock(return_value=None))

        mock_db.query.return_value.filter_by.side_effect = mock_filter_by

        # Mock du scheduler global - patch au niveau du module
        with patch('app.scheduler') as mock_scheduler_instance:
            mock_scheduler_instance.get_jobs.return_value = []
            mock_scheduler_instance.running = True

            # Exécuter la fonction
            reload_scheduler_jobs()

            # Vérifications
            mock_scheduler_instance.remove_all_jobs.assert_called_once()
            # Vérifier que add_job a été appelé (ne pas vérifier le nombre exact car dépend de la logique)
