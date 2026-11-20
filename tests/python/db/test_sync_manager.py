from datetime import datetime, timezone
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from database.models import OtpConfiguration, SyncLog
from sync.sync_manager import SyncManager


def _process(stdout: str) -> MagicMock:
    """Sous-processus de synchro factice, terminé avec succès."""
    process = MagicMock()
    process.returncode = 0
    process.stdout = StringIO(stdout)
    process.stderr = StringIO("")
    return process


def _sync_log_values_line(modified: str | None, deleted: str | None) -> str:
    modified_json = f'"{modified}"' if modified else "null"
    deleted_json = f'"{deleted}"' if deleted else "null"
    return (
        'SYNC_LOG_VALUES: {"duration_seconds": 1.0, '
        f'"modified_dossiers_since": {modified_json}, '
        f'"deleted_dossiers_since": {deleted_json}}}\n'
    )


@pytest.fixture
def otp_config_id(db_session) -> int:
    otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
    db_session.add(otp_config)
    db_session.commit()
    return otp_config.id


class TestIncrementalSyncDates:
    """Dates de la synchro incrémentale enregistrées dans sync_logs réelle et
    transmises au sous-processus de la synchronisation suivante."""

    def _sync(self, otp_config_id: int, stdout: str, demarche_number="12345"):
        """Lance une synchro ; renvoie l'environnement reçu par le sous-processus."""
        config = {
            "ds_api_token": "jeton",
            "demarche_number": demarche_number,
            "grist_api_key": "cle",
            "grist_doc_id": "docA",
            "grist_user_id": "userA",
            "otp_config_id": otp_config_id,
        }
        with (
            patch("sync.sync_manager.grist_doc_access_level", return_value="owners"),
            patch("sync.sync_manager.ConfigManager"),
            patch("subprocess.Popen", return_value=_process(stdout)) as popen,
        ):
            SyncManager().run_synchronization_task(
                config, progress_callback=lambda *_: None
            )

        return popen.call_args.kwargs["env"]

    def test_first_sync_is_full_and_records_dates(self, otp_config_id, db_session):
        env = self._sync(
            otp_config_id,
            _sync_log_values_line("2024-02-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )

        assert env["MODIFIED_DOSSIERS_SINCE"] == ""
        sync_log = (
            db_session.query(SyncLog).filter_by(otp_config_id=otp_config_id).one()
        )
        assert sync_log.force_full_sync is True
        assert sync_log.modified_dossiers_since == datetime(
            2024, 2, 1, tzinfo=timezone.utc
        )
        assert sync_log.deleted_dossiers_since == datetime(
            2024, 1, 1, tzinfo=timezone.utc
        )

    def test_next_sync_resumes_from_recorded_dates(self, otp_config_id):
        self._sync(
            otp_config_id,
            _sync_log_values_line("2024-02-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )

        env = self._sync(otp_config_id, "Terminé\n")

        assert env["MODIFIED_DOSSIERS_SINCE"] == "2024-02-01T00:00:00Z"
        assert env["DELETED_DOSSIERS_SINCE"] == "2024-01-01T00:00:00Z"

    def test_sync_without_dates_is_skipped(self, otp_config_id):
        """Une synchro qui n'a pas émis de dates (sous-processus en échec) ne
        fait pas perdre celles de la précédente."""
        self._sync(otp_config_id, _sync_log_values_line("2024-02-01T00:00:00Z", None))
        self._sync(otp_config_id, "Terminé\n")

        env = self._sync(otp_config_id, "Terminé\n")

        assert env["MODIFIED_DOSSIERS_SINCE"] == "2024-02-01T00:00:00Z"
        assert env["DELETED_DOSSIERS_SINCE"] == ""

    def test_latest_dates_win(self, otp_config_id):
        self._sync(otp_config_id, _sync_log_values_line("2024-02-01T00:00:00Z", None))
        self._sync(otp_config_id, _sync_log_values_line("2024-03-01T00:00:00Z", None))

        env = self._sync(otp_config_id, "Terminé\n")

        assert env["MODIFIED_DOSSIERS_SINCE"] == "2024-03-01T00:00:00Z"

    def test_changed_demarche_is_full_sync(self, otp_config_id):
        self._sync(otp_config_id, _sync_log_values_line("2024-02-01T00:00:00Z", None))

        env = self._sync(otp_config_id, "Terminé\n", demarche_number="67890")

        assert env["MODIFIED_DOSSIERS_SINCE"] == ""

    def test_dates_of_other_configuration_ignored(self, otp_config_id, db_session):
        other = OtpConfiguration(grist_user_id="userB", grist_doc_id="docB")
        db_session.add(other)
        db_session.commit()
        self._sync(other.id, _sync_log_values_line("2024-02-01T00:00:00Z", None))

        env = self._sync(otp_config_id, "Terminé\n")

        assert env["MODIFIED_DOSSIERS_SINCE"] == ""
