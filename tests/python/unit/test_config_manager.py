import pytest
import os
from unittest.mock import patch, MagicMock
from configuration.config_manager import ConfigManager


class TestConfigManager:
    """Tests unitaires pour la classe ConfigManager"""

    @patch('configuration.config_manager.Fernet')
    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key'})
    def test_encrypt_decrypt_value(self, mock_fernet):
        """Test du chiffrement et déchiffrement d'une valeur"""
        # Mock Fernet
        mock_fernet_instance = MagicMock()
        mock_fernet_instance.encrypt.return_value = b'encrypted_data'
        mock_fernet_instance.decrypt.return_value = b'test_sensitive_data'
        mock_fernet.return_value = mock_fernet_instance

        original_value = "test_sensitive_data"

        # Chiffrement
        encrypted = ConfigManager.encrypt_value(original_value)
        assert encrypted == 'encrypted_data'

        # Déchiffrement
        decrypted = ConfigManager.decrypt_value(encrypted)
        assert decrypted == 'test_sensitive_data'

        # Vérifier que Fernet a été appelé correctement
        mock_fernet.assert_called_with(b'test_key')

    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key_12345678901234567890123456789012'})
    def test_encrypt_empty_value(self):
        """Test du chiffrement d'une valeur vide"""
        encrypted = ConfigManager.encrypt_value("")
        assert encrypted == ""

        encrypted = ConfigManager.encrypt_value(None)
        assert encrypted is None

    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key_12345678901234567890123456789012'})
    def test_decrypt_empty_value(self):
        """Test du déchiffrement d'une valeur vide"""
        decrypted = ConfigManager.decrypt_value("")
        assert decrypted == ""

        decrypted = ConfigManager.decrypt_value(None)
        assert decrypted is None

    @patch.dict(os.environ, {'ENCRYPTION_KEY': ''})
    def test_get_encryption_key_missing(self):
        """Test d'erreur quand la clé de chiffrement est manquante"""
        with pytest.raises(ValueError, match='"ENCRYPTION_KEY" non définie'):
            ConfigManager.get_encryption_key()

    @patch('configuration.config_manager.DatabaseManager')
    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key_12345678901234567890123456789012'})
    def test_load_config_existing(self, mock_db_manager):
        """Test du chargement d'une configuration existante"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock des données retournées par la DB
        mock_cursor.fetchone.return_value = (
            'encrypted_token',  # ds_api_token
            '12345',           # demarche_number
            'https://test.grist.com',  # grist_base_url
            'encrypted_key',   # grist_api_key
            'test_doc',        # grist_doc_id
            'test_user'        # grist_user_id
        )

        # Mock des méthodes de déchiffrement
        with patch.object(ConfigManager, 'decrypt_value', side_effect=lambda x: f"decrypted_{x}"):
            config = ConfigManager.load_config('test_user', 'test_doc')

        # Vérifications
        assert config['ds_api_token'] == 'decrypted_encrypted_token'
        assert config['demarche_number'] == '12345'
        assert config['grist_base_url'] == 'https://test.grist.com'
        assert config['grist_api_key'] == 'decrypted_encrypted_key'
        assert config['grist_doc_id'] == 'test_doc'
        assert config['grist_user_id'] == 'test_user'

        # Vérifier que la requête SQL a été appelée correctement
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert 'SELECT ds_api_token' in call_args[0]
        assert call_args[1] == ('test_user', 'test_doc')

    @patch('configuration.config_manager.DatabaseManager')
    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key_12345678901234567890123456789012'})
    def test_load_config_not_found(self, mock_db_manager):
        """Test du chargement quand aucune configuration n'existe"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock : aucune ligne trouvée
        mock_cursor.fetchone.return_value = None

        config = ConfigManager.load_config('test_user', 'test_doc')

        # Vérifications des valeurs par défaut
        assert config['ds_api_token'] == ''
        assert config['demarche_number'] == ''
        assert config['grist_base_url'] == 'https://grist.numerique.gouv.fr/api'
        assert config['grist_api_key'] == ''
        assert config['grist_doc_id'] == ''
        assert config['grist_user_id'] == ''

    @patch('configuration.config_manager.DatabaseManager')
    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key_12345678901234567890123456789012'})
    def test_load_config_invalid_params(self, mock_db_manager):
        """Test d'erreur avec des paramètres invalides"""
        with pytest.raises(Exception, match="No grist user id or doc id"):
            ConfigManager.load_config('', '')

        with pytest.raises(Exception, match="No grist user id or doc id"):
            ConfigManager.load_config(None, 'test_doc')

    @patch('configuration.config_manager.DatabaseManager')
    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key_12345678901234567890123456789012'})
    def test_save_config_update_existing(self, mock_db_manager):
        """Test de la sauvegarde (mise à jour d'une config existante)"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock : configuration existe déjà
        mock_cursor.fetchone.return_value = [1]  # COUNT(*) = 1

        # Mock des méthodes de chiffrement
        with patch.object(ConfigManager, 'encrypt_value', side_effect=lambda x: f"encrypted_{x}"):
            result = ConfigManager.save_config({
                'ds_api_token': 'test_token',
                'demarche_number': '12345',
                'grist_base_url': 'https://test.grist.com',
                'grist_api_key': 'test_key',
                'grist_doc_id': 'test_doc',
                'grist_user_id': 'test_user'
            })

        assert result is True

        # Vérifier que UPDATE a été appelé
        assert mock_cursor.execute.call_count == 2  # SELECT COUNT + UPDATE
        update_call = mock_cursor.execute.call_args_list[1]
        assert 'UPDATE otp_configurations SET' in update_call[0][0]

    @patch('configuration.config_manager.DatabaseManager')
    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key_12345678901234567890123456789012'})
    def test_save_config_insert_new(self, mock_db_manager):
        """Test de la sauvegarde (insertion d'une nouvelle config)"""
        # Mock de la connexion DB
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_db_manager.get_connection.return_value = mock_conn

        # Mock : configuration n'existe pas
        mock_cursor.fetchone.return_value = [0]  # COUNT(*) = 0

        # Mock des méthodes de chiffrement
        with patch.object(ConfigManager, 'encrypt_value', side_effect=lambda x: f"encrypted_{x}"):
            result = ConfigManager.save_config({
                'ds_api_token': 'test_token',
                'demarche_number': '12345',
                'grist_base_url': 'https://test.grist.com',
                'grist_api_key': 'test_key',
                'grist_doc_id': 'test_doc',
                'grist_user_id': 'test_user'
            })

        assert result is True

        # Vérifier que INSERT a été appelé
        assert mock_cursor.execute.call_count == 2  # SELECT COUNT + INSERT
        insert_call = mock_cursor.execute.call_args_list[1]
        assert 'INSERT INTO otp_configurations' in insert_call[0][0]

    @patch('configuration.config_manager.DatabaseManager')
    @patch.dict(os.environ, {'ENCRYPTION_KEY': 'test_key'})
    def test_save_config_invalid_params(self, mock_db_manager):
        """Test d'erreur de sauvegarde avec paramètres invalides"""
        # La méthode retourne False au lieu de lever une exception
        result = ConfigManager.save_config({
            'grist_user_id': '',
            'grist_doc_id': 'test_doc'
        })
        assert result is False



    def test_sensitive_keys_constant(self):
        """Test de la constante SENSITIVE_KEYS"""
        assert 'ds_api_token' in ConfigManager.SENSITIVE_KEYS
        assert 'grist_api_key' in ConfigManager.SENSITIVE_KEYS
        assert len(ConfigManager.SENSITIVE_KEYS) == 2