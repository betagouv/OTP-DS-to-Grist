from unittest.mock import MagicMock, patch

import pytest


def _inline_enqueue(otp_config_id, grist_doc_id, fn):
    """Enfilement synchrone pour les tests : exécute l'étape immédiatement."""
    fn()
    return f"fake_step_config_{otp_config_id}"


def _trigger_value(trigger, name):
    """Extrait la première valeur d'un champ de CronTrigger."""
    return [field for field in trigger.fields if field.name == name][0].expressions[0].first


class TestScheduledSyncJob:
    """Tests pour scheduled_sync_job"""

    @patch("sync.scheduled_sync._is_schedule_enabled", return_value=True)
    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.SessionLocal")
    @patch("sync.scheduled_sync.config_manager")
    def test_success(
        self, mock_cm, mock_session_local, mock_sequencer, _mock_schedule_enabled
    ):
        """Synchro réussie : l'étape s'exécute sans désactiver le planning"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_sequencer.enqueue.side_effect = _inline_enqueue

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

            mock_sequencer.enqueue.assert_called_once()
            enqueue_kwargs = mock_sequencer.enqueue.call_args.kwargs
            assert enqueue_kwargs["otp_config_id"] == 1
            assert enqueue_kwargs["grist_doc_id"] == "doc456"
            mock_sync.assert_called_once()
            args, kwargs = mock_sync.call_args
            assert args == (mock_cm.load_config_by_id.return_value,)
            assert kwargs["auto"] is True
            assert callable(kwargs["progress_callback"])
            mock_session_local.assert_not_called()

    @patch("sync.scheduled_sync._is_schedule_enabled", return_value=True)
    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.SessionLocal")
    @patch("sync.scheduled_sync.config_manager")
    def test_sync_failure_keeps_schedule_enabled(
        self, mock_cm, mock_session_local, mock_sequencer, _mock_schedule_enabled
    ):
        """Échec sync (success=False) : schedule reste activé"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_sequencer.enqueue.side_effect = _inline_enqueue

        mock_cm.load_config_by_id.return_value = {
            "otp_config_id": 1,
            "grist_doc_id": "doc456",
        }

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            mock_sync.return_value = {"success": False, "message": "Sync failed"}

            scheduled_sync_job(1, sync_manager)

            mock_session_local.assert_not_called()

    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.SessionLocal")
    @patch("sync.scheduled_sync.config_manager")
    def test_api_error_disables_schedule(
        self, mock_cm, mock_session_local, mock_sequencer
    ):
        """Erreur API (EXIT_CODE_EXTERNAL_API_ERROR) : schedule désactivé"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager
        from utils.constants import EXIT_CODE_EXTERNAL_API_ERROR

        mock_sequencer.enqueue.side_effect = _inline_enqueue

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_user_schedule = MagicMock()
        mock_user_schedule.otp_config_id = 1
        mock_db.query.return_value.filter_by.return_value.first.return_value = (
            mock_user_schedule
        )

        mock_cm.load_config_by_id.return_value = {
            "otp_config_id": 1,
            "grist_doc_id": "doc456",
        }

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

    @patch("sync.scheduled_sync._is_schedule_enabled", return_value=True)
    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.SessionLocal")
    @patch("sync.scheduled_sync.config_manager")
    def test_unexpected_exception_keeps_schedule_enabled(
        self, mock_cm, mock_session_local, mock_sequencer, _mock_schedule_enabled
    ):
        """Exception inattendue : propagée au séquenceur, qui la journalise et
        marque l'étape en erreur. Le planning reste actif, seule une erreur
        définitive le désactive."""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_sequencer.enqueue.side_effect = _inline_enqueue

        mock_cm.load_config_by_id.return_value = {
            "otp_config_id": 1,
            "grist_doc_id": "doc456",
        }

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            mock_sync.side_effect = RuntimeError("Unexpected")

            with pytest.raises(RuntimeError):
                scheduled_sync_job(1, sync_manager)

            mock_session_local.assert_not_called()

    @patch("sync.scheduled_sync._is_schedule_enabled", return_value=True)
    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.SessionLocal")
    @patch("sync.scheduled_sync.config_manager")
    def test_grist_read_error_keeps_schedule_enabled(
        self, mock_cm, mock_session_local, mock_sequencer, _mock_schedule_enabled
    ):
        """Lecture Grist en échec (EXIT_CODE_GRIST_READ_ERROR) : erreur
        transitoire, schedule toujours actif"""
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager
        from utils.constants import EXIT_CODE_GRIST_READ_ERROR

        mock_sequencer.enqueue.side_effect = _inline_enqueue

        mock_cm.load_config_by_id.return_value = {
            "otp_config_id": 1,
            "grist_doc_id": "doc456",
        }

        sync_manager = SyncManager(notify_callback=MagicMock())

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            mock_sync.return_value = {
                "success": False,
                "error_code": EXIT_CODE_GRIST_READ_ERROR,
                "message": "Grist n'a pas pu lire la table Demarche_1_dossiers",
            }

            scheduled_sync_job(1, sync_manager)

            mock_session_local.assert_not_called()

    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.SessionLocal")
    @patch("sync.scheduled_sync.config_manager")
    def test_config_not_found(
        self, mock_cm, mock_session_local, mock_sequencer
    ):
        """Config introuvable : retourne sans crash sans appeler la sync"""
        from configuration.config_manager import ConfigNotFoundError
        from sync.scheduled_sync import scheduled_sync_job
        from sync.sync_manager import SyncManager

        mock_cm.load_config_by_id.side_effect = ConfigNotFoundError("absent")

        mock_notifier = MagicMock()
        sync_manager = SyncManager(notify_callback=mock_notifier)

        with patch.object(
            sync_manager, "run_synchronization_task"
        ) as mock_sync:
            scheduled_sync_job(999, sync_manager)

            mock_sequencer.enqueue.assert_not_called()
            mock_sync.assert_not_called()


class TestScheduledSyncStepRefresh:
    """L'étape relit le planning et la configuration à son démarrage"""

    def _enqueue_and_capture(self, mock_sequencer):
        """Enfilement différé : retourne la liste où l'étape sera capturée."""
        captured = []

        def enqueue(otp_config_id, grist_doc_id, fn):
            captured.append(fn)
            return f"fake_step_config_{otp_config_id}"

        mock_sequencer.enqueue.side_effect = enqueue
        return captured

    @patch("sync.scheduled_sync._is_schedule_enabled", return_value=False)
    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.config_manager")
    def test_planning_desactive_apres_mise_en_file(
        self, mock_cm, mock_sequencer, _mock_schedule_enabled
    ):
        from sync.scheduled_sync import scheduled_sync_job

        captured = self._enqueue_and_capture(mock_sequencer)
        mock_cm.load_config_by_id.return_value = {"grist_doc_id": "doc456"}
        sync_manager = MagicMock()

        scheduled_sync_job(1, sync_manager)
        captured[0]()

        sync_manager.run_synchronization_task.assert_not_called()

    @patch("sync.scheduled_sync._is_schedule_enabled", return_value=True)
    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.config_manager")
    def test_config_modifiee_apres_mise_en_file(
        self, mock_cm, mock_sequencer, _mock_schedule_enabled
    ):
        """C'est la configuration relue au démarrage de l'étape qui est synchronisée"""
        from sync.scheduled_sync import scheduled_sync_job

        captured = self._enqueue_and_capture(mock_sequencer)
        config_at_enqueue = {"grist_doc_id": "doc456", "demarche_number": "123"}
        config_at_start = {"grist_doc_id": "doc456", "demarche_number": "456"}
        mock_cm.load_config_by_id.side_effect = [config_at_enqueue, config_at_start]
        sync_manager = MagicMock()
        sync_manager.run_synchronization_task.return_value = {"success": True}

        scheduled_sync_job(1, sync_manager)
        captured[0]()

        assert sync_manager.run_synchronization_task.call_args.args == (
            config_at_start,
        )

    @patch("sync.scheduled_sync._is_schedule_enabled", return_value=True)
    @patch("sync.scheduled_sync.sequencer")
    @patch("sync.scheduled_sync.config_manager")
    def test_config_supprimee_apres_mise_en_file(
        self, mock_cm, mock_sequencer, _mock_schedule_enabled
    ):
        from configuration.config_manager import ConfigNotFoundError
        from sync.scheduled_sync import scheduled_sync_job

        captured = self._enqueue_and_capture(mock_sequencer)
        mock_cm.load_config_by_id.side_effect = [
            {"grist_doc_id": "doc456"},
            ConfigNotFoundError("absent"),
        ]
        sync_manager = MagicMock()

        scheduled_sync_job(1, sync_manager)
        captured[0]()

        sync_manager.run_synchronization_task.assert_not_called()

    @pytest.mark.parametrize(
        ("schedule", "expected"),
        [
            (MagicMock(enabled=True), True),
            (MagicMock(enabled=False), False),
            (None, False),
        ],
    )
    @patch("sync.scheduled_sync.SessionLocal")
    def test_is_schedule_enabled_lit_le_planning_en_base(
        self, mock_session_local, schedule, expected
    ):
        from sync.scheduled_sync import _is_schedule_enabled

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter_by.return_value.first.return_value = schedule

        assert _is_schedule_enabled(1) is expected
        mock_db.query.return_value.filter_by.assert_called_once_with(otp_config_id=1)
        mock_db.close.assert_called_once()


