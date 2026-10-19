import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from app import ConfigManager, sync_manager
from configuration.config_manager import ConfigIncompleteError, ConfigNotFoundError
from grist.base_url import GristBaseUrlImmutableError, GristBaseUrlNotAllowedError
from security.widget_token import WidgetTokenInvalidError, WidgetTokenUnavailableError


class TestEndpoints:
    """Tests d'intégration pour les endpoints Flask"""

    def test_index_route(self, client):
        """Test de la route d'accueil"""
        response = client.get("/")
        assert response.status_code == 200
        assert b"One Trick Pony" in response.data

    def test_execution_route_is_gone(self, client):
        """La route /execution n'existe plus : la page ne doit pas être visitable directement"""
        response = client.get("/execution")
        assert response.status_code == 404

    @patch.object(sync_manager, "start_sync")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_success(self, mock_load, mock_start, client):
        """Test de démarrage de synchronisation réussi"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "token",
            "demarche_number": "123",
            "grist_api_key": "key",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
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

    @patch.object(ConfigManager, "save_config")
    def test_api_config_post_without_grist_key_rejected(self, mock_save, client):
        """Création sans clé API Grist → 400 (la sauvegarde partielle est interdite)"""
        mock_save.side_effect = ConfigIncompleteError(["grist_api_key"])

        config_data = {
            "ds_api_token": "token123",
            "demarche_number": "12345",
            "grist_base_url": "https://grist.numerique.gouv.fr/api",
            "grist_doc_id": "doc123",
            "grist_user_id": "user456",
            # grist_api_key manquant
        }

        response = client.post(
            "/api/config", data=json.dumps(config_data), content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Le champ grist_api_key est requis"

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_config_update_config_not_found(self, mock_load, client):
        """Update avec un otp_config_id inexistant → 404"""
        mock_load.side_effect = ConfigNotFoundError("Configuration non trouvée (id=999)")

        response = client.post(
            "/api/config",
            json={
                "otp_config_id": 999,
                "grist_doc_id": "doc123",
                "grist_user_id": "user456",
            },
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Configuration non trouvée (id=999)"

    @patch.object(ConfigManager, "save_config")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_config_update_row_missing_during_save(
        self, mock_load, mock_save, client
    ):
        """La config disparaît entre le load et le save → 404"""
        mock_load.return_value = {
            "grist_user_id": "userA",
            "grist_doc_id": "docA",
            "grist_base_url": "https://grist.test.com/api",
        }
        mock_save.side_effect = ConfigNotFoundError("Configuration non trouvée (id=7)")

        response = client.post(
            "/api/config",
            json={
                "otp_config_id": 7,
                "ds_api_token": "token123",
                "demarche_number": "12345",
                "grist_base_url": "https://grist.test.com/api",
                "grist_doc_id": "doc123",
                "grist_user_id": "user456",
                "grist_api_key": "key123",
            },
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Configuration non trouvée (id=7)"

    @patch.object(ConfigManager, "save_config")
    def test_api_config_post_normalizes_types(self, mock_save, client):
        """Vérifie que les types mixtes (int, bool) sont normalisés en str par le POST"""
        mock_save.return_value = 789

        config_data = {
            "ds_api_token": "token123",
            "demarche_number": 12345,
            "grist_base_url": "https://grist.test.com/api",
            "grist_doc_id": 67890,
            "grist_user_id": 999,
            "filter_date_start": 20230101,
            "filter_date_end": 20231231,
            "filter_statuses": 1,
            "filter_groups": 2,
        }

        response = client.post("/api/config", json=config_data)

        assert response.status_code == 200

        normalized = mock_save.call_args[0][0]
        assert isinstance(normalized["demarche_number"], str)
        assert normalized["demarche_number"] == "12345"
        assert isinstance(normalized["grist_doc_id"], str)
        assert normalized["grist_doc_id"] == "docA"
        assert isinstance(normalized["grist_user_id"], str)
        assert normalized["grist_user_id"] == "userA"
        assert isinstance(normalized["filter_date_start"], str)
        assert normalized["filter_date_start"] == "20230101"
        assert isinstance(normalized["filter_date_end"], str)
        assert normalized["filter_date_end"] == "20231231"
        assert isinstance(normalized["filter_statuses"], str)
        assert normalized["filter_statuses"] == "1"
        assert isinstance(normalized["filter_groups"], str)
        assert normalized["filter_groups"] == "2"
        assert isinstance(normalized["grist_base_url"], str)
        assert isinstance(normalized["ds_api_token"], str)
        assert isinstance(normalized["batch_size"], int)
        assert isinstance(normalized["max_workers"], int)
        assert isinstance(normalized["parallel"], bool)

    @patch.object(ConfigManager, "save_config")
    @patch("app.SessionLocal")
    def test_api_config_post_returns_id_from_save_config(
        self, mock_session, mock_save, client
    ):
        """La réponse porte l'id retourné par save_config, sans relecture SessionLocal"""
        mock_save.return_value = 789
        # Simule une autre config existante pour le même user/doc
        mock_otp = (
            mock_session.return_value.query.return_value.filter_by.return_value.first.return_value
        )
        mock_otp.id = 999

        config_data = {
            "ds_api_token": "token123",
            "demarche_number": "12345",
            "grist_base_url": "https://grist.numerique.gouv.fr/api",
            "grist_doc_id": "doc123",
            "grist_user_id": "user456",
            "grist_api_key": "key123",
        }

        response = client.post("/api/config", json=config_data)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["otp_config_id"] == 789
        mock_session.assert_not_called()

    @patch.object(ConfigManager, "save_config")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_config_update_base_url_unchanged_success(
        self, mock_load, mock_save, client
    ):
        """Update avec la même base URL → 200"""
        mock_load.return_value = {
            "grist_user_id": "userA",
            "grist_doc_id": "docA",
            "grist_base_url": "https://grist.test.com/api",
        }
        mock_save.return_value = 1

        response = client.post(
            "/api/config",
            json={
                "otp_config_id": 1,
                "ds_api_token": "token123",
                "demarche_number": "12345",
                "grist_base_url": "https://grist.test.com/api",
                "grist_doc_id": "doc123",
                "grist_user_id": "user456",
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    @patch.object(ConfigManager, "save_config")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_config_update_base_url_different_forbidden(
        self, mock_load, mock_save, client
    ):
        """Update avec une base URL différente → 403 immuable"""
        mock_load.return_value = {
            "grist_user_id": "userA",
            "grist_doc_id": "docA",
            "grist_base_url": "https://grist.test.com/api",
        }
        mock_save.side_effect = GristBaseUrlImmutableError(
            "L'URL de base Grist ne peut pas être modifiée"
        )

        response = client.post(
            "/api/config",
            json={
                "otp_config_id": 1,
                "ds_api_token": "token123",
                "demarche_number": "12345",
                "grist_base_url": "https://grist.numerique.gouv.fr/api",
                "grist_doc_id": "doc123",
                "grist_user_id": "user456",
            },
        )

        assert response.status_code == 403
        data = json.loads(response.data)
        assert data["success"] is False
        assert "ne peut pas être modifiée" in data["message"]

    @patch.object(ConfigManager, "save_config")
    def test_api_config_insert_base_url_hors_liste_bad_request(
        self, mock_save, client
    ):
        """Création vers une instance hors liste blanche → 400"""
        mock_save.side_effect = GristBaseUrlNotAllowedError(
            "URL de base Grist non autorisée : grist.hors-liste.example"
        )

        response = client.post(
            "/api/config",
            json={
                "ds_api_token": "token123",
                "demarche_number": "12345",
                "grist_base_url": "https://grist.hors-liste.example/api",
                "grist_doc_id": "doc123",
                "grist_user_id": "user456",
            },
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "grist.hors-liste.example" in data["message"]

    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches(self, mock_test, client):
        """Test du endpoint de test de connexion Démarches"""
        mock_test.return_value = (True, "Connexion réussie", "Titre démarche")

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
        assert data["title"] == "Titre démarche"

    @patch.object(ConfigManager, "load_config_by_id")
    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches_with_otp_config_id(
        self, mock_test, mock_load, client
    ):
        """otp_config_id sans api_token → charge le token serveur"""
        mock_load.return_value = {
            "ds_api_token": "server-token",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }
        mock_test.return_value = (True, "Connexion réussie", "Titre démarche")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "demarches",
                    "otp_config_id": 42,
                    "demarche_number": "123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert mock_load.call_count == 2
        mock_load.assert_called_with(42)
        mock_test.assert_called_once_with("server-token", "123")

    @patch.object(ConfigManager, "load_config_by_id")
    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches_with_both_token_and_otp_id(
        self, mock_test, mock_load, client
    ):
        """api_token présent → la route n'appelle pas load_config_by_id (seule l'authentification l'a fait)"""
        mock_load.return_value = {
            "ds_api_token": "server-token",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }
        mock_test.return_value = (True, "Connexion réussie", "Titre démarche")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "demarches",
                    "api_token": "explicit-token",
                    "otp_config_id": 42,
                    "demarche_number": "123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert mock_load.call_count == 1
        mock_test.assert_called_once_with("explicit-token", "123")

    @patch.object(ConfigManager, "load_config_by_id")
    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches_with_otp_config_id_empty_token(
        self, mock_test, mock_load, client
    ):
        """otp_config_id présent mais token vide en base → 400"""
        mock_load.return_value = {
            "ds_api_token": "",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "demarches",
                    "otp_config_id": 42,
                    "demarche_number": "123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "non fourni" in data["message"]
        mock_test.assert_not_called()

    def test_api_test_connection_demarches_no_token_no_otp_id(self, client):
        """ni api_token ni otp_config_id → 400"""
        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "demarches",
                    "demarche_number": "123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "non fourni" in data["message"]

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
        assert data["title"] is None

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

    @patch("utils.api_validator.test_demarches_api")
    @patch("utils.api_validator.test_grist_api")
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
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
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

    @patch("utils.api_validator.test_demarches_api")
    @patch("utils.api_validator.test_grist_api")
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
        mock_demarches.return_value = (True, "DS OK", "Titre démarche")
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

    @patch.object(ConfigManager, "load_config_by_id")
    @patch("app.get_groups")
    def test_api_groups_otp_config_id_mode(self, mock_groups, mock_load, client):
        """Test de récupération des groupes en mode otp_config_id"""
        mock_load.return_value = {
            "ds_api_token": "token789",
            "demarche_number": "456",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }
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

        # Vérifie que load_config_by_id a été appelé (authentification puis route),
        # la garde avec l'identifiant entier et la route avec la valeur du paramètre
        assert mock_load.call_count == 2
        assert mock_load.call_args_list[0].args == (789,)
        assert mock_load.call_args_list[1].args == ("789",)

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_groups_otp_config_id_not_found(self, mock_load, client):
        """Test de récupération des groupes avec otp_config_id inexistant"""
        mock_load.side_effect = ConfigNotFoundError("Configuration non trouvée (id=999)")

        response = client.get("/api/groups?otp_config_id=999")
        assert response.status_code == 404

        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Configuration non trouvée (id=999)"

    def test_api_groups_no_params_400(self, client):
        """Test de récupération des groupes sans aucun paramètre"""
        response = client.get("/api/groups")
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data["success"] is False

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_config_not_found(self, mock_load, client):
        """otp_config_id inexistant au démarrage de sync → 404"""
        mock_load.side_effect = ConfigNotFoundError("Configuration non trouvée (id=999)")

        response = client.post(
            "/api/start-sync",
            data=json.dumps({"otp_config_id": 999, "filters": {}}),
            content_type="application/json",
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Configuration non trouvée (id=999)"

    @patch.object(sync_manager, "start_sync")
    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_manager_success(self, mock_load, mock_start, client):
        """Test de démarrage de synchronisation réussi"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "token",
            "demarche_number": "123",
            "grist_api_key": "key",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
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
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
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
        mock_test.return_value = (
            False,
            "Timeout: L'API met trop de temps à répondre",
            None,
        )

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
        assert data["title"] is None

    @patch("app.test_demarches_api")
    def test_api_test_connection_demarches_invalid_token(self, mock_test, client):
        """Test token invalide Démarches"""
        mock_test.return_value = (False, "Erreur API: Unauthorized", None)

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

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_demarches_with_otp_config_id_not_found(
        self, mock_load, client
    ):
        """otp_config_id inexistant → 404 avec message JSON"""
        mock_load.side_effect = ConfigNotFoundError("Configuration non trouvée (id=999)")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "demarches",
                    "otp_config_id": 999,
                    "demarche_number": "123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Configuration non trouvée (id=999)"

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
    @patch("app.test_grist_api")
    def test_api_test_connection_grist_with_otp_config_id(
        self, mock_test, mock_load, client
    ):
        """otp_config_id sans api_key → charge la clé depuis la DB"""
        mock_load.return_value = {
            "grist_api_key": "server-key",
            "grist_base_url": "https://grist.server.com",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }
        mock_test.return_value = (True, "Connexion réussie")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "grist",
                    "otp_config_id": 42,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert mock_load.call_count == 2
        mock_load.assert_called_with(42)
        mock_test.assert_called_once_with(
            "https://grist.server.com", "server-key", "docA"
        )

    def test_api_test_connection_grist_base_url_hors_liste(self, client):
        """URL de base hors liste blanche → 200 success:false, aucune requête émise"""
        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "grist",
                    "base_url": "https://grist.hors-liste.example",
                    "api_key": "key",
                    "doc_id": "doc123",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is False
        assert "grist.hors-liste.example" in data["message"]

    @patch.object(ConfigManager, "load_config_by_id")
    @patch("app.test_grist_api")
    def test_api_test_connection_grist_with_both_key_and_otp_id(
        self, mock_test, mock_load, client
    ):
        """api_key présent → la route n'appelle pas load_config_by_id (seule l'authentification l'a fait)"""
        mock_load.return_value = {
            "grist_api_key": "server-key",
            "grist_base_url": "https://grist.server.com",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }
        mock_test.return_value = (True, "Connexion réussie")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "grist",
                    "api_key": "explicit-key",
                    "base_url": "https://grist.explicit.com",
                    "doc_id": "explicit-doc",
                    "otp_config_id": 42,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert mock_load.call_count == 1
        mock_test.assert_called_once_with(
            "https://grist.explicit.com", "explicit-key", "explicit-doc"
        )

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_grist_with_otp_config_id_empty_key(
        self, mock_load, client
    ):
        """otp_config_id présent mais clé vide en base → 400"""
        mock_load.return_value = {
            "grist_api_key": "",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "grist",
                    "otp_config_id": 42,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "non fourni" in data["message"]

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_grist_with_otp_config_id_not_found(
        self, mock_load, client
    ):
        """otp_config_id inexistant → 404 avec message JSON"""
        mock_load.side_effect = ConfigNotFoundError("Configuration non trouvée (id=999)")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "grist",
                    "otp_config_id": 999,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Configuration non trouvée (id=999)"

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_test_connection_no_type_config_not_found(
        self, mock_load, client
    ):
        """Sans type, config absente → 404 (auparavant une 500 brute)"""
        mock_load.side_effect = ConfigNotFoundError("Configuration non trouvée (id=999)")

        response = client.post(
            "/api/test-connection",
            data=json.dumps({"otp_config_id": 999}),
            content_type="application/json",
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False
        assert data["message"] == "Configuration non trouvée (id=999)"

    @patch.object(ConfigManager, "load_config_by_id")
    def test_api_start_sync_missing_demarche_token(self, mock_load, client):
        """Test démarrage sync avec token manquant"""
        mock_load.return_value = {
            "otp_config_id": 123,
            "ds_api_token": "",  # Manquant
            "demarche_number": "123",
            "grist_api_key": "key",
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
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
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
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
            "grist_base_url": "https://grist.example.com/api",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
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
        mock_save.side_effect = Exception("Erreur BDD")

        config_data = {
            "ds_api_token": "token",
            "demarche_number": "123",
            "grist_base_url": "base",
            "grist_api_key": "key",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
        }

        response = client.post(
            "/api/config", data=json.dumps(config_data), content_type="application/json"
        )

        assert response.status_code == 500
        data = json.loads(response.data)
        assert data["success"] is False
        assert "Erreur interne lors de la sauvegarde" in data["message"]

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
        assert data_resp["message"] == "Configuration non trouvée (id=999)"

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

    @patch("app.scheduler")
    @patch("app.SessionLocal")
    def test_api_schedule_get_with_next_run(self, mock_session, mock_scheduler, client):
        """Test GET planning avec prochaine exécution prévue"""
        mock_db = mock_session.return_value
        mock_config = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_config.id = 1
        mock_schedule = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_schedule.enabled = True
        mock_schedule.last_run = None
        mock_schedule.last_status = None
        mock_job = MagicMock()
        mock_job.next_run_time = datetime(2026, 9, 3, 9, 14, tzinfo=timezone.utc)
        mock_scheduler.get_job.return_value = mock_job

        response = client.get("/api/schedule?otp_config_id=1")
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp["success"] is True
        assert data_resp["enabled"] is True
        assert data_resp["next_run"] == "2026-09-03T09:14:00+00:00"
        mock_scheduler.get_job.assert_called_once_with("scheduled_sync_1")

    @patch("app.scheduler")
    @patch("app.SessionLocal")
    def test_api_schedule_get_no_job(self, mock_session, mock_scheduler, client):
        """Test GET planning sans job scheduler (next_run None)"""
        mock_db = mock_session.return_value
        mock_config = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_config.id = 1
        mock_schedule = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_schedule.enabled = True
        mock_schedule.last_run = None
        mock_schedule.last_status = None
        mock_scheduler.get_job.return_value = None

        response = client.get("/api/schedule?otp_config_id=1")
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp["success"] is True
        assert data_resp["enabled"] is True
        assert data_resp["next_run"] is None

    @patch("app.scheduler")
    @patch("app.SessionLocal")
    def test_api_schedule_get_disabled(self, mock_session, mock_scheduler, client):
        """Test GET planning sans schedule activé (enabled False, next_run None)"""
        mock_db = mock_session.return_value
        mock_config = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_config.id = 1
        mock_schedule = (
            mock_db.query.return_value.filter_by.return_value.first.return_value
        )
        mock_schedule.enabled = False
        mock_schedule.last_run = None
        mock_schedule.last_status = None
        mock_scheduler.get_job.return_value = None

        response = client.get("/api/schedule?otp_config_id=1")
        assert response.status_code == 200

        data_resp = json.loads(response.data)
        assert data_resp["success"] is True
        assert data_resp["enabled"] is False
        assert data_resp["next_run"] is None

    @patch("app.SessionLocal")
    def test_api_schedule_get_missing_param(self, mock_session, client):
        """Test GET planning sans otp_config_id -> 400"""
        response = client.get("/api/schedule")

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
    @patch(
        "sync.scheduled_sync.compute_next_run",
        return_value=datetime(2026, 9, 3, 9, 14, tzinfo=timezone.utc),
    )
    def test_scheduled_sync_job_success(
        self,
        mock_compute_next_run,
        mock_load_config,
        mock_sessionmaker,
        mock_create_engine,
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

        mock_schedule = MagicMock()
        mock_schedule.otp_config_id = 1
        mock_schedule.last_run = None
        mock_schedule.last_status = None
        mock_schedule.next_run = None

        def query_side_effect(model):
            if model.__name__ == "OtpConfiguration":
                mock_q = MagicMock()
                mock_q.filter_by.return_value.first.return_value = mock_config
                return mock_q
            elif model.__name__ == "UserSchedule":
                mock_q = MagicMock()
                mock_q.filter_by.return_value.first.return_value = mock_schedule
                return mock_q
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

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
            args, kwargs = mock_sync.call_args
            assert args == (
                {
                    "otp_config_id": 1,
                    "demarche_number": "123",
                    "grist_doc_id": "doc456",
                    "grist_user_id": "user123",
                    "has_ds_token": True,
                    "has_grist_key": True,
                },
            )
            assert kwargs["auto"] is True
            assert callable(kwargs["progress_callback"])

            assert mock_schedule.last_run is not None
            assert mock_schedule.last_status == "success"
            assert mock_schedule.next_run == datetime(
                2026, 9, 3, 9, 14, tzinfo=timezone.utc
            )

    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager.load_config_by_id")
    @patch(
        "sync.scheduled_sync.compute_next_run",
        return_value=datetime(2026, 9, 3, 9, 14, tzinfo=timezone.utc),
    )
    def test_scheduled_sync_job_error(
        self, mock_compute_next_run, mock_load_config, mock_sessionmaker
    ):
        """Test sync échouée (success=False) : last_status=error, schedule reste actif"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_db = MagicMock()
        mock_session_class = MagicMock(return_value=mock_db)
        mock_sessionmaker.return_value = mock_session_class

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.grist_user_id = "user123"
        mock_config.grist_doc_id = "doc456"

        mock_schedule = MagicMock()
        mock_schedule.otp_config_id = 1
        mock_schedule.last_run = None
        mock_schedule.last_status = None
        mock_schedule.next_run = None
        mock_schedule.enabled = True

        def query_side_effect(model):
            if model.__name__ == "OtpConfiguration":
                mock_q = MagicMock()
                mock_q.filter_by.return_value.first.return_value = mock_config
                return mock_q
            elif model.__name__ == "UserSchedule":
                mock_q = MagicMock()
                mock_q.filter_by.return_value.first.return_value = mock_schedule
                return mock_q
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

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
            args, kwargs = mock_sync.call_args
            assert args == (
                {
                    "otp_config_id": 1,
                    "demarche_number": "123",
                    "grist_doc_id": "doc456",
                    "grist_user_id": "user123",
                    "has_ds_token": True,
                    "has_grist_key": True,
                },
            )
            assert kwargs["auto"] is True
            assert callable(kwargs["progress_callback"])

            assert mock_schedule.last_run is not None
            assert mock_schedule.last_status == "error"
            assert mock_schedule.next_run == datetime(
                2026, 9, 3, 9, 14, tzinfo=timezone.utc
            )
            assert mock_schedule.enabled is True

    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager.load_config_by_id")
    def test_scheduled_sync_job_external_api_error_disables_schedule(
        self, mock_load_config, mock_sessionmaker
    ):
        """Test erreur API externe : schedule désactivé automatiquement"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager
        from utils.constants import EXIT_CODE_EXTERNAL_API_ERROR

        mock_db = MagicMock()
        mock_session_class = MagicMock(return_value=mock_db)
        mock_sessionmaker.return_value = mock_session_class

        mock_config = MagicMock()
        mock_config.id = 1
        mock_config.grist_user_id = "user123"
        mock_config.grist_doc_id = "doc456"

        mock_schedule = MagicMock()
        mock_schedule.otp_config_id = 1
        mock_schedule.last_run = None
        mock_schedule.last_status = None
        mock_schedule.next_run = None
        mock_schedule.enabled = True

        def query_side_effect(model):
            if model.__name__ == "OtpConfiguration":
                mock_q = MagicMock()
                mock_q.filter_by.return_value.first.return_value = mock_config
                return mock_q
            elif model.__name__ == "UserSchedule":
                mock_q = MagicMock()
                mock_q.filter_by.return_value.first.return_value = mock_schedule
                return mock_q
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

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
            mock_sync.return_value = {
                "success": False,
                "error_code": EXIT_CODE_EXTERNAL_API_ERROR,
                "message": "Erreur API externe",
            }

            scheduled_sync_job(1, sync_manager)

            mock_sync.assert_called_once()

            assert mock_schedule.last_run is not None
            assert mock_schedule.next_run is None
            assert mock_schedule.last_status is None
            assert mock_schedule.enabled is False

    @patch("sync.scheduled_sync.SYNC_MINUTE", 0)
    @patch("sync.scheduled_sync.SYNC_HOUR", 11)
    @patch("sync.scheduled_sync.sessionmaker")
    def test_reload_scheduler_jobs(self, mock_sessionmaker):
        """Test rechargement des jobs du scheduler (stagger +5 min par config)"""
        from sync.scheduled_sync import reload_scheduler_jobs, scheduler
        from sync.sync_manager import SyncManager

        mock_db = MagicMock()
        mock_sessionmaker.return_value = MagicMock(return_value=mock_db)

        mock_schedule1 = MagicMock()
        mock_schedule1.otp_config_id = 1
        mock_schedule1.enabled = True

        mock_schedule2 = MagicMock()
        mock_schedule2.otp_config_id = 2
        mock_schedule2.enabled = True

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
            if kwargs.get("enabled"):
                mock_query = MagicMock()
                mock_query.filter.return_value.all.return_value = [
                    mock_schedule1,
                    mock_schedule2,
                ]
                return mock_query
            if kwargs.get("id") == 1:
                return MagicMock(first=MagicMock(return_value=mock_config1))
            elif kwargs.get("id") == 2:
                return MagicMock(first=MagicMock(return_value=mock_config2))
            return MagicMock(first=MagicMock(return_value=None))

        mock_db.query.return_value.filter_by.side_effect = mock_filter_by

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(scheduler, "remove_all_jobs") as mock_remove, patch.object(
            scheduler, "add_job"
        ) as mock_add:
            reload_scheduler_jobs(sync_manager)

            mock_remove.assert_called_once()

            assert mock_add.call_count == 2

            job_ids = [call.kwargs["id"] for call in mock_add.call_args_list]
            assert job_ids == ["scheduled_sync_1", "scheduled_sync_2"]

            first_trigger = mock_add.call_args_list[0].kwargs["trigger"]
            second_trigger = mock_add.call_args_list[1].kwargs["trigger"]

            def trigger_value(trigger, name):
                return [
                    f for f in trigger.fields if f.name == name
                ][0].expressions[0].first

            assert trigger_value(first_trigger, "hour") == 11
            assert trigger_value(first_trigger, "minute") == 0
            assert trigger_value(second_trigger, "hour") == 11
            assert trigger_value(second_trigger, "minute") == 5


class SyncLogMock:
    """Mock simple pour SyncLog avec attributs sérialisables"""

    def __init__(
        self,
        timestamp_iso,
        status,
        success_count,
        error_count,
        message,
        otp_config_id=None,
        demarche_number=None,
    ):
        self.timestamp = datetime.fromisoformat(timestamp_iso)
        self.status = status
        self.success_count = success_count
        self.error_count = error_count
        self.message = message
        self.otp_config_id = otp_config_id
        self.demarche_number = demarche_number


class OtpConfigMock:
    """Mock simple pour OtpConfiguration avec attributs sérialisables"""

    def __init__(self, id, grist_user_id, grist_doc_id):
        self.id = id
        self.grist_user_id = grist_user_id
        self.grist_doc_id = grist_doc_id


class TestApiSyncLogLatestWithOTPConfigId:
    """Tests pour la route /api/sync-log/latest utilisant otp_config_id"""

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

class TestApiSyncLogLatestWithGristDocId:
    """Tests pour le rapport de sync par document du jeton, sans configuration."""

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_success_with_both(self, mock_session, client):
        """Test retour avec auto et manual sync"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_sync_auto = SyncLogMock(
            "2026-04-20T10:00:00+00:00", "success", 10, 0, "Sync auto réussie"
        )
        mock_sync_manual = SyncLogMock(
            "2026-04-20T14:30:00+00:00", "success", 5, 1, "Sync manuelle réussie"
        )

        mock_db.query.return_value.filter_by.return_value.order_by.return_value.first.side_effect = [
            mock_sync_auto,
            mock_sync_manual,
        ]

        response = client.get("/api/sync-log/latest")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["auto"] is not None
        assert data["auto"]["status"] == "success"
        assert data["auto"]["success_count"] == 10
        assert data["manual"] is not None
        assert data["manual"]["success_count"] == 5

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_auto_only(self, mock_session, client):
        """Test retour avec seulement sync auto"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db

        mock_sync_auto = SyncLogMock(
            "2026-04-20T10:00:00+00:00", "success", 10, 0, "Sync auto réussie"
        )

        mock_db.query.return_value.filter_by.return_value.order_by.return_value.first.side_effect = [
            mock_sync_auto,
            None,
        ]

        response = client.get("/api/sync-log/latest")
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
        mock_db.query.return_value.filter_by.return_value.order_by.return_value.first.side_effect = [
            None,
            None,
        ]

        response = client.get("/api/sync-log/latest")

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["auto"] is None
        assert data["manual"] is None

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_no_sync_for_grist_doc(self, mock_session, client):
        """Document sans historique → rapport vide, sans configuration enregistrée"""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter_by.return_value.order_by.return_value.first.side_effect = [
            None,
            None,
        ]

        client.identity = {"userId": "newU", "docId": "docZ", "readOnly": False}

        response = client.get("/api/sync-log/latest")
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data["success"] is True
        assert data["auto"] is None
        assert data["manual"] is None

    @patch("app.SessionLocal")
    def test_api_sync_log_latest_uses_doc_from_identity(self, mock_session, client):
        """Le document du rapport est celui du jeton, jamais un paramètre de requête."""
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter_by.return_value.order_by.return_value.first.side_effect = [
            None,
            None,
        ]

        client.identity = {"userId": "userA", "docId": "docB", "readOnly": False}

        response = client.get("/api/sync-log/latest?grist_doc_id=999")
        assert response.status_code == 200

        filter_calls = mock_db.query.return_value.filter_by.call_args_list
        assert all(call.kwargs["grist_doc_id"] == "docB" for call in filter_calls)
        assert all("grist_user_id" not in call.kwargs for call in filter_calls)

    def test_api_sync_log_latest_requires_doc(self, client):
        """Sans otp_config_id ni document d'identité → 400"""
        client.identity = {"userId": "userA", "docId": None, "readOnly": False}

        response = client.get(
            "/api/sync-log/latest?grist_base_url=https://grist.example.com/api"
        )
        assert response.status_code == 400

        data = json.loads(response.data)
        assert data["success"] is False
        assert "otp_config_id" in data["message"]


WIDGET_TEST_CONFIG = {
    "otp_config_id": 7,
    "ds_api_token": "ds-token",
    "demarche_number": "123",
    "grist_base_url": "https://grist.example.com/api",
    "grist_api_key": "grist-key",
    "grist_doc_id": "docA",
    "grist_user_id": "userA",
}


class TestWidgetAuth:
    """Authentification des requêtes par le jeton widget."""

    PROTECTED = [
        ("post", "/api/config"),
        ("get", "/api/config"),
        ("delete", "/api/config/7"),
        ("post", "/api/schedule"),
        ("delete", "/api/schedule"),
        ("get", "/api/schedule?otp_config_id=7"),
        ("post", "/api/start-sync"),
        ("post", "/api/test-connection"),
        ("get", "/api/groups?otp_config_id=7"),
        ("get", "/api/sync-log/latest?otp_config_id=7"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED)
    def test_missing_token_returns_401(self, client, method, path):
        client.anonymous = True
        response = getattr(client, method)(path, json={})
        assert response.status_code == 401

    def test_malformed_token_returns_401(self, client):
        client.raw_token = "not-a-jwt"
        response = client.post(
            "/api/config", json={"grist_base_url": "https://grist.example.com/api"}
        )
        assert response.status_code == 401

    def test_rejected_token_returns_401(self, client):
        client.validation_error = WidgetTokenInvalidError("refusé")
        response = client.post(
            "/api/config", json={"grist_base_url": "https://grist.example.com/api"}
        )
        assert response.status_code == 401

    def test_grist_unavailable_returns_502(self, client):
        client.validation_error = WidgetTokenUnavailableError("réseau")
        response = client.post(
            "/api/config", json={"grist_base_url": "https://grist.example.com/api"}
        )
        assert response.status_code == 502

    @staticmethod
    def _stub_owned_config(monkeypatch, config):
        monkeypatch.setattr(
            "app.config_manager.load_config_by_id", lambda otp_config_id: config
        )

    def test_other_user_on_existing_config_returns_403(self, client, monkeypatch):
        self._stub_owned_config(monkeypatch, WIDGET_TEST_CONFIG)
        client.identity = {"userId": "userB", "docId": "docA", "readOnly": False}
        response = client.post("/api/schedule", json={"otp_config_id": 7})
        assert response.status_code == 403

    def test_other_document_on_existing_config_returns_403(self, client, monkeypatch):
        self._stub_owned_config(monkeypatch, WIDGET_TEST_CONFIG)
        client.identity = {"userId": "userA", "docId": "docB", "readOnly": False}
        response = client.post("/api/schedule", json={"otp_config_id": 7})
        assert response.status_code == 403

    def test_other_user_cannot_delete_config_returns_403(self, client, monkeypatch):
        self._stub_owned_config(monkeypatch, WIDGET_TEST_CONFIG)
        client.identity = {"userId": "userB", "docId": "docA", "readOnly": False}
        response = client.delete("/api/config/7")
        assert response.status_code == 403

    def test_other_user_cannot_update_config_returns_403(self, client, monkeypatch):
        self._stub_owned_config(monkeypatch, WIDGET_TEST_CONFIG)
        client.identity = {"userId": "userB", "docId": "docA", "readOnly": False}
        response = client.post(
            "/api/config",
            json={"otp_config_id": 7, "grist_base_url": "https://grist.example.com/api"},
        )
        assert response.status_code == 403

    def test_editor_token_allows_write(self, client, monkeypatch):
        self._stub_owned_config(monkeypatch, WIDGET_TEST_CONFIG)
        monkeypatch.setattr(
            "app.sync_manager.start_sync", lambda config, auto=False: "task-1"
        )
        response = client.post("/api/start-sync", json={"otp_config_id": 7})
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    def test_readonly_token_rejected_on_write_returns_403(self, client, monkeypatch):
        self._stub_owned_config(monkeypatch, WIDGET_TEST_CONFIG)
        client.identity = {"userId": "userA", "docId": "docA", "readOnly": True}
        response = client.delete("/api/config/7")
        assert response.status_code == 403

    def test_readonly_token_rejected_on_read_returns_403(self, client, monkeypatch):
        self._stub_owned_config(monkeypatch, WIDGET_TEST_CONFIG)
        client.identity = {"userId": "userA", "docId": "docA", "readOnly": True}
        response = client.get("/api/sync-log/latest?otp_config_id=7")
        assert response.status_code == 403

    @staticmethod
    def _stub_document_access(monkeypatch, *, document_info=None, error=None):
        """Simule la consultation du document ciblé par la clé API."""
        get_document_info = MagicMock()
        if error is not None:
            get_document_info.side_effect = error
        else:
            get_document_info.return_value = document_info
        grist_client = MagicMock()
        grist_client.return_value.get_document_info = get_document_info
        monkeypatch.setattr("security.widget_auth.GristClient", grist_client)

    @staticmethod
    def _http_error(status_code):
        response = requests.Response()
        response.status_code = status_code

        return requests.exceptions.HTTPError(response=response)

    def test_key_without_document_access_returns_403(self, client, monkeypatch):
        """La clé qui ne voit pas le document (404) est refusée."""
        self._stub_document_access(monkeypatch, error=self._http_error(404))
        response = client.post(
            "/api/config",
            json={
                "grist_base_url": "https://grist.example.com/api",
                "grist_api_key": "some-key",
            },
        )
        assert response.status_code == 403
        data = json.loads(response.data)
        assert "sans accès au document" in data["message"]

    def test_key_document_lookup_unavailable_returns_502(self, client, monkeypatch):
        """Grist injoignable pendant la vérification de la clé : 502."""
        self._stub_document_access(
            monkeypatch, error=requests.exceptions.ConnectionError()
        )
        response = client.post(
            "/api/config",
            json={
                "grist_base_url": "https://grist.example.com/api",
                "grist_api_key": "some-key",
            },
        )
        assert response.status_code == 502

    def test_viewer_key_returns_403(self, client, monkeypatch):
        """Un accès lecture seule ne suffit pas pour synchroniser."""
        self._stub_document_access(monkeypatch, document_info={"access": "viewers"})
        response = client.post(
            "/api/config",
            json={
                "grist_base_url": "https://grist.example.com/api",
                "grist_api_key": "some-key",
            },
        )
        assert response.status_code == 403
        data = json.loads(response.data)
        assert "propriétaire" in data["message"]

    def test_editor_key_returns_403(self, client, monkeypatch):
        """Un accès éditeur ne suffit pas : seule la sauvegarde d'une clé propriétaire est acceptée."""
        self._stub_document_access(monkeypatch, document_info={"access": "editors"})
        response = client.post(
            "/api/config",
            json={
                "grist_base_url": "https://grist.example.com/api",
                "grist_api_key": "some-key",
            },
        )
        assert response.status_code == 403
        data = json.loads(response.data)
        assert "propriétaire" in data["message"]

    def test_unspecified_access_key_allows_save(self, client, monkeypatch):
        """Grist n'expose pas le niveau d'accès : la clé est acceptée."""
        self._stub_document_access(monkeypatch, document_info={"name": "Doc"})
        monkeypatch.setattr("app.config_manager.save_config", lambda config: True)
        response = client.post(
            "/api/config",
            json={"otp_config_id": 1, "grist_api_key": "some-key"},
        )
        assert response.status_code == 200

    def test_service_account_key_allows_save(self, client, monkeypatch):
        """La clé d'un compte de service doit pouvoir être enregistrée.

        /profile/user renvoie l'id du compte de service, pas celui de
        l'utilisateur du widget : seule la consultation du document compte.
        """
        grist_client = MagicMock()
        grist_client.return_value.get_document_info.return_value = {"access": "owners"}
        grist_client.return_value.get_profile.return_value = {
            "id": "service-account-42"
        }
        monkeypatch.setattr("security.widget_auth.GristClient", grist_client)
        monkeypatch.setattr("app.config_manager.save_config", lambda config: True)
        response = client.post(
            "/api/config",
            json={"otp_config_id": 1, "grist_api_key": "sa-key"},
        )
        assert response.status_code == 200

    def test_ids_come_from_identity_not_body(self, client, monkeypatch):
        saved = {}
        monkeypatch.setattr(
            "app.config_manager.save_config",
            lambda config: saved.update(config) or True,
        )
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = MagicMock(
            id=42
        )
        monkeypatch.setattr("app.SessionLocal", lambda: mock_db)

        response = client.post(
            "/api/config",
            json={
                "ds_api_token": "ds",
                "demarche_number": "123",
                "grist_base_url": "https://grist.example.com/api",
                "grist_api_key": "key",
                "grist_user_id": "spoofed",
                "grist_doc_id": "spoofed",
            },
        )

        assert response.status_code == 200
        assert saved["grist_user_id"] == "userA"
        assert saved["grist_doc_id"] == "docA"

    def test_new_user_gets_empty_configs(self, client, monkeypatch):
        """Un nouvel utilisateur reçoit une configuration vide, après validation du jeton."""
        monkeypatch.setattr(
            "app.config_manager.load_config", lambda grist_user_id, grist_doc_id: []
        )
        validated_base_urls = []
        monkeypatch.setattr(
            "security.widget_auth.validate_widget_token",
            lambda token, base_url, doc_id: validated_base_urls.append(base_url)
            or {"userId": "newU", "docId": "newDoc", "readOnly": False},
        )
        client.identity = {"userId": "newU", "docId": "newDoc", "readOnly": False}

        response = client.get(
            "/api/config?grist_base_url=https://grist.example.com/api"
        )

        assert response.status_code == 200
        assert response.get_json() == {"configs": []}
        assert validated_base_urls == ["https://grist.example.com/api"]

    def test_config_get_without_base_url_is_rejected(self, client, monkeypatch):
        """Sans URL Grist connue, le jeton n'est pas vérifiable : la requête est refusée."""
        monkeypatch.setattr(
            "app.config_manager.load_config", lambda grist_user_id, grist_doc_id: []
        )
        client.identity = {"userId": "newU", "docId": "newDoc", "readOnly": False}

        response = client.get("/api/config")

        assert response.status_code == 400

    def test_config_load_failure_is_rejected(self, client, monkeypatch):
        """Le contrôle d'appartenance exige le chargement : une erreur le fait échouer."""

        def explode(otp_config_id):
            raise RuntimeError("connexion perdue")

        monkeypatch.setattr("app.config_manager.load_config_by_id", explode)

        response = client.get("/api/sync-log/latest?otp_config_id=7")

        assert response.status_code == 500
        assert response.get_json()["message"] == "Configuration indisponible"

    @patch("app.SessionLocal")
    def test_missing_config_reaches_the_route(self, mock_session, client, monkeypatch):
        """Une configuration absente n'est pas une erreur de chargement : la route répond 404."""
        mock_session.return_value.query.return_value.filter_by.return_value.first.\
            return_value = None

        def missing(otp_config_id):
            raise ConfigNotFoundError("Configuration non trouvée (id=999)")

        monkeypatch.setattr("app.config_manager.load_config_by_id", missing)

        response = client.delete("/api/config/999")

        assert response.status_code == 404

    @patch("app.SessionLocal")
    def test_zero_config_id_is_treated_as_missing(
        self, mock_session, client, monkeypatch
    ):
        """otp_config_id=0 désigne une configuration inexistante : la route répond 404."""
        monkeypatch.setattr(
            "configuration.config_manager.DatabaseManager.get_connection",
            MagicMock(),
        )
        mock_session.return_value.query.return_value.filter_by.return_value.first.\
            return_value = None

        response = client.get("/api/schedule?otp_config_id=0")

        assert response.status_code == 404
        assert response.get_json()["message"] == "Configuration non trouvée (id=0)"

    def test_stored_base_url_is_used_over_request_param(self, client, monkeypatch):
        """L'URL de vérification vient de la config stockée, pas du paramètre de l'appelant."""
        validated_base_urls = []
        monkeypatch.setattr(
            "security.widget_auth.validate_widget_token",
            lambda token, base_url, doc_id: validated_base_urls.append(base_url)
            or {"userId": "userA", "docId": "docA", "readOnly": False},
        )

        response = client.get("/api/config?grist_base_url=https://evil.example.com/api")

        assert response.status_code == 200
        assert validated_base_urls == ["https://grist.example.com/api"]

    def test_stored_config_load_failure_is_rejected(self, client, monkeypatch):
        """Une erreur de chargement de la config stockée ne retombe pas sur l'URL fournie."""

        def explode(grist_user_id, grist_doc_id):
            raise RuntimeError("connexion perdue")

        monkeypatch.setattr("app.config_manager.load_config", explode)

        response = client.get(
            "/api/config?grist_base_url=https://grist.example.com/api"
        )

        assert response.status_code == 500
        assert response.get_json()["message"] == "Configuration indisponible"

    @patch("app.test_demarches_api")
    def test_new_user_demarches_test_with_base_url_header(
        self, mock_test, client, monkeypatch
    ):
        """Un nouvel utilisateur présente l'en-tête X-Grist-Base-Url : le test DN passe."""
        monkeypatch.setattr(
            "app.config_manager.load_config", lambda grist_user_id, grist_doc_id: []
        )
        validated_base_urls = []
        monkeypatch.setattr(
            "security.widget_auth.validate_widget_token",
            lambda token, base_url, doc_id: validated_base_urls.append(base_url)
            or {"userId": "newU", "docId": "newDoc", "readOnly": False},
        )
        client.identity = {"userId": "newU", "docId": "newDoc", "readOnly": False}
        mock_test.return_value = (True, "Connexion réussie", "Titre démarche")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "demarches",
                    "api_token": "token",
                    "demarche_number": "123",
                }
            ),
            content_type="application/json",
            headers={"X-Grist-Base-Url": "https://grist.example.com/api"},
        )

        assert response.status_code == 200
        assert validated_base_urls == ["https://grist.example.com/api"]
        mock_test.assert_called_once_with("token", "123")

    @patch("app.test_demarches_api")
    def test_body_base_url_serves_new_user(self, mock_test, client, monkeypatch):
        """L'URL fournie dans le corps reste une source valide pour un nouvel utilisateur."""
        monkeypatch.setattr(
            "app.config_manager.load_config", lambda grist_user_id, grist_doc_id: []
        )
        validated_base_urls = []
        monkeypatch.setattr(
            "security.widget_auth.validate_widget_token",
            lambda token, base_url, doc_id: validated_base_urls.append(base_url)
            or {"userId": "newU", "docId": "newDoc", "readOnly": False},
        )
        client.identity = {"userId": "newU", "docId": "newDoc", "readOnly": False}
        mock_test.return_value = (True, "Connexion réussie", "Titre démarche")

        response = client.post(
            "/api/test-connection",
            data=json.dumps(
                {
                    "type": "demarches",
                    "api_token": "token",
                    "demarche_number": "123",
                    "grist_base_url": "https://grist.example.com/api",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 200
        assert validated_base_urls == ["https://grist.example.com/api"]

    def test_stored_base_url_is_used_over_header(self, client, monkeypatch):
        """L'URL de vérification vient de la config stockée, pas de l'en-tête de l'appelant."""
        validated_base_urls = []
        monkeypatch.setattr(
            "security.widget_auth.validate_widget_token",
            lambda token, base_url, doc_id: validated_base_urls.append(base_url)
            or {"userId": "userA", "docId": "docA", "readOnly": False},
        )

        response = client.get(
            "/api/config",
            headers={"X-Grist-Base-Url": "https://evil.example.com/api"},
        )

        assert response.status_code == 200
        assert validated_base_urls == ["https://grist.example.com/api"]


class TestGristKeyAccessField:
    """Champ grist_key_access sur GET /api/config (niveau d'accès de la clé)."""

    @staticmethod
    def _config_from_response(response):
        assert response.status_code == 200
        return response.get_json()["configs"][0]

    @staticmethod
    def _stub_document_access(monkeypatch, *, document_info=None, error=None):
        grist_client = MagicMock()
        if error is not None:
            grist_client.return_value.get_document_info.side_effect = error
        else:
            grist_client.return_value.get_document_info.return_value = document_info
        monkeypatch.setattr("security.widget_auth.GristClient", grist_client)
        return grist_client

    def test_grist_key_access_reports_owners(self, client):
        """La config stockée expose le niveau d'accès fourni par Grist, sans la clé."""
        response = client.get("/api/config")

        config = self._config_from_response(response)
        assert config["grist_key_access"] == "owners"
        assert config["has_grist_key"] is True
        assert "grist_api_key" not in config

    def test_grist_key_access_reports_viewer(self, client, monkeypatch):
        """Une clé rétrogradée viewer apparaît explicitement dans la réponse."""
        self._stub_document_access(monkeypatch, document_info={"access": "viewers"})

        response = client.get("/api/config")

        assert self._config_from_response(response)["grist_key_access"] == "viewers"

    def test_grist_key_access_absent_without_key(self, client, monkeypatch):
        """Sans clé enregistrée, le champ n'est pas produit (rien à vérifier)."""
        monkeypatch.setattr(
            "app.config_manager.load_config",
            lambda grist_user_id, grist_doc_id: [
                {
                    "otp_config_id": 1,
                    "demarche_number": "123",
                    "grist_base_url": "https://grist.example.com/api",
                    "grist_doc_id": "docA",
                    "grist_user_id": "userA",
                }
            ],
        )

        response = client.get("/api/config")

        config = self._config_from_response(response)
        assert "grist_key_access" not in config
        assert config["has_grist_key"] is False

    def test_grist_key_access_is_cached(self, client, monkeypatch):
        """Deux lectures successives n'interrogent Grist qu'une seule fois."""
        grist_client = self._stub_document_access(
            monkeypatch, document_info={"access": "owners"}
        )

        first = client.get("/api/config")
        second = client.get("/api/config")

        assert self._config_from_response(first)["grist_key_access"] == "owners"
        assert self._config_from_response(second)["grist_key_access"] == "owners"
        assert grist_client.return_value.get_document_info.call_count == 1

    def test_grist_key_access_unavailable_on_error(self, client, monkeypatch):
        """Une erreur réseau côté Grist produit un niveau explicite, sans casser le GET."""
        self._stub_document_access(monkeypatch, error=ConnectionError("réseau"))

        response = client.get("/api/config")

        assert (
            self._config_from_response(response)["grist_key_access"] == "unavailable"
        )
