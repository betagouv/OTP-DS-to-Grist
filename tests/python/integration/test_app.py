import pytest
import json
from unittest.mock import patch, MagicMock
from app import app, ConfigManager, sync_manager


@pytest.fixture
def client():
    """Fixture pour le client de test Flask"""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_config():
    """Fixture pour mocker la configuration"""
    with patch.object(ConfigManager, "load_config") as mock_load:
        mock_load.return_value = {
            "ds_api_token": "test-token",
            "demarche_number": "123",
            "grist_base_url": "https://grist.test.com",
            "grist_api_key": "test-key",
            "grist_doc_id": "test-doc",
            "grist_user_id": "test-user",
        }
        yield mock_load


class TestEndpoints:
    """Tests d'intégration pour les endpoints Flask"""

    def test_index_route(self, client):
        """Test de la route d'accueil"""
        response = client.get("/")
        assert response.status_code == 200
        assert b"One Trick Pony" in response.data

    def test_execution_route(self, client):
        """Test de la route d'exécution"""
        response = client.get("/execution")
        assert response.status_code == 200
        assert b"Synchronisation" in response.data

    def test_debug_route(self, client):
        """Test de la route de débogage"""
        response = client.get("/debug")
        assert response.status_code == 200
        assert b"debug" in response.data

    def test_use_otp_route(self, client):
        """Test de la route d'utilisation"""
        response = client.get("/utiliser-le-connecteur")
        assert response.status_code == 200
        assert b"utiliser" in response.data

    @patch.object(sync_manager, "start_sync")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_success(self, mock_load, mock_start, client):
        """Test de démarrage de synchronisation réussi"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "token",
            "demarche_number": "123",
            "grist_api_key": "key",
            "grist_doc_id": "doc",
            "grist_user_id": "user",
        }
        mock_start.return_value = "task_123"

        sync_data = {"otp_config_id": 123, "filters": {}}

        response = client.post(
            "/api/start-sync",
            data=json.dumps(sync_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["task_id"] == "task_123"

    def test_api_config_post_missing_field(self, client):
        """Test de sauvegarde avec champ minimum manquant"""
        config_data = {
            "ds_api_token": "",  # Manquant
            "demarche_number": "123",
            # Champs manquants
        }

        response = client.post(
            "/api/config", data=json.dumps(config_data), content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "requis" in data["message"]

    @patch("app.SessionLocal")
    @patch.object(ConfigManager, "save_config")
    def test_api_config_post_partial_save_success(
        self, mock_save, mock_session, client
    ):
        """Test de sauvegarde partielle réussie (sans clé API Grist)"""
        mock_save.return_value = True

        # Mock pour l'id
        mock_db = mock_session.return_value
        mock_otp = mock_db.query.return_value.filter_by.return_value.first.return_value
        mock_otp.id = 456

        # Configuration partielle (sans grist_api_key)
        config_data = {
            "ds_api_token": "token123",
            "demarche_number": "12345",
            "grist_base_url": "https://grist.numerique.gouv.fr/api",
            "grist_doc_id": "doc123",
            "grist_user_id": "user456",
            # grist_api_key manquant (sauvegarde partielle)
        }

        response = client.post(
            "/api/config", data=json.dumps(config_data), content_type="application/json"
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "sauvegardée" in data["message"]
        assert data["otp_config_id"] == 456

        # Vérifier que save_config a été appelé avec la configuration partielle
        mock_save.assert_called_once()
        call_args = mock_save.call_args[0][0]
        assert call_args["ds_api_token"] == "token123"
        assert call_args["demarche_number"] == "12345"
        assert call_args["grist_base_url"] == "https://grist.numerique.gouv.fr/api"
        assert call_args["grist_doc_id"] == "doc123"
        assert call_args["grist_user_id"] == "user456"

    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches(self, mock_test, client):
        """Test du endpoint de test de connexion Démarches"""
        mock_test.return_value = (True, "Connexion réussie")

        test_data = {
            "type": "demarches",
            "api_token": "token",
            "demarche_number": "123",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["message"] == "Connexion réussie"

    @patch("app.test_grist_api")
    def test_api_test_connection_grist(self, mock_test, client):
        """Test du endpoint de test de connexion Grist"""
        mock_test.return_value = (False, "Erreur de connexion")

        test_data = {
            "type": "grist",
            "base_url": "https://grist.test.com",
            "api_key": "key",
            "doc_id": "doc123",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Erreur" in data["message"]

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_no_params_missing_ds_token(self, mock_load, client):
        """Test sans paramètres - token DS manquant dans le body"""
        test_data = {
            "grist_api_key": "key",
            "grist_base_url": "https://grist.example.com",
            "grist_doc_id": "doc123",
        }

        mock_load.return_value = test_data

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Token API Démarches Simplifiées non configuré" in data["message"]

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_no_params_missing_grist_config(
        self, mock_load, client
    ):
        """Test sans paramètres - config Grist incomplète dans le body"""
        test_data = {"ds_api_token": "valid-token", "demarche_number": "123"}

        mock_load.return_value = test_data

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Configuration Grist incomplète" in data["message"]

    @patch("api_validator.test_demarches_api")
    @patch("api_validator.test_grist_api")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_no_params_success(
        self, mock_load, mock_grist, mock_demarches, client
    ):
        """Test sans paramètres - succès des deux connexions"""
        test_data = {
            "ds_api_token": "valid-token",
            "demarche_number": "123",
            "grist_api_key": "valid-key",
            "grist_base_url": "https://grist.example.com",
            "grist_doc_id": "doc123",
        }

        mock_load.return_value = test_data
        mock_demarches.return_value = (True, "DS OK")
        mock_grist.return_value = (True, "Grist OK")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["message"] == "2/2 tests réussis"
        assert len(data["results"]) == 2
        assert data["results"][0]["type"] == "demarches"
        assert data["results"][0]["success"] is True
        assert data["results"][1]["type"] == "grist"
        assert data["results"][1]["success"] is True

    @patch("api_validator.test_demarches_api")
    @patch("api_validator.test_grist_api")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_no_params_partial_failure(
        self, mock_load, mock_grist, mock_demarches, client
    ):
        """Test sans paramètres - échec partiel"""
        test_data = {
            "ds_api_token": "valid-token",
            "demarche_number": "123",
            "grist_api_key": "valid-key",
            "grist_base_url": "https://grist.example.com",
            "grist_doc_id": "doc123",
        }

        mock_load.return_value = test_data
        mock_demarches.return_value = (True, "DS OK")
        mock_grist.return_value = (False, "Grist Error")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "1/2 tests réussis"
        assert data["results"][0]["success"] is True
        assert data["results"][1]["success"] is False

    @patch.object(ConfigManager, "load_config")
    @patch("app.get_available_groups")
    def test_api_groups_with_grist_params(self, mock_groups, mock_load, client):
        """
        Test de récupération des groupes
        avec paramètres grist_user_id et grist_doc_id
        """
        mock_load.return_value = {"ds_api_token": "token", "demarche_number": "123"}
        mock_groups.return_value = [{"id": "1", "label": "Groupe 1"}]

        response = client.get("/api/groups?grist_user_id=user123&grist_doc_id=doc456")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["label"] == "Groupe 1"

        # Vérifie que load_config a été appelé avec les bons paramètres
        mock_load.assert_called_once_with(
            grist_user_id="user123", grist_doc_id="doc456"
        )

    @patch.object(ConfigManager, "load_config_by_id")
    @patch("app.get_available_groups")
    def test_api_groups_otp_config_id_mode(self, mock_groups, mock_load, client):
        """Test de récupération des groupes en mode otp_config_id"""
        mock_load.return_value = {"ds_api_token": "token789", "demarche_number": "456"}
        mock_groups.return_value = [
            (1, "Groupe Instructeur A"),
            (2, "Groupe Instructeur B"),
        ]

        response = client.get("/api/groups?otp_config_id=789")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0] == [1, "Groupe Instructeur A"]
        assert data[1] == [2, "Groupe Instructeur B"]

        # Vérifie que load_config_by_id a été appelé avec le bon ID
        mock_load.assert_called_once_with("789")

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_groups_otp_config_id_not_found(self, mock_load, client):
        """Test de récupération des groupes avec otp_config_id inexistant"""
        mock_load.side_effect = Exception("Configuration not found")

        response = client.get("/api/groups?otp_config_id=999")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data
        assert "Erreur lors de la récupération des groupes" == data["error"]

    @patch.object(ConfigManager, "load_config")
    def test_api_groups_legacy_missing_params(self, mock_load, client):
        """Test de récupération des groupes en mode legacy sans paramètres"""
        mock_load.side_effect = Exception("No grist user id or doc id")

        response = client.get("/api/groups")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data
        assert "Erreur lors de la récupération des groupes" == data["error"]

    def test_api_groups_no_params_400(self, client):
        """Test de récupération des groupes sans aucun paramètre"""
        response = client.get("/api/groups")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data

    @patch.object(sync_manager, "start_sync")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_manager_success(self, mock_load, mock_start, client):
        """Test de démarrage de synchronisation réussi"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "token",
            "demarche_number": "123",
            "grist_api_key": "key",
            "grist_doc_id": "doc",
            "grist_user_id": "user",
        }
        mock_start.return_value = "task_123"

        sync_data = {"otp_config_id": 123, "filters": {}}

        response = client.post(
            "/api/start-sync",
            data=json.dumps(sync_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["task_id"] == "task_123"

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_missing_config(self, mock_load, client):
        """Test de démarrage avec configuration manquante"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "",
            "demarche_number": "123",
            # Champs manquants
        }

        sync_data = {"otp_config_id": 123, "filters": {}}

        response = client.post(
            "/api/start-sync",
            data=json.dumps(sync_data),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "manquants" in data["message"]


class TestErrorHandling:
    """Tests d'intégration pour la gestion d'erreurs"""

    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches_timeout(self, mock_test, client):
        """Test timeout API Démarches"""
        mock_test.return_value = (False, "Timeout: L'API met trop de temps à répondre")

        test_data = {
            "type": "demarches",
            "api_token": "token",
            "demarche_number": "123",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Timeout" in data["message"]

    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches_invalid_token(self, mock_test, client):
        """Test token invalide Démarches"""
        mock_test.return_value = (False, "Erreur API: Unauthorized")

        test_data = {
            "type": "demarches",
            "api_token": "invalid-token",
            "demarche_number": "123",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Unauthorized" in data["message"]

    @patch("app.test_grist_api")
    def test_api_test_connection_grist_network_error(self, mock_test, client):
        """Test erreur réseau Grist"""
        mock_test.return_value = (False, "Erreur de connexion: Network is unreachable")

        test_data = {
            "type": "grist",
            "base_url": "https://grist.test.com",
            "api_key": "key",
            "doc_id": "doc123",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Network" in data["message"]

    @patch("app.test_grist_api")
    def test_api_test_connection_grist_invalid_key(self, mock_test, client):
        """Test clé API invalide Grist"""
        mock_test.return_value = (
            False,
            "Erreur de connexion à Grist: 401 - Unauthorized",
        )

        test_data = {
            "type": "grist",
            "base_url": "https://grist.test.com",
            "api_key": "invalid-key",
            "doc_id": "doc123",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(test_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "401" in data["message"]

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_missing_demarche_token(self, mock_load, client):
        """Test démarrage sync avec token manquant"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "",  # Manquant
            "demarche_number": "123",
            "grist_api_key": "key",
            "grist_doc_id": "doc",
            "grist_user_id": "user",
        }

        sync_data = {"otp_config_id": 123, "filters": {}}

        response = client.post(
            "/api/start-sync",
            data=json.dumps(sync_data),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "manquants" in data["message"]
        assert "ds_api_token" in data["missing_fields"]

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_missing_demarche_number(self, mock_load, client):
        """Test démarrage sync avec numéro démarche manquant"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "token",
            "demarche_number": "",  # Manquant
            "grist_api_key": "key",
            "grist_doc_id": "doc",
            "grist_user_id": "user",
        }

        sync_data = {"otp_config_id": 123, "filters": {}}

        response = client.post(
            "/api/start-sync",
            data=json.dumps(sync_data),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "manquants" in data["message"]
        assert "demarche_number" in data["missing_fields"]

    @patch.object(sync_manager, "run_synchronization_task")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_failure_before_refactor(self, mock_load, mock_run, client):
        """Test échec de tâche de synchronisation"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "token",
            "demarche_number": "123",
            "grist_api_key": "key",
            "grist_doc_id": "doc",
            "grist_user_id": "user",
        }
        mock_run.return_value = {
            "success": False,
            "message": "Erreur lors du traitement",
        }

        sync_data = {"otp_config_id": 123, "filters": {}}

        response = client.post(
            "/api/start-sync",
            data=json.dumps(sync_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True  # Tâche démarrée, même si elle échoue
        assert "task_id" in data

    @patch.object(ConfigManager, "save_config")
    def test_api_config_post_save_failure(self, mock_save, client):
        """Test échec de sauvegarde configuration"""
        mock_save.return_value = False

        config_data = {
            "ds_api_token": "token",
            "demarche_number": "123",
            "grist_base_url": "base",
            "grist_api_key": "key",
            "grist_doc_id": "doc",
            "grist_user_id": "user",
        }

        response = client.post(
            "/api/config", data=json.dumps(config_data), content_type="application/json"
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Erreur lors de la sauvegarde" in data["message"]

    @patch("app.SessionLocal")
    def test_api_schedule_post_success(self, mock_session, client):
        """Test activation de planning réussi"""
        mock_db = mock_session.return_value
        mock_config = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_config.id = 1
        mock_schedule = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_schedule.enabled = False

        data = {"otp_config_id": 1}

        response = client.post(
            "/api/schedule", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp["success"] is True
        assert "enabled" in data_resp["message"]

    @patch("app.SessionLocal")
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
            if model.__name__ == "OtpConfiguration":
                return mock_config_query
            elif model.__name__ == "UserSchedule":
                mock_schedule_query = MagicMock()
                mock_schedule_filter = MagicMock()
                mock_schedule_filter.first.return_value = None
                mock_schedule_query.filter_by.return_value = mock_schedule_filter
                return mock_schedule_query
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        data = {"otp_config_id": 1}

        response = client.post(
            "/api/schedule", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp["success"] is True
        assert "enabled" in data_resp["message"]

    @patch("app.SessionLocal")
    def test_api_schedule_delete(self, mock_session, client):
        """Test désactivation de planning"""
        mock_db = mock_session.return_value
        mock_config = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_config.id = 1
        mock_schedule = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_schedule.enabled = True

        data = {"otp_config_id": 1}

        response = client.delete(
            "/api/schedule", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp["success"] is True
        assert "disabled" in data_resp["message"]

    @patch("app.SessionLocal")
    def test_api_schedule_post_missing_grist_key(self, mock_session, client):
        """Test activation planning sans clé Grist"""
        mock_db = mock_session.return_value
        mock_config = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_config.id = 1
        mock_config.grist_api_key = None  # Clé Grist manquante

        data = {"otp_config_id": 1}

        response = client.post(
            "/api/schedule", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 403

        data_resp = json.loads(response.data)
        assert data_resp["success"] is False
        assert "Clé grist manquante" in data_resp["message"]

    @patch("app.SessionLocal")
    def test_api_schedule_missing_config(self, mock_session, client):
        """Test planning avec config manquante"""
        mock_db = mock_session.return_value
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        data = {"otp_config_id": 999}

        response = client.post(
            "/api/schedule", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 404

        data_resp = json.loads(response.data)
        assert data_resp["success"] is False
        assert "not found" in data_resp["message"]

    @patch("app.SessionLocal")
    def test_api_schedule_missing_fields(self, _, client):
        """Test planning avec champs manquants"""
        data = {}  # missing otp_config_id

        response = client.post(
            "/api/schedule", data=json.dumps(data), content_type="application/json"
        )
        assert response.status_code == 400

        data_resp = json.loads(response.data)
        assert data_resp["success"] is False
        assert "required" in data_resp["message"]

    @patch("app.SessionLocal")
    @patch("app.reload_scheduler_jobs")
    def test_api_delete_config_success(self, mock_reload, mock_session, client):
        """Test suppression de configuration réussie"""
        mock_db = mock_session.return_value
        mock_config = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_config.id = 123

        response = client.delete("/api/config/123")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert "supprimée" in data["message"]
        mock_db.delete.assert_called_once_with(mock_config)
        mock_db.commit.assert_called_once()
        mock_reload.assert_called_once()

    @patch("app.SessionLocal")
    def test_api_delete_config_not_found(self, mock_session, client):
        """Test suppression de configuration inexistante"""
        mock_db = mock_session.return_value
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        response = client.delete("/api/config/999")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["success"] is False
        assert "non trouvée" in data["message"]

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager.load_config_by_id")
    def test_scheduled_sync_job_success(
        self, mock_load_config, mock_sessionmaker, mock_create_engine
    ):
        """Test exécution réussie d'une synchronisation planifiée"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_db = MagicMock()
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        mock_session_class = MagicMock(return_value=mock_db)
        mock_sessionmaker.return_value = mock_session_class

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.grist_user_id = "user123"
        mock_config.grist_doc_id = "doc456"

        mock_db.query.return_value.filter_by.return_value.first.return_value = (
            mock_config
        )

        mock_load_config.return_value = {
            "otp_config_id": 1,
            "demarche_number": "123",
            "grist_doc_id": "doc456",
            "grist_user_id": "user123",
            "has_ds_token": True,
            "has_grist_key": True,
        }

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(sync_manager, "run_synchronization_task") as mock_sync:
            mock_sync.return_value = {"success": True, "message": "Sync successful"}

            scheduled_sync_job(1, sync_manager)

            mock_load_config.assert_called_once_with(1)
            mock_sync.assert_called_once()
            mock_sync.assert_called_once_with(
                {
                    "otp_config_id": 1,
                    "demarche_number": "123",
                    "grist_doc_id": "doc456",
                    "grist_user_id": "user123",
                    "has_ds_token": True,
                    "has_grist_key": True,
                },
                auto=True,
            )

    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager.load_config_by_id")
    def test_scheduled_sync_job_error(self, mock_load_config, mock_sessionmaker):
        """Test exécution échouée d'une synchronisation planifiée"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_db = MagicMock()
        mock_session_class = MagicMock(return_value=mock_db)
        mock_sessionmaker.return_value = mock_session_class

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.grist_user_id = "user123"
        mock_config.grist_doc_id = "doc456"

        mock_db.query.return_value.filter_by.return_value.first.return_value = (
            mock_config
        )

        mock_load_config.return_value = {
            "otp_config_id": 1,
            "demarche_number": "123",
            "grist_doc_id": "doc456",
            "grist_user_id": "user123",
            "has_ds_token": True,
            "has_grist_key": True,
        }

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(sync_manager, "run_synchronization_task") as mock_sync:
            mock_sync.return_value = {"success": False, "message": "Sync failed"}

            scheduled_sync_job(1, sync_manager)

            mock_load_config.assert_called_once_with(1)
            mock_sync.assert_called_once()
            mock_sync.assert_called_once_with(
                {
                    "otp_config_id": 1,
                    "demarche_number": "123",
                    "grist_doc_id": "doc456",
                    "grist_user_id": "user123",
                    "has_ds_token": True,
                    "has_grist_key": True,
                },
                auto=True,
            )

    @patch("sync.scheduled_sync.sessionmaker")
    def test_reload_scheduler_jobs(self, mock_sessionmaker):
        """Test rechargement des jobs du scheduler"""
        from sync.scheduled_sync import reload_scheduler_jobs, scheduler
        from sync.sync_manager import SyncManager

        mock_db = MagicMock()
        mock_sessionmaker.return_value = mock_db

        mock_schedule1 = MagicMock()
        mock_schedule1.otp_config_id = 1
        mock_schedule1.enabled = True

        mock_schedule2 = MagicMock()
        mock_schedule2.otp_config_id = 2
        mock_schedule2.enabled = True

        mock_db.query.return_value.filter_by.return_value.all.return_value = [
            mock_schedule1,
            mock_schedule2,
        ]

        mock_config1 = MagicMock()
        mock_config1.id = 1
        mock_config1.grist_user_id = "user1"
        mock_config1.grist_doc_id = "doc1"
        mock_config1.demarche_number = "123"

        mock_config2 = MagicMock()
        mock_config2.id = 2
        mock_config2.grist_user_id = "user2"
        mock_config2.grist_doc_id = "doc2"
        mock_config2.demarche_number = "456"

        def mock_filter_by(**kwargs):
            if kwargs.get("id") == 1:
                return MagicMock(first=MagicMock(return_value=mock_config1))
            elif kwargs.get("id") == 2:
                return MagicMock(first=MagicMock(return_value=mock_config2))
            return MagicMock(first=MagicMock(return_value=None))

        mock_db.query.return_value.filter_by.side_effect = mock_filter_by

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(scheduler, "remove_all_jobs") as mock_remove:
            reload_scheduler_jobs(sync_manager)

            mock_remove.assert_called_once()


class SyncLogMock:
    """Mock simple pour SyncLog avec attributs sérialisables"""

    def __init__(self, timestamp_iso, status, success_count, error_count, message):
        class TimestampMock:
            def isoformat(self):
                return timestamp_iso

        self.timestamp = TimestampMock()
        self.status = status
        self.success_count = success_count
        self.error_count = error_count
        self.message = message


class OtpConfigMock:
    """Mock simple pour OtpConfiguration avec attributs sérialisables"""

    def __init__(self, id, grist_user_id, grist_doc_id):
        self.id = id
        self.grist_user_id = grist_user_id
        self.grist_doc_id = grist_doc_id


class TestApiSyncLogLatest:
    """Tests pour la route /api/sync-log/latest"""

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_success_with_both(self, mock_session, client):
        """Test retour avec auto et manual sync"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_otp_config = OtpConfigMock(1, "user123", "doc456")
        mock_sync_auto = SyncLogMock(
            "2026-04-20T10:00:00+00:00", "success", 10, 0, "Sync auto réussie"
        )
        mock_sync_manual = SyncLogMock(
            "2026-04-20T14:30:00+00:00", "success", 5, 1, "Sync manuelle réussie"
        )

        query_calls = []

        def query_side_effect(model):
            query_calls.append(model)
            mock_result = MagicMock()
            mock_filter = MagicMock()
            mock_order = MagicMock()

            if model.__name__ == "OtpConfiguration":
                mock_filter.order_by.return_value.first.return_value = mock_otp_config
            elif query_calls.count(model) == 1:
                mock_filter.order_by.return_value.first.return_value = mock_sync_auto
            else:
                mock_filter.order_by.return_value.first.return_value = mock_sync_manual

            mock_result.filter_by.return_value = mock_filter
            mock_order.first.return_value = None
            return mock_result

        mock_db.query.side_effect = query_side_effect

        response = client.get("/api/sync-log/latest?otp_config_id=1")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["auto"] is not None
        assert data["auto"]["status"] == "success"
        assert data["auto"]["success_count"] == 10
        assert data["manual"] is not None
        assert data["manual"]["status"] == "success"
        assert data["manual"]["success_count"] == 5

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_auto_only(self, mock_session, client):
        """Test retour avec seulement sync auto"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_otp_config = OtpConfigMock(1, "user123", "doc456")
        mock_sync_auto = SyncLogMock(
            "2026-04-20T10:00:00+00:00", "success", 10, 0, "Sync auto réussie"
        )

        query_count = [0]

        def query_side_effect(model):
            query_count[0] += 1
            mock_result = MagicMock()
            mock_filter = MagicMock()

            if model.__name__ == "OtpConfiguration":
                mock_filter.order_by.return_value.first.return_value = mock_otp_config
            elif query_count[0] == 2:
                mock_filter.order_by.return_value.first.return_value = mock_sync_auto
            else:
                mock_filter.order_by.return_value.first.return_value = None

            mock_result.filter_by.return_value = mock_filter
            return mock_result

        mock_db.query.side_effect = query_side_effect

        response = client.get("/api/sync-log/latest?otp_config_id=1")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["auto"] is not None
        assert data["manual"] is None

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_no_sync(self, mock_session, client):
        """Test retour sans aucune sync (null)"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_otp_config = OtpConfigMock(1, "user123", "doc456")

        query_count = [0]

        def query_side_effect(model):
            query_count[0] += 1
            mock_result = MagicMock()
            mock_filter = MagicMock()
            mock_order = MagicMock()
            if model.__name__ == "OtpConfiguration":
                mock_order.first.return_value = mock_otp_config
            else:
                mock_order.first.return_value = None
            mock_filter.order_by.return_value = mock_order
            mock_result.filter_by.return_value = mock_filter
            return mock_result

        mock_db.query.side_effect = query_side_effect

        response = client.get("/api/sync-log/latest?otp_config_id=1")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["auto"] is None
        assert data["manual"] is None

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_missing_config(self, mock_session, client):
        """Test avec config inexistante - 404"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        response = client.get("/api/sync-log/latest?otp_config_id=999")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["success"] is False

    def test_api_sync_log_latest_missing_param(self, client):
        """Test sans otp_config_id - 400"""
        response = client.get("/api/sync-log/latest")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data["success"] is False
        assert "otp_config_id" in data["message"]
