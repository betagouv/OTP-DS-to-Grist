from datetime import datetime, timezone

import pytest

from database.models import OtpConfiguration, SyncLog
from sync.incremental import last_sync_with_dates

DATES = datetime(2024, 2, 1, tzinfo=timezone.utc)


@pytest.fixture
def otp_config_id(db_session) -> int:
    otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
    db_session.add(otp_config)
    db_session.commit()
    return otp_config.id


def _add_sync(db_session, otp_config_id: int, day: int, dates: datetime | None):
    """Enregistre une synchro du `day` février 2024, qui a laissé `dates`."""
    sync_log = SyncLog(
        otp_config_id=otp_config_id,
        timestamp=datetime(2024, 2, day, tzinfo=timezone.utc),
        modified_dossiers_since=dates,
    )
    db_session.add(sync_log)
    db_session.commit()
    return sync_log.id


class TestLastSyncWithDates:
    def test_no_sync(self, db_session, otp_config_id):
        assert last_sync_with_dates(db_session, otp_config_id) is None

    def test_syncs_without_dates_skipped(self, db_session, otp_config_id):
        """Une synchro dont le sous-processus a échoué ne laisse pas de date."""
        with_dates = _add_sync(db_session, otp_config_id, 1, DATES)
        _add_sync(db_session, otp_config_id, 2, None)

        assert last_sync_with_dates(db_session, otp_config_id).id == with_dates

    def test_only_syncs_without_dates(self, db_session, otp_config_id):
        _add_sync(db_session, otp_config_id, 1, None)

        assert last_sync_with_dates(db_session, otp_config_id) is None

    def test_latest_by_timestamp(self, db_session, otp_config_id):
        """La plus récente selon sa date, pas selon son ordre d'insertion."""
        latest = _add_sync(db_session, otp_config_id, 3, DATES)
        _add_sync(db_session, otp_config_id, 2, DATES)

        assert last_sync_with_dates(db_session, otp_config_id).id == latest

    def test_other_configuration_ignored(self, db_session, otp_config_id):
        other = OtpConfiguration(grist_user_id="userB", grist_doc_id="docB")
        db_session.add(other)
        db_session.commit()
        _add_sync(db_session, other.id, 1, DATES)

        assert last_sync_with_dates(db_session, otp_config_id) is None
