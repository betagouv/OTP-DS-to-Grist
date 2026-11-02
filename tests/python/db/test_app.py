import json
from datetime import datetime, timezone

import pytest
from flask import g

from database.models import OtpConfiguration, SyncLog


@pytest.fixture
def app_module():
    """
    Application, importée au moment du test (et non à la collecte) : elle
    initialise alors le schéma sur la base de test.
    """
    import app

    return app


def _add_config(db_session) -> int:
    otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
    db_session.add(otp_config)
    db_session.flush()
    return otp_config.id


class TestApiSyncLogLatestByDemarche:
    """GET /api/sync-log/latest-by-demarche : requête sur la table sync_logs réelle"""

    def _latest_syncs(self, app_module, monkeypatch, otp_config_ids):
        monkeypatch.setattr(
            app_module.config_manager,
            "load_config",
            lambda grist_user_id, grist_doc_id: [
                {"otp_config_id": otp_config_id, "demarche_number": str(otp_config_id)}
                for otp_config_id in otp_config_ids
            ],
        )
        with app_module.app.test_request_context("/api/sync-log/latest-by-demarche"):
            g.widget_identity = {"userId": "userA", "docId": "docA"}
            response = app_module.api_sync_log_latest_by_demarche()

        return {
            sync["otp_config_id"]: sync for sync in json.loads(response.data)["syncs"]
        }

    def test_returns_the_latest_sync_of_each_config(
        self, app_module, monkeypatch, db_session
    ):
        first_id = _add_config(db_session)
        second_id = _add_config(db_session)
        db_session.add_all(
            [
                SyncLog(otp_config_id=first_id, status="error", auto=True),
                SyncLog(
                    otp_config_id=first_id,
                    status="success",
                    auto=False,
                    success_count=14,
                    error_count=0,
                    message="Synchronisation terminée",
                    timestamp=datetime(2026, 11, 2, 13, 41, tzinfo=timezone.utc),
                ),
                SyncLog(otp_config_id=second_id, status="error", auto=True),
            ]
        )
        db_session.commit()

        latest = self._latest_syncs(app_module, monkeypatch, [first_id, second_id])

        assert latest[first_id] == {
            "otp_config_id": first_id,
            "demarche_number": str(first_id),
            "timestamp": "2026-11-02T14:41:00",
            "status": "success",
            "success_count": 14,
            "error_count": 0,
            "message": "Synchronisation terminée",
            "auto": False,
        }
        assert latest[second_id]["status"] == "error"
        assert latest[second_id]["auto"] is True

    def test_ignores_configs_never_synced_or_of_others(
        self, app_module, monkeypatch, db_session
    ):
        synced_id = _add_config(db_session)
        never_synced_id = _add_config(db_session)
        other_id = _add_config(db_session)
        db_session.add_all(
            [
                SyncLog(otp_config_id=synced_id, status="success"),
                SyncLog(otp_config_id=other_id, status="success"),
            ]
        )
        db_session.commit()

        latest = self._latest_syncs(
            app_module, monkeypatch, [synced_id, never_synced_id]
        )

        assert set(latest) == {synced_id}

    def test_returns_nothing_without_saved_config(
        self, app_module, monkeypatch, db_session
    ):
        assert self._latest_syncs(app_module, monkeypatch, []) == {}
