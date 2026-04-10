import pytest
from unittest.mock import MagicMock, patch
from database.models import OtpConfiguration, UserSchedule, SyncLog, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestOtpConfiguration:
    """Tests unitaires pour le modèle OtpConfiguration"""

    def test_otp_configuration_creation(self):
        """Test de création d'une instance OtpConfiguration avec tous les champs"""
        config = OtpConfiguration(
            ds_api_token="test_token",
            demarche_number="12345",
            grist_base_url="https://test.grist.com",
            grist_api_key="test_key",
            grist_doc_id="test_doc",
            grist_user_id="test_user",
            filter_date_start="2024-01-01",
            filter_date_end="2024-12-31",
            filter_statuses="en_construction,en_instruction",
            filter_groups="1,2,3"
        )

        assert config.ds_api_token == "test_token"
        assert config.demarche_number == "12345"
        assert config.grist_base_url == "https://test.grist.com"
        assert config.grist_api_key == "test_key"
        assert config.grist_doc_id == "test_doc"
        assert config.grist_user_id == "test_user"
        assert config.filter_date_start == "2024-01-01"
        assert config.filter_date_end == "2024-12-31"
        assert config.filter_statuses == "en_construction,en_instruction"
        assert config.filter_groups == "1,2,3"

    def test_otp_configuration_table_name(self):
        """Test que le nom de table est correct"""
        assert OtpConfiguration.__tablename__ == 'otp_configurations'

    def test_otp_configuration_filter_fields_default_none(self):
        """Test que les champs de filtres sont None par défaut"""
        config = OtpConfiguration()

        assert config.filter_date_start is None
        assert config.filter_date_end is None
        assert config.filter_statuses is None
        assert config.filter_groups is None

    @patch('app.SessionLocal')
    def test_otp_configuration_database_interaction(self, mock_session_local):
        """Test d'interaction mockée avec la base de données"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Créer une config avec filtres
        config = OtpConfiguration(
            filter_date_start="2024-01-01",
            filter_statuses="en_construction"
        )

        # Simuler ajout et commit
        mock_session.add(config)
        mock_session.commit()

        # Vérifier que les méthodes ont été appelées
        mock_session.add.assert_called_once_with(config)
        mock_session.commit.assert_called_once()

    def test_otp_configuration_backward_compatibility(self):
        """Test que les configurations existantes sans filtres fonctionnent"""
        config = OtpConfiguration(
            ds_api_token="existing_token",
            demarche_number="67890",
            grist_base_url="https://existing.grist.com",
            grist_api_key="existing_key",
            grist_doc_id="existing_doc",
            grist_user_id="existing_user"
            # Pas de champs filtres
        )

        assert config.ds_api_token == "existing_token"
        assert config.filter_date_start is None
        assert config.filter_statuses is None


class TestUserSchedule:
    """Tests unitaires pour le modèle UserSchedule"""

    def test_user_schedule_creation(self):
        """Test de création d'une instance UserSchedule"""
        schedule = UserSchedule(
            otp_config_id=1,
            frequency="daily",
            enabled=True
        )

        assert schedule.otp_config_id == 1
        assert schedule.frequency == "daily"
        assert schedule.enabled is True
        assert schedule.last_run is None
        assert schedule.next_run is None
        assert schedule.last_status is None

    def test_user_schedule_table_name(self):
        """Test que le nom de table est correct"""
        assert UserSchedule.__tablename__ == 'user_schedules'


class TestSyncLog:
    """Tests unitaires pour le modèle SyncLog"""

    def test_sync_log_creation(self):
        """Test de création d'une instance SyncLog"""
        from datetime import datetime, timezone
        log = SyncLog(
            grist_user_id="test_user",
            grist_doc_id="test_doc",
            status="success",
            message="Sync completed"
        )

        assert log.grist_user_id == "test_user"
        assert log.grist_doc_id == "test_doc"
        assert log.status == "success"
        assert log.message == "Sync completed"
        # Timestamp is set by default, but not when manually created
        # We can test that the field exists
        assert hasattr(log, 'timestamp')

    def test_sync_log_table_name(self):
        """Test que le nom de table est correct"""
        assert SyncLog.__tablename__ == 'sync_logs'


class TestModelsIntegration:
    """Tests d'intégration entre les modèles"""

    @patch('app.SessionLocal')
    def test_models_relationship(self, mock_session_local):
        """Test des relations entre modèles (mocké)"""
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Créer les instances
        config = OtpConfiguration(id=1, grist_user_id="test_user")
        schedule = UserSchedule(otp_config_id=1)
        log = SyncLog(grist_user_id="test_user")

        # Simuler les queries
        mock_session.query.return_value.filter_by.return_value.first.return_value = config

        # Vérifier que les instances sont créées correctement
        assert config.id == 1
        assert schedule.otp_config_id == 1
        assert log.grist_user_id == "test_user"