class TestDailySyncJob:
    """Tests pour daily_sync_job"""

    @patch("sync.scheduled_sync.scheduled_sync_job")
    @patch("sync.scheduled_sync._enabled_schedule_config_ids", return_value=[])
    def test_aucun_planning_active(self, mock_ids, mock_job):
        """0 planning activé : rien n'est enfilé"""
        from sync.scheduled_sync import daily_sync_job

        daily_sync_job(MagicMock())

        mock_job.assert_not_called()

    @patch("sync.scheduled_sync.scheduled_sync_job")
    @patch("sync.scheduled_sync._enabled_schedule_config_ids", return_value=[1, 2])
    def test_enfile_chaque_planning_active_dans_l_ordre(self, mock_ids, mock_job):
        from sync.scheduled_sync import daily_sync_job

        sync_manager = MagicMock()

        daily_sync_job(sync_manager)

        assert [call.args for call in mock_job.call_args_list] == [
            (1, sync_manager),
            (2, sync_manager),
        ]

    @patch("sync.scheduled_sync.scheduled_sync_job")
    @patch("sync.scheduled_sync._enabled_schedule_config_ids", return_value=[1, 2])
    def test_echec_d_une_config_n_arrete_pas_les_suivantes(self, mock_ids, mock_job):
        from sync.scheduled_sync import daily_sync_job

        mock_job.side_effect = [RuntimeError("déchiffrement impossible"), None]

        daily_sync_job(MagicMock())

        assert mock_job.call_count == 2

    @patch("sync.scheduled_sync.SessionLocal")
    def test_lit_les_plannings_actives_a_chaque_execution(
        self, mock_session_local
    ):
        """Les plannings sont relus en base : seuls les activés sont enfilés"""
        from sync.scheduled_sync import daily_sync_job

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        query = mock_db.query.return_value
        query.filter_by.return_value.filter.return_value.order_by.return_value.all.return_value = [
            MagicMock(otp_config_id=3)
        ]

        with patch("sync.scheduled_sync.scheduled_sync_job") as mock_job:
            daily_sync_job(MagicMock())

        query.filter_by.assert_called_once_with(enabled=True)
        assert mock_job.call_args.args[0] == 3
        mock_db.close.assert_called_once()


class TestRegisterDailySyncJob:
    """Tests pour register_daily_sync_job"""

    def test_un_seul_job_a_l_heure_configuree(self):
        from sync.scheduled_sync import (
            DAILY_SYNC_JOB_ID,
            SYNC_HOUR,
            SYNC_MINUTE,
            daily_sync_job,
            register_daily_sync_job,
        )

        sync_manager = MagicMock()
        mock_scheduler = MagicMock()

        with patch("sync.scheduled_sync.scheduler", mock_scheduler):
            register_daily_sync_job(sync_manager)

        mock_scheduler.add_job.assert_called_once()
        kwargs = mock_scheduler.add_job.call_args.kwargs
        assert kwargs["func"] is daily_sync_job
        assert kwargs["args"] == [sync_manager]
        assert kwargs["id"] == DAILY_SYNC_JOB_ID
        assert kwargs["replace_existing"] is True
        assert kwargs["coalesce"] is True
        assert kwargs["misfire_grace_time"] > 1
        assert _trigger_value(kwargs["trigger"], "hour") == SYNC_HOUR
        assert _trigger_value(kwargs["trigger"], "minute") == SYNC_MINUTE
