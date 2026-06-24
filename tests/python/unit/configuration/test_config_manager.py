import pytest
import os
from unittest.mock import patch, MagicMock
from configuration.config_manager import ConfigManager


class TestConfigManager:
    """Tests unitaires pour la classe ConfigManager"""

    @patch("configuration.config_manager.Fernet")
    @patch.dict(os.environ, {"ENCRYPTION_KEY": "test_key"})
    def test_encrypt_decrypt_value(self, mock_fernet):
        """Test du chiffrement et déchiffrement d'une valeur"""
        # Mock Fernet
        mock_fernet_instance = MagicMock()
        mock_fernet_instance.encrypt.return_value = b"encrypted_data"
        mock_fernet_instance.decrypt.return_value = b"test_sensitive_data"
        mock_fernet.return_value = mock_fernet_instance

        original_value = "test_sensitive_data"

        # Chiffrement
        encrypted = ConfigManager.encrypt_value(original_value)
        assert encrypted == "encrypted_data"

        # Déchiffrement
        decrypted = ConfigManager.decrypt_value(encrypted)
        assert decrypted == "test_sensitive_data"

        # Vérifier que Fernet a été appelé correctement
        mock_fernet.assert_called_with(b"test_key")

    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_encrypt_empty_value(self):
        """Test du chiffrement d'une valeur vide"""
        encrypted = ConfigManager.encrypt_value("")
        assert encrypted == ""

        encrypted = ConfigManager.encrypt_value(None)
        assert encrypted is None

    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_decrypt_empty_value(self):
        """Test du déchiffrement d'une valeur vide"""
        decrypted = ConfigManager.decrypt_value("")
        assert decrypted == ""

        decrypted = ConfigManager.decrypt_value(None)
        assert decrypted is None

    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_decrypt_unencrypted_value(self):
        """Test du déchiffrement d'une valeur non chiffrée (doit lever ValueError)"""
        with pytest.raises(ValueError, match="Échec du déchiffrement"):
            ConfigManager.decrypt_value("unencrypted_value")

    @patch.dict(os.environ, {"ENCRYPTION_KEY": ""})
    def test_get_encryption_key_missing(self):
        """Test d'erreur quand la clé de chiffrement est manquante"""
        with pytest.raises(ValueError, match='"ENCRYPTION_KEY" non définie'):
            ConfigManager.get_encryption_key()

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_load_config_existing(self, mock_db_manager):
        """Test du chargement d'une configuration existante - retourne une liste"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock des données retournées par la DB - liste de tuples (fetchall)
        mock_cursor.fetchall.return_value = [
            (
                1,  # id (otp_config_id)
                "encrypted_token",  # ds_api_token (à déchiffrer)
                "12345",  # demarche_number
                "https://test.grist.com",  # grist_base_url
                "encrypted_key",  # grist_api_key (à déchiffrer)
                "test_doc",  # grist_doc_id
                "test_user",  # grist_user_id
                "2023-01-01",  # filter_date_start
                "2023-12-31",  # filter_date_end
                "status1,status2",  # filter_statuses
                "group1,group2",  # filter_groups
            )
        ]

        # Mock des méthodes de déchiffrement
        with patch.object(
            ConfigManager, "decrypt_value", side_effect=lambda x: f"decrypted_{x}"
        ):
            config_manager = ConfigManager("dummy_url")
            configs = config_manager.load_config("test_user", "test_doc")

        # Vérifications - c'est une liste
        assert isinstance(configs, list)
        assert len(configs) == 1

        config = configs[0]  # Prendre la première config
        assert config["otp_config_id"] == 1
        assert config["ds_api_token"] == "decrypted_encrypted_token"
        assert config["demarche_number"] == "12345"
        assert config["grist_base_url"] == "https://test.grist.com"
        assert config["grist_api_key"] == "decrypted_encrypted_key"
        assert config["grist_doc_id"] == "test_doc"
        assert config["grist_user_id"] == "test_user"
        assert config["filter_date_start"] == "2023-01-01"
        assert config["filter_date_end"] == "2023-12-31"
        assert config["filter_statuses"] == "status1,status2"
        assert config["filter_groups"] == "group1,group2"

        # Vérifier que la requête SQL a été appelée correctement
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert "SELECT id," in call_args[0]
        assert "FROM otp_configurations" in call_args[0]
        assert call_args[1] == ("test_user", "test_doc")

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_load_config_not_found(self, mock_db_manager):
        """Test du chargement quand aucune configuration n'existe - retourne liste avec config vide"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock : aucune ligne trouvée (fetchall retourne liste vide)
        mock_cursor.fetchall.return_value = []

        config_manager = ConfigManager("dummy_url")
        configs = config_manager.load_config("test_user", "test_doc")

        # Vérifications - c'est une liste avec une config vide
        assert isinstance(configs, list)
        assert len(configs) == 1
        config = configs[0]  # Prendre la première (config vide)

        # Vérifications des valeurs par défaut
        assert config["otp_config_id"] is None
        assert config["ds_api_token"] == ""
        assert config["demarche_number"] == ""
        assert config["grist_base_url"] == "https://grist.numerique.gouv.fr/api"
        assert config["grist_api_key"] == ""
        assert config["grist_doc_id"] == ""
        assert config["grist_user_id"] == ""
        assert config["filter_date_start"] == ""
        assert config["filter_date_end"] == ""
        assert config["filter_statuses"] == ""
        assert config["filter_groups"] == ""

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_load_config_invalid_params(self, mock_db_manager):
        """Test d'erreur avec des paramètres invalides"""
        config_manager = ConfigManager("dummy_url")
        with pytest.raises(Exception, match="No grist user id or doc id"):
            config_manager.load_config("", "")

        with pytest.raises(Exception, match="No grist user id or doc id"):
            config_manager.load_config(None, "test_doc")

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_save_config_update_existing(self, mock_db_manager):
        """Test de la sauvegarde (mise à jour par ID)"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock : config existe avec tokens existants
        mock_cursor.fetchone.return_value = [
            "existing_encrypted_token",
            "existing_encrypted_key",
        ]

        # Mock des méthodes de chiffrement
        with patch.object(
            ConfigManager, "encrypt_value", side_effect=lambda x: f"encrypted_{x}"
        ):
            config_manager = ConfigManager("dummy_url")
            result = config_manager.save_config(
                {
                    "otp_config_id": 1,
                    "ds_api_token": "test_token",
                    "demarche_number": "12345",
                    "grist_base_url": "https://test.grist.com",
                    "grist_api_key": "test_key",
                    "grist_doc_id": "test_doc",
                    "grist_user_id": "test_user",
                    "filter_date_start": "2023-01-01",
                    "filter_date_end": "2023-12-31",
                    "filter_statuses": "status1,status2",
                    "filter_groups": "group1,group2",
                }
            )

        assert result is True

        # Vérifier que SELECT (tokens) + UPDATE ont été appelés
        assert mock_cursor.execute.call_count == 2  # SELECT tokens + UPDATE
        select_call = mock_cursor.execute.call_args_list[0]
        assert "SELECT ds_api_token, grist_api_key" in select_call[0][0]
        assert "FROM otp_configurations" in select_call[0][0]
        assert "WHERE id = %s" in select_call[0][0]
        update_call = mock_cursor.execute.call_args_list[1]
        assert "UPDATE otp_configurations SET" in update_call[0][0]
        assert "filter_date_start" in update_call[0][0]

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_save_config_insert_new(self, mock_db_manager):
        """Test de la sauvegarde (insertion d'une nouvelle config sans otp_config_id)"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock des méthodes de chiffrement
        with patch.object(
            ConfigManager, "encrypt_value", side_effect=lambda x: f"encrypted_{x}"
        ):
            config_manager = ConfigManager("dummy_url")
            result = config_manager.save_config(
                {
                    "ds_api_token": "test_token",
                    "demarche_number": "12345",
                    "grist_base_url": "https://test.grist.com",
                    "grist_api_key": "test_key",
                    "grist_doc_id": "test_doc",
                    "grist_user_id": "test_user",
                    "filter_date_start": "2023-01-01",
                    "filter_date_end": "2023-12-31",
                    "filter_statuses": "status1,status2",
                    "filter_groups": "group1,group2",
                }
            )

        assert result is True

        # Vérifier que INSERT a été appelé (pas de SELECT COUNT)
        assert mock_cursor.execute.call_count == 1  # Juste INSERT
        insert_call = mock_cursor.execute.call_args_list[0]
        assert "INSERT INTO otp_configurations" in insert_call[0][0]
        assert "filter_date_start" in insert_call[0][0]

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(os.environ, {"ENCRYPTION_KEY": "test_key"})
    def test_save_config_invalid_params(self, mock_db_manager):
        """Test d'erreur de sauvegarde avec paramètres invalides"""
        # La méthode retourne False au lieu de lever une exception
        config_manager = ConfigManager("dummy_url")
        result = config_manager.save_config(
            {"grist_user_id": "", "grist_doc_id": "test_doc"}
        )
        assert result is False

    def test_sensitive_keys_constant(self):
        """Test de la constante SENSITIVE_KEYS"""
        assert "ds_api_token" in ConfigManager.SENSITIVE_KEYS
        assert "grist_api_key" in ConfigManager.SENSITIVE_KEYS
        assert len(ConfigManager.SENSITIVE_KEYS) == 2

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_save_config_partial_without_grist_key(self, mock_db_manager):
        """Test de la sauvegarde partielle sans clé API Grist (nouvelle config)"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock des méthodes de chiffrement (ne chiffre que les valeurs non vides)
        with patch.object(
            ConfigManager,
            "encrypt_value",
            side_effect=lambda x: f"encrypted_{x}" if x else x,
        ):
            config_manager = ConfigManager("dummy_url")
            result = config_manager.save_config(
                {
                    "ds_api_token": "test_token",
                    "demarche_number": "12345",
                    "grist_base_url": "https://grist.numerique.gouv.fr/api",
                    "grist_doc_id": "test_doc",
                    "grist_user_id": "test_user",
                    # grist_api_key manquant (sauvegarde partielle)
                    "filter_date_start": "2023-01-01",
                    "filter_date_end": "2023-12-31",
                    "filter_statuses": "status1,status2",
                    "filter_groups": "group1,group2",
                }
            )

        assert result is True

        # Vérifier que INSERT a été appelé (pas de SELECT COUNT)
        assert mock_cursor.execute.call_count == 1  # Juste INSERT
        insert_call = mock_cursor.execute.call_args_list[0]
        assert "INSERT INTO otp_configurations" in insert_call[0][0]

        # Vérifier que les valeurs chiffrées sont correctes
        call_args = insert_call[0]
        assert call_args[1][0] == "encrypted_test_token"  # ds_api_token
        assert call_args[1][1] == "12345"  # demarche_number
        assert (
            call_args[1][2] == "https://grist.numerique.gouv.fr/api"
        )  # grist_base_url
        assert call_args[1][3] == ""  # grist_api_key vide (pas chiffré)

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_save_config_update_without_tokens(self, mock_db_manager):
        """Test update avec tokens vides → garder l'existant"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock : config existe avec tokens existants
        mock_cursor.fetchone.return_value = [
            "existing_encrypted_token",
            "existing_encrypted_key",
        ]

        # Mock des méthodes de chiffrement
        with patch.object(
            ConfigManager,
            "encrypt_value",
            side_effect=lambda x: f"encrypted_{x}" if x else x,
        ):
            config_manager = ConfigManager("dummy_url")
            result = config_manager.save_config(
                {
                    "otp_config_id": 1,
                    "ds_api_token": "",  # vide → garder l'existant
                    "demarche_number": "12345",
                    "grist_base_url": "https://test.grist.com",
                    "grist_api_key": "",  # vide → garder l'existant
                    "grist_doc_id": "test_doc",
                    "grist_user_id": "test_user",
                    "filter_date_start": "2023-01-01",
                    "filter_date_end": "2023-12-31",
                    "filter_statuses": "status1,status2",
                    "filter_groups": "group1,group2",
                }
            )

        assert result is True

        # Vérifier que UPDATE a été appelé avec les tokens existants
        update_call = mock_cursor.execute.call_args_list[1]
        assert "UPDATE otp_configurations SET" in update_call[0][0]
        call_args = update_call[0][1]
        assert call_args[0] == "existing_encrypted_token"  # token existant gardé
        assert call_args[3] == "existing_encrypted_key"  # key existante gardée

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_save_config_nonexistent_id(self, mock_db_manager):
        """Test update avec otp_config_id inexistant → False"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock : config n'existe pas (None)
        mock_cursor.fetchone.return_value = None

        config_manager = ConfigManager("dummy_url")
        result = config_manager.save_config(
            {
                "otp_config_id": 999,  # ID inexistant
                "ds_api_token": "test_token",
                "demarche_number": "12345",
                "grist_base_url": "https://test.grist.com",
                "grist_api_key": "test_key",
                "grist_doc_id": "test_doc",
                "grist_user_id": "test_user",
            }
        )

        assert result is False


class TestConfigNormalization:
    """Tests TDD pour la normalisation centralisée des types (étape 1 : échoue)"""

    @patch("configuration.config_manager.DatabaseManager")
    @patch.dict(
        os.environ, {"ENCRYPTION_KEY": "test_key_12345678901234567890123456789012"}
    )
    def test_save_config_normalizes_all_fields(self, mock_db_manager):
        """
        BUG: save_config normalise partiellement — demarche_number, grist_doc_id
        passent en int (JSON) sans conversion str pour SQL.
        Un seul test vérifie tous les paramètres.
        """
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        with patch.object(
            ConfigManager,
            "encrypt_value",
            side_effect=lambda x: f"encrypted_{x}" if x else x,
        ):
            config_manager = ConfigManager("dummy_url")
            result = config_manager.save_config(
                {
                    "ds_api_token": "test_token",
                    "demarche_number": 12345,
                    "grist_base_url": "https://test.grist.com",
                    "grist_api_key": "test_key",
                    "grist_doc_id": 67890,
                    "grist_user_id": 999,
                    "filter_date_start": 20230101,
                    "filter_date_end": 20231231,
                    "filter_statuses": 1,
                    "filter_groups": 2,
                }
            )

        assert result is True
        insert_call = mock_cursor.execute.call_args_list[0]

        insert_columns = [
            "ds_api_token",
            "demarche_number",
            "grist_base_url",
            "grist_api_key",
            "grist_doc_id",
            "grist_user_id",
            "filter_date_start",
            "filter_date_end",
            "filter_statuses",
            "filter_groups",
        ]
        params = dict(zip(insert_columns, insert_call[0][1]))

        assert isinstance(params["demarche_number"], str)
        assert params["demarche_number"] == "12345"
        assert isinstance(params["grist_doc_id"], str)
        assert params["grist_doc_id"] == "67890"
        assert isinstance(params["grist_user_id"], str)
        assert params["grist_user_id"] == "999"
        assert isinstance(params["filter_date_start"], str)
        assert params["filter_date_start"] == "20230101"
        assert isinstance(params["filter_date_end"], str)
        assert params["filter_date_end"] == "20231231"
        assert isinstance(params["filter_statuses"], str)
        assert params["filter_statuses"] == "1"
        assert isinstance(params["filter_groups"], str)
        assert params["filter_groups"] == "2"
