from database.models import OtpConfiguration, SyncLog
from tests.python.db.schema_helpers import assert_database_matches_models


class TestModelsMatchDatabase:
    """Les modèles ORM décrivent fidèlement la base créée par les migrations"""

    def test_autogenerate_detects_no_difference(self, initialized_database):
        assert_database_matches_models(initialized_database)


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

    def test_sync_log_round_trip_errors(self, db_session):
        """Les erreurs d'une synchro sont relues telles qu'enregistrées, dans l'ordre"""
        errors = {
            "dossiers": [
                {
                    "dossier": "7",
                    "timestamp": "2026-11-16T23:05:27.412Z",
                    "message": "Erreur 400 : « é »",
                }
            ],
            "dossiers_total": 11,
            "general": [
                {"timestamp": "2026-11-16T23:05:27.630Z", "message": "Labels"},
                {"timestamp": "2026-11-16T23:05:27.700Z", "message": "Suppressions"},
            ],
        }
        db_session.add(SyncLog(status="error", errors=errors))
        db_session.add(SyncLog(status="success"))
        db_session.commit()
        db_session.expunge_all()

        failed, succeeded = db_session.query(SyncLog).order_by(SyncLog.id).all()

        assert failed.errors == errors
        assert succeeded.errors is None
