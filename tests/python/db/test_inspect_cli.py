import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from database.models import IpBlocklist, OtpConfigIp, OtpConfiguration, SyncLog
from tools import inspect_cli

IP = "203.0.113.7"

PARIS = ZoneInfo("Europe/Paris")


@pytest.fixture(autouse=True)
def paris_local_time(monkeypatch):
    """Heure locale de l'exploitant : Paris, quel que soit le poste de test."""
    monkeypatch.setenv("TZ", "Europe/Paris")
    time.tzset()

    yield

    monkeypatch.undo()
    time.tzset()


@pytest.fixture
def otp_config_id(db_session) -> int:
    otp_config = OtpConfiguration(grist_user_id="userA", grist_doc_id="docA")
    db_session.add(otp_config)
    db_session.commit()

    return otp_config.id


def _report(capsys, *argv: str) -> str:
    assert inspect_cli.main(list(argv)) == 0

    return capsys.readouterr().out


def _paris(moment: datetime) -> str:
    return moment.astimezone(PARIS).strftime("%d/%m %H:%M")


class TestSyncLogs:
    """Synchros des dernières 24 h, datées à l'heure locale"""

    def test_lists_recent_syncs_at_local_time(self, capsys, db_session, otp_config_id):
        recent = datetime.now(timezone.utc) - timedelta(minutes=10)
        db_session.add(
            SyncLog(otp_config_id=otp_config_id, message="récente", timestamp=recent)
        )
        db_session.commit()

        report = _report(capsys, "--config", str(otp_config_id))

        assert _paris(recent) in report
        assert "récente" in report

    def test_ignores_syncs_older_than_period(self, capsys, db_session, otp_config_id):
        db_session.add_all(
            [
                SyncLog(
                    otp_config_id=otp_config_id,
                    message="juste dans la période",
                    timestamp=datetime.now(timezone.utc) - timedelta(hours=23),
                ),
                SyncLog(
                    otp_config_id=otp_config_id,
                    message="hors période",
                    timestamp=datetime.now(timezone.utc) - timedelta(hours=25),
                ),
            ]
        )
        db_session.commit()

        report = _report(capsys, "--config", str(otp_config_id))

        assert "juste dans la période" in report
        assert "hors période" not in report


class TestBanStatus:
    """État de blocage d'une IP, fin de ban à l'heure locale"""

    def test_active_ban(self, capsys, db_session):
        banned_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        db_session.add(IpBlocklist(ip=IP, ban_count=1, banned_until=banned_until))
        db_session.commit()

        report = _report(capsys, "--ip", IP)

        assert f"bannie jusqu'au {_paris(banned_until)} (1 bannissement(s))" in report

    def test_finished_ban(self, capsys, db_session):
        banned_until = datetime.now(timezone.utc) - timedelta(minutes=30)
        db_session.add(IpBlocklist(ip=IP, ban_count=2, banned_until=banned_until))
        db_session.commit()

        report = _report(capsys, "--ip", IP)

        assert (
            f"non bannie (2 bannissement(s), dernier terminé le {_paris(banned_until)})"
            in report
        )


class TestLastUse:
    """Dernière utilisation d'une configuration par une IP, à l'heure locale"""

    def test_last_use_at_local_time(self, capsys, db_session, otp_config_id):
        seen_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.add(OtpConfigIp(ip=IP, otp_config_id=otp_config_id, seen_at=seen_at))
        db_session.commit()

        report = _report(capsys, "--ip", IP)

        assert _paris(seen_at) in report
