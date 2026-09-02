from datetime import datetime, timezone

import pytest

from unittest.mock import MagicMock, patch
from database.models import UserSchedule, OtpConfiguration
from sync import scheduled_sync


def _utc(year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)

def _make_session_mock():
    """Crée un mock de session SQLAlchemy où filter_by().first() retourne un mock dédié."""
    mock_db = MagicMock()
    mock_session_class = MagicMock(return_value=mock_db)
    return mock_db, mock_session_class


class TestScheduledSyncJob:
    """Tests pour scheduled_sync_job"""

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager")
    def test_success(self, mock_cm, mock_sessionmaker, mock_create_engine):
        """Synchro réussie : last_status='success', next_run calculé"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_config_otp = MagicMock()
        mock_config_otp.id = 1
        mock_user_schedule = MagicMock()
        mock_user_schedule.otp_config_id = 1

        def filter_by_side_effect(**kwargs):
            mock_q = MagicMock()
            if "id" in kwargs and kwargs["id"] == 1 and "otp_config_id" not in kwargs:
                mock_q.first.return_value = mock_config_otp
            elif "otp_config_id" in kwargs:
                mock_q.first.return_value = mock_user_schedule
            else:
                mock_q.first.return_value = None
            return mock_q

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        mock_cm.load_config_by_id.return_value = {
            "otp_config_id": 1,
            "demarche_number": "123",
            "grist_doc_id": "doc456",
            "grist_user_id": "user123",
        }

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            mock_sync.return_value = {"success": True}

            scheduled_sync_job(1, sync_manager)

            mock_sync.assert_called_once_with(
                mock_cm.load_config_by_id.return_value, auto=True
            )
            assert mock_user_schedule.last_status == "success"
            assert mock_user_schedule.last_run is not None

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager")
    def test_sync_failure_keeps_schedule_enabled(
        self, mock_cm, mock_sessionmaker, mock_create_engine
    ):
        """Échec sync (success=False) : schedule reste activé"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_config_otp = MagicMock()
        mock_config_otp.id = 1
        mock_user_schedule = MagicMock()
        mock_user_schedule.otp_config_id = 1

        def filter_by_side_effect(**kwargs):
            mock_q = MagicMock()
            if "id" in kwargs and "otp_config_id" not in kwargs:
                mock_q.first.return_value = mock_config_otp
            elif "otp_config_id" in kwargs:
                mock_q.first.return_value = mock_user_schedule
            else:
                mock_q.first.return_value = None
            return mock_q

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        mock_cm.load_config_by_id.return_value = {"otp_config_id": 1}

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            mock_sync.return_value = {"success": False, "message": "Sync failed"}

            scheduled_sync_job(1, sync_manager)

            assert mock_user_schedule.last_status == "error"
            assert mock_user_schedule.enabled is not False

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager")
    def test_api_error_disables_schedule(
        self, mock_cm, mock_sessionmaker, mock_create_engine
    ):
        """Erreur API (EXIT_CODE_EXTERNAL_API_ERROR) : schedule désactivé"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager
        from utils.constants import EXIT_CODE_EXTERNAL_API_ERROR

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_config_otp = MagicMock()
        mock_config_otp.id = 1
        mock_user_schedule = MagicMock()
        mock_user_schedule.otp_config_id = 1

        def filter_by_side_effect(**kwargs):
            mock_q = MagicMock()
            if "id" in kwargs and "otp_config_id" not in kwargs:
                mock_q.first.return_value = mock_config_otp
            elif "otp_config_id" in kwargs:
                mock_q.first.return_value = mock_user_schedule
            else:
                mock_q.first.return_value = None
            return mock_q

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        mock_cm.load_config_by_id.return_value = {"otp_config_id": 1}

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            mock_sync.return_value = {
                "success": False,
                "error_code": EXIT_CODE_EXTERNAL_API_ERROR,
                "message": "API error",
            }

            scheduled_sync_job(1, sync_manager)

            assert mock_user_schedule.enabled is False

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager")
    def test_unexpected_exception_disables_schedule(
        self, mock_cm, mock_sessionmaker, mock_create_engine
    ):
        """Exception inattendue : schedule désactivé"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_config_otp = MagicMock()
        mock_config_otp.id = 1
        mock_user_schedule = MagicMock()
        mock_user_schedule.otp_config_id = 1

        def filter_by_side_effect(**kwargs):
            mock_q = MagicMock()
            if "id" in kwargs and "otp_config_id" not in kwargs:
                mock_q.first.return_value = mock_config_otp
            elif "otp_config_id" in kwargs:
                mock_q.first.return_value = mock_user_schedule
            else:
                mock_q.first.return_value = None
            return mock_q

        mock_db.query.return_value.filter_by.side_effect = filter_by_side_effect

        mock_cm.load_config_by_id.return_value = {"otp_config_id": 1}

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            mock_sync.side_effect = RuntimeError("Unexpected")

            scheduled_sync_job(1, sync_manager)

            assert mock_user_schedule.enabled is False

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    @patch("sync.scheduled_sync.config_manager")
    def test_config_not_found(
        self, mock_cm, mock_sessionmaker, mock_create_engine
    ):
        """Config introuvable : retourne sans crash sans appeler la sync"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_db.query.return_value.filter_by.return_value.first.return_value = None

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            scheduled_sync_job(999, sync_manager)

            mock_sync.assert_not_called()


class TestReloadSchedulerJobs:
    """Tests pour reload_scheduler_jobs"""

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    def test_zero_active_schedules(self, mock_sessionmaker, mock_create_engine):
        """0 schedules actifs : 0 jobs ajoutés"""
        from sync.scheduled_sync import reload_scheduler_jobs
        from sync.sync_manager import SyncManager

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_db.query.return_value.filter_by.return_value.filter.return_value.all.return_value = (
            []
        )

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        mock_scheduler = MagicMock()

        with patch("sync.scheduled_sync.scheduler", mock_scheduler):
            reload_scheduler_jobs(sync_manager)

            mock_scheduler.remove_all_jobs.assert_called_once()
            mock_scheduler.add_job.assert_not_called()

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    def test_two_schedules_five_min_offset(
        self, mock_sessionmaker, mock_create_engine
    ):
        """2 schedules actifs : 2 jobs avec offset de 5 min"""
        from sync.scheduled_sync import (
            reload_scheduler_jobs,
            SYNC_MINUTE,
        )
        from sync.sync_manager import SyncManager

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_schedule1 = MagicMock()
        mock_schedule1.otp_config_id = 1
        mock_schedule1.enabled = True

        mock_schedule2 = MagicMock()
        mock_schedule2.otp_config_id = 2
        mock_schedule2.enabled = True

        mock_config1 = MagicMock()
        mock_config1.demarche_number = "100"
        mock_config1.grist_doc_id = "doc_a"

        mock_config2 = MagicMock()
        mock_config2.demarche_number = "200"
        mock_config2.grist_doc_id = "doc_b"

        # Mock query pour UserSchedule
        mock_schedule_query = MagicMock()
        mock_schedule_query.filter_by.return_value.filter.return_value.all.return_value = [
            mock_schedule1,
            mock_schedule2,
        ]

        # Mock queries pour OtpConfiguration (un par config_id)
        mock_config_q1 = MagicMock()
        mock_config_q1.filter_by.return_value.first.return_value = mock_config1
        mock_config_q2 = MagicMock()
        mock_config_q2.filter_by.return_value.first.return_value = mock_config2
        config_queries = [mock_config_q1, mock_config_q2]
        config_idx = {"i": 0}

        def query_side_effect(model):
            if model is UserSchedule:
                return mock_schedule_query
            elif model is OtpConfiguration:
                idx = config_idx["i"]
                config_idx["i"] += 1
                return config_queries[idx]
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        mock_scheduler = MagicMock()

        with patch("sync.scheduled_sync.scheduler", mock_scheduler):
            reload_scheduler_jobs(sync_manager)

            assert mock_scheduler.add_job.call_count == 2

            trigger_1 = mock_scheduler.add_job.call_args_list[0][1]["trigger"]
            trigger_2 = mock_scheduler.add_job.call_args_list[1][1]["trigger"]

            assert f"minute='{SYNC_MINUTE}'" in str(trigger_1)
            assert f"minute='{SYNC_MINUTE + 5}'" in str(trigger_2)

    @patch("sync.scheduled_sync.create_engine")
    @patch("sync.scheduled_sync.sessionmaker")
    def test_missing_config_skips_schedule(
        self, mock_sessionmaker, mock_create_engine
    ):
        """Config manquante pour un schedule : skip, les autres sont ajoutés"""
        from sync.scheduled_sync import reload_scheduler_jobs
        from sync.sync_manager import SyncManager

        mock_db, mock_session_class = _make_session_mock()
        mock_sessionmaker.return_value = mock_session_class

        mock_schedule1 = MagicMock()
        mock_schedule1.otp_config_id = 1
        mock_schedule1.enabled = True

        mock_schedule2 = MagicMock()
        mock_schedule2.otp_config_id = 2
        mock_schedule2.enabled = True

        mock_config1 = MagicMock()
        mock_config1.demarche_number = "100"
        mock_config1.grist_doc_id = "doc_a"

        mock_schedule_query = MagicMock()
        mock_schedule_query.filter_by.return_value.filter.return_value.all.return_value = [
            mock_schedule1,
            mock_schedule2,
        ]

        mock_config_q1 = MagicMock()
        mock_config_q1.filter_by.return_value.first.return_value = mock_config1
        mock_config_q2 = MagicMock()
        mock_config_q2.filter_by.return_value.first.return_value = None
        config_queries = [mock_config_q1, mock_config_q2]
        config_idx = {"i": 0}

        def query_side_effect(model):
            if model is UserSchedule:
                return mock_schedule_query
            elif model is OtpConfiguration:
                idx = config_idx["i"]
                config_idx["i"] += 1
                return config_queries[idx]
            return MagicMock()

        mock_db.query.side_effect = query_side_effect

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        mock_scheduler = MagicMock()

        with patch("sync.scheduled_sync.scheduler", mock_scheduler):
            reload_scheduler_jobs(sync_manager)

            assert mock_scheduler.add_job.call_count == 1
            assert mock_scheduler.add_job.call_args_list[0][1]["id"] == "scheduled_sync_1"

class TestComputeNextRun:
    """Calcul de la prochaine exécution planifiée dans SYNC_TZ."""

    @pytest.fixture(autouse=True)
    def _config(self, monkeypatch):
        monkeypatch.setattr(scheduled_sync, "SYNC_HOUR", 11)
        monkeypatch.setattr(scheduled_sync, "SYNC_MINUTE", 14)
        monkeypatch.setattr(scheduled_sync, "SYNC_TZ", "Europe/Paris")

    def test_next_run_in_configured_timezone(self):
        """11h14 Paris = 09h14 UTC. Avant l'échéance -> aujourd'hui."""
        now = _utc(2026, 9, 2, 8, 0)  # 10h00 Paris
        expected = _utc(2026, 9, 2, 9, 14)  # 11h14 Paris
        assert scheduled_sync.compute_next_run(now) == expected

    def test_next_run_when_past_rolls_to_next_day(self):
        """Déjà passé aujourd'hui -> lendemain (heure Paris conservée)."""
        now = _utc(2026, 9, 2, 10, 0)  # 12h00 Paris, après 11h14
        expected = _utc(2026, 9, 3, 9, 14)  # 11h14 Paris le lendemain
        assert scheduled_sync.compute_next_run(now) == expected

    def test_next_run_exact_moment_rolls_to_next_day(self):
        """À l'échéance exacte -> considéré passé -> lendemain."""
        now = _utc(2026, 9, 2, 9, 14)  # exactement 11h14 Paris
        expected = _utc(2026, 9, 3, 9, 14)
        assert scheduled_sync.compute_next_run(now) == expected

    def test_next_run_with_naive_datetime_treated_as_utc(self):
        """Un datetime naïf est interprété comme UTC puis converti."""
        now = datetime(2026, 9, 2, 8, 0)
        expected = _utc(2026, 9, 2, 9, 14)
        assert scheduled_sync.compute_next_run(now) == expected
