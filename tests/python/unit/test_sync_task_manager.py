"""
Tests unitaires pour la classe SyncTaskManager

Ces tests couvrent l'ensemble des fonctionnalités de la classe :
- Gestion des tâches asynchrones
- Configuration des variables d'environnement
- Exécution des scripts de synchronisation
- Callbacks de notification et progression
- Gestion des erreurs
"""

import os
from io import StringIO
from unittest.mock import patch, MagicMock
from sync_task_manager import SyncTaskManager


def create_mock_process(stdout_text, stderr_text="", returncode=0):
    """Crée un mock de processus avec comportement de pipe"""
    lines = list(stdout_text.split("\n"))

    class StdoutMock:
        def readline(self):
            if not lines:
                return ""
            return lines.pop(0) + "\n"

    mock_process = MagicMock()
    mock_process.returncode = returncode
    mock_process.stdout = StdoutMock()
    mock_process.stderr = StringIO(stderr_text)
    mock_process.wait = MagicMock(return_value=returncode)
    return mock_process


class TestSyncTaskManager:
    """Tests unitaires pour la classe SyncTaskManager"""

    def setup_method(self):
        """Initialisation avant chaque test"""
        self.mock_callback = MagicMock()
        self.manager = SyncTaskManager(notify_callback=self.mock_callback)

    def test_initialization_without_callback(self):
        """Test l'initialisation sans callback de notification"""
        manager = SyncTaskManager()
        assert manager.tasks == {}
        assert manager.task_counter == 0
        assert manager.notify_callback is None

    def test_initialization_with_callback(self):
        """Test l'initialisation avec callback de notification"""
        assert self.manager.tasks == {}
        assert self.manager.task_counter == 0
        assert self.manager.notify_callback == self.mock_callback

    def test_notify_with_callback(self):
        """Test la méthode notify avec callback configuré"""
        event_type = "test_event"
        data = {"key": "value"}

        self.manager.notify(event_type, data)

        self.mock_callback.assert_called_once_with(event_type, data)

    def test_notify_without_callback(self):
        """Test la méthode notify sans callback configuré"""
        manager = SyncTaskManager()

        # Ne doit pas lever d'exception
        manager.notify("test_event", {"key": "value"})

    def test_start_task_creates_unique_id(self):
        """Test que start_task crée un ID unique"""
        task_func = MagicMock(return_value="result")

        task_id1 = self.manager.start_task(task_func)
        task_id2 = self.manager.start_task(task_func)

        assert task_id1 != task_id2
        assert task_id1.startswith("task_")
        assert task_id2.startswith("task_")
        assert self.manager.task_counter == 2

    @patch("threading.Thread")
    def test_start_task_initializes_task_state(self, mock_thread):
        """Test que start_task initialise correctement l'état de la tâche"""
        task_func = MagicMock(return_value="result")
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        task_id = self.manager.start_task(task_func, "arg1", kwarg1="value1")

        # Vérifier l'état initial de la tâche
        task = self.manager.tasks[task_id]
        assert task["status"] == "running"
        assert task["progress"] == 0
        assert task["message"] == "Initialisation..."
        assert "start_time" in task
        assert task["logs"] == []

        # Vérifier que le thread a été démarré
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    @patch("threading.Thread")
    def test_get_task_existing(self, mock_thread):
        """Test get_task avec une tâche existante"""
        task_func = MagicMock(return_value="result")
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        task_id = self.manager.start_task(task_func)

        task = self.manager.get_task(task_id)

        assert task is not None
        assert task["status"] == "running"
        assert task["progress"] == 0

    def test_get_task_nonexistent(self):
        """Test get_task avec une tâche inexistante"""
        task = self.manager.get_task("nonexistent_task")
        assert task is None

    def test_update_progress_existing_task(self):
        """Test _update_progress pour une tâche existante"""
        task_func = MagicMock(return_value="result")
        task_id = self.manager.start_task(task_func)

        self.manager._update_progress(task_id, 50, "Test message")

        task = self.manager.tasks[task_id]
        assert task["progress"] == 50
        assert task["message"] == "Test message"

        # Vérifier que la notification a été envoyée
        self.mock_callback.assert_called_with(
            "task_update", {"task_id": task_id, "task": task}
        )

    def test_update_progress_nonexistent_task(self):
        """Test _update_progress pour une tâche inexistante"""
        # Ne doit pas lever d'exception
        self.manager._update_progress("nonexistent_task", 50, "Test message")

        # Aucune notification ne doit être envoyée
        self.mock_callback.assert_not_called()

    def test_add_log_existing_task(self):
        """Test _add_log pour une tâche existante"""
        task_func = MagicMock(return_value="result")
        task_id = self.manager.start_task(task_func)

        self.manager._add_log(task_id, "Test log message")

        task = self.manager.tasks[task_id]
        assert len(task["logs"]) == 1
        assert task["logs"][0]["message"] == "Test log message"
        assert "timestamp" in task["logs"][0]

        # Vérifier que la notification a été envoyée
        self.mock_callback.assert_called_with(
            "task_update", {"task_id": task_id, "task": task}
        )

    def test_add_log_nonexistent_task(self):
        """Test _add_log pour une tâche inexistante"""
        # Ne doit pas lever d'exception
        self.manager._add_log("nonexistent_task", "Test log message")

        # Aucune notification ne doit être envoyée
        self.mock_callback.assert_not_called()

    def test_emit_update(self):
        """Test _emit_update envoie la bonne notification"""
        task_func = MagicMock(return_value="result")
        task_id = self.manager.start_task(task_func)

        task = self.manager.tasks[task_id]

        self.manager._emit_update(task_id)

        self.mock_callback.assert_called_with(
            "task_update", {"task_id": task_id, "task": task}
        )

    def test_run_task_success(self):
        """Test _run_task avec exécution réussie"""

        # pyright: ignore[reportUnusedVariable]
        def mock_task_func(*_args, **_kwargs):
            return {"success": True, "message": "Task completed"}

        # Créer une tâche et l'exécuter directement
        task_id = self.manager.start_task(mock_task_func)

        # Exécuter manuellement la tâche en appelant _run_task directement
        self.manager._run_task(task_id, mock_task_func)

        # Vérifier l'état final de la tâche
        task = self.manager.get_task(task_id)
        assert task is not None
        assert task["status"] == "completed"
        assert task["progress"] == 100
        assert "result" in task
        assert task["result"]["success"] is True

    def test_start_sync_calls_start_task(self):
        """
        Test que start_sync appelle bien start_task avec la bonne fonction
        """
        server_config = {"test": "config"}

        with patch.object(self.manager, "start_task") as mock_start_task:
            self.manager.start_sync(server_config)

            mock_start_task.assert_called_once_with(
                self.manager.run_synchronization_task, server_config
            )

    @patch.dict(
        os.environ,
        {
            "DEMARCHES_API_TOKEN": "test_token",
            "DEMARCHE_NUMBER": "12345",
            "GRIST_BASE_URL": "https://test.grist.com",
            "GRIST_API_KEY": "test_key",
            "GRIST_DOC_ID": "test_doc",
            "GRIST_USER_ID": "test_user",
        },
    )
    @patch("subprocess.Popen")
    def test_run_synchronization_task_success(self, mock_subprocess):
        """Test run_synchronization_task avec succès"""
        mock_subprocess.return_value = create_mock_process("""Récupération de la démarche 12345
        Progression: 35 - Analyse de la démarche
        Nombre de dossiers trouvés: 10
        Types de colonnes détectés
        Progression: 50 - Création des tables
        Table dossiers
        Table champs
        Traitement du lot 1/5
        Progression: 95 - Finalisation
        Dossiers traités avec succès: 10
        Dossiers en échec: 0
        Total dossiers traités: 10
        """)

        # Configuration de test
        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_base_url": "https://test.grist.com",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
            "grist_user_id": "test_user",
        }

        # Callbacks de test
        progress_calls = []
        log_calls = []

        def progress_callback(progress, message):
            progress_calls.append((progress, message))

        def log_callback(message):
            log_calls.append(message)

        # Exécuter la tâche
        result = self.manager.run_synchronization_task(
            config, progress_callback, log_callback
        )

        # Vérifier le résultat
        assert result["success"] is True
        assert result["success_count"] == 10
        assert result["error_count"] == 0
        assert result["total_processed"] == 10
        assert "timestamp" in result

        # Vérifier que subprocess a été appelé
        mock_subprocess.assert_called_once()

        # Vérifier les appels de progression
        assert len(progress_calls) > 0
        assert progress_calls[-1][0] == 100  # Dernière progression à 100%

    @patch("subprocess.Popen")
    def test_run_synchronization_task_with_filters(self, mock_subprocess):
        """Test run_synchronization_task avec des filtres"""
        mock_subprocess.return_value = create_mock_process(
            "10 dossiers traités avec succès"
        )

        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
            "filter_date_start": "2024-01-01",
            "filter_date_end": "2024-12-31",
            "filter_statuses": "en_construction,en_instruction",
            "filter_groups": "1,2,3",
        }

        log_calls = []

        def log_callback(message):
            log_calls.append(message)

        self.manager.run_synchronization_task(config, log_callback=log_callback)

        # Vérifier que les filtres sont affichés dans les logs
        filter_logs = [log for log in log_calls if "Filtre" in log]
        assert len(filter_logs) > 0

        # Vérifier l'environnement passé à subprocess
        _, kwargs = mock_subprocess.call_args
        env = kwargs["env"]
        assert env.get("DATE_DEPOT_DEBUT") == "2024-01-01"
        assert env.get("DATE_DEPOT_FIN") == "2024-12-31"
        assert env.get("STATUTS_DOSSIERS") == "en_construction,en_instruction"
        assert env.get("GROUPES_INSTRUCTEURS") == "1,2,3"

    @patch("subprocess.Popen")
    def test_run_synchronization_task_subprocess_error(self, mock_subprocess):
        """Test run_synchronization_task avec erreur subprocess"""
        mock_subprocess.return_value = create_mock_process(
            "", "Script error occurred", returncode=1
        )

        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
        }

        log_calls = []

        def log_callback(message):
            log_calls.append(message)

        result = self.manager.run_synchronization_task(
            config, log_callback=log_callback
        )

        # Vérifier que l'erreur est bien gérée
        assert result["success"] is False
        assert "Erreur lors de la synchronisation" in result["message"]
        assert "Script error occurred" in result["message"]
        assert "traceback" in result

    @patch("subprocess.Popen")
    def test_run_synchronization_task_error_code_api_error(self, mock_subprocess):
        """Test error_code=2 retourné pour erreur API externe"""
        mock_subprocess.return_value = create_mock_process(
            "", "API error: Token expiré", returncode=2
        )

        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
        }

        result = self.manager.run_synchronization_task(config)

        assert result["error_code"] == 2

    @patch("subprocess.Popen")
    def test_run_synchronization_task_error_code_general_error(self, mock_subprocess):
        """Test error_code=1 retourné pour erreur générale"""
        mock_subprocess.return_value = create_mock_process(
            "", "General error", returncode=1
        )

        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
        }

        result = self.manager.run_synchronization_task(config)

        assert result["error_code"] == 1

    def test_run_synchronization_task_exception_handling(self):
        """Test run_synchronization_task avec exception générale"""
        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
        }

        log_calls = []

        def log_callback(message):
            log_calls.append(message)

        # Simuler une erreur dans le traitement
        with patch("subprocess.Popen", side_effect=Exception("Unexpected error")):
            result = self.manager.run_synchronization_task(
                config, log_callback=log_callback
            )

            assert result["success"] is False
            assert "Erreur lors de la synchronisation" in result["message"]
            assert "traceback" in result

    @patch("subprocess.Popen")
    def test_progress_parsing(self, mock_subprocess):
        """Test le parsing de la progression depuis les logs"""
        mock_subprocess.return_value = create_mock_process("""Configuration Grist
        Progression: 34 - Vérification des connexions aux APIs
        Progression: 39 - Préparation du traitement
        100 dossiers traités avec succès""")

        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
        }

        progress_calls = []

        def progress_callback(progress, message):
            progress_calls.append((progress, message))

        self.manager.run_synchronization_task(
            config, progress_callback=progress_callback
        )

        # Vérifier que la progression a été calculée correctement
        progress_values = [p[0] for p in progress_calls]
        matching_34 = [p for p in progress_values if 34 <= p <= 35]
        matching_39 = [p for p in progress_values if 39 <= p <= 40]
        assert matching_34, f"Progression attendue ~34, recue: {progress_values}"
        assert matching_39, f"Progression attendue ~40, recue: {progress_values}"

    @patch("subprocess.Popen")
    def test_environment_variables_setup(self, mock_subprocess):
        """Test la configuration des variables d'environnement"""
        mock_subprocess.return_value = create_mock_process("Test output")

        config = {
            "ds_api_token": "new_token",
            "demarche_number": "99999",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
            "grist_base_url": "https://new.grist.com",
        }

        self.manager.run_synchronization_task(config)

        # Vérifier l'environnement passé à subprocess
        _, kwargs = mock_subprocess.call_args
        env = kwargs["env"]
        assert env.get("DEMARCHES_API_TOKEN") == "new_token"
        assert env.get("DEMARCHE_NUMBER") == "99999"
        assert env.get("GRIST_BASE_URL") == "https://new.grist.com"

    @patch("subprocess.Popen")
    def test_statistics_parsing(self, mock_subprocess):
        """Test le parsing des statistiques depuis la sortie"""
        mock_subprocess.return_value = create_mock_process("""Dossiers traités avec succès: 85
        Dossiers en échec: 15
        Total dossiers traités: 100
        """)

        config = {
            "ds_api_token": "test_token",
            "demarche_number": "12345",
            "grist_api_key": "test_key",
            "grist_doc_id": "test_doc",
        }

        result = self.manager.run_synchronization_task(config)

        assert result["success_count"] == 85
        assert result["error_count"] == 15
        assert result["total_processed"] == 100
        assert result["dossier_count"] == 100
        assert result["success"] is False  # Parce qu'il y a des erreurs
