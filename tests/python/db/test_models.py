import pytest
from sqlalchemy import inspect

from database.models import Base, OtpConfiguration, SyncLog


class TestModelsMatchSchema:
    """
    Les modèles ORM décrivent le schéma créé en SQL brut par DatabaseManager :
    les deux sont maintenus à la main et peuvent diverger.
    """

    @pytest.mark.parametrize("table", Base.metadata.sorted_tables, ids=str)
    def test_same_columns(self, initialized_database, table):
        inspector = inspect(initialized_database)
        db_columns = {column["name"] for column in inspector.get_columns(table.name)}

        assert db_columns == set(table.columns.keys())

    @pytest.mark.parametrize("table", Base.metadata.sorted_tables, ids=str)
    def test_same_python_types(self, initialized_database, table):
        inspector = inspect(initialized_database)
        db_types = {
            column["name"]: column["type"].python_type
            for column in inspector.get_columns(table.name)
        }
        model_types = {
            column.name: column.type.python_type for column in table.columns
        }

        assert db_types == model_types


class TestModelsPersistence:
    """Écriture et relecture par l'ORM, comme le font les routes de app.py"""

    def test_sync_log_round_trip_with_defaults(self, db_session):
        otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
        db_session.add(otp_config)
        db_session.flush()
        otp_config_id = otp_config.id
        db_session.add(
            SyncLog(otp_config_id=otp_config_id, status="success", success_count=3)
        )
        db_session.commit()
        db_session.expunge_all()

        sync_log = db_session.query(SyncLog).filter_by(otp_config_id=otp_config_id).one()

        assert sync_log.status == "success"
        assert sync_log.success_count == 3
        assert sync_log.auto is True
        assert sync_log.timestamp is not None

    def test_deleting_configuration_keeps_sync_logs(self, db_session):
        otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
        db_session.add(otp_config)
        db_session.flush()
        db_session.add(SyncLog(otp_config_id=otp_config.id, status="success"))
        db_session.commit()

        db_session.delete(otp_config)
        db_session.commit()
        db_session.expunge_all()

        sync_log = db_session.query(SyncLog).one()

        assert sync_log.otp_config_id is None
