import time
import threading
import os
import subprocess
import sys
import traceback
from typing import Callable, Any
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sync.sync_result_parser import parse_output
from sync.environment_config import build_environment
from sync.error_parser import extract_error_parts
from database.models import SyncLog

DATABASE_URL = os.getenv("DATABASE_URL")


class SyncManager:
    """
    Gestionnaire de synchronisations asynchrones avec callbacks de notification
    pour les mises à jour en temps réel
    """

    def __init__(
        self,
        notify_callback: Callable[..., Any] | None = None
    ):
        self.tasks = {}
        self.task_counter = 0
        self.notify_callback = notify_callback

    def notify(self, event_type: str, data: dict[str, Any]) -> None:
        """Méthode publique pour les notifications"""
        if self.notify_callback:
            self.notify_callback(event_type, data)

    def start_sync(
        self,
        server_config: dict[str, Any],
        auto: bool = False
    ) -> str:
        """Démarre une nouvelle synchronisation avec la configuration donnée"""
        return self.start_task(
            self.run_synchronization_task,
            server_config,
            auto=auto
        )

    def run_synchronization_task(
        self,
        config: dict[str, Any],
        progress_callback: Callable[[float, str], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
        auto: bool = False
    ) -> dict[str, Any]:
        """
        Exécute la synchronisation avec callbacks pour le suivi en temps réel
        """

        output_lines = []

        # Pré-définition en cas d'erreur
        result = {
            "success": False,
            "message": "",
            "success_count": 0,
            "error_count": 0
        }

        try:
            if progress_callback:
                progress_callback(5, "Préparation de l'environnement...")

            # Copie de l'environnement pour éviter la pollution globale
            env_copy = build_environment(config)

            if progress_callback:
                progress_callback(10, "Configuration des variables d'environnement...")

            # Appliquer les variables d'environnement pour ce thread
            os.environ.update(env_copy)

            if progress_callback:
                progress_callback(
                    15, "Chargement des données depuis Démarches Simplifiées..."
                )

            # ✅ Afficher les filtres effectivement utilisés (après définition)
            if log_callback:
                log_callback("=== CONFIGURATION DES FILTRES ===")

                # Vérifier et afficher les variables d'environnement de la copie
                date_debut = env_copy.get("DATE_DEPOT_DEBUT", "").strip()
                date_fin = env_copy.get("DATE_DEPOT_FIN", "").strip()
                statuts = env_copy.get("STATUTS_DOSSIERS", "").strip()
                groupes = env_copy.get("GROUPES_INSTRUCTEURS", "").strip()

                if date_debut:
                    log_callback(f"✓ Filtre date début: {date_debut}")
                else:
                    log_callback("○ Date début: AUCUN FILTRE (tous les dossiers)")

                if date_fin:
                    log_callback(f"✓ Filtre date fin: {date_fin}")
                else:
                    log_callback("○ Date fin: AUCUN FILTRE (tous les dossiers)")

                if statuts:
                    log_callback(f"✓ Filtre statuts: {statuts}")
                else:
                    log_callback("○ Statuts: AUCUN FILTRE (tous les dossiers)")

                if groupes:
                    log_callback(f"✓ Filtres groupes: {groupes}")
                else:
                    log_callback("○ Groupes: AUCUN FILTRE (tous les dossiers)")

                log_callback("====================================")

            if progress_callback:
                progress_callback(20, "Configuration des variables d'environnement...")

            # Appliquer les variables d'environnement pour ce thread
            os.environ.update(env_copy)

            if progress_callback:
                progress_callback(25, "Lancement du script de synchronisation...")

            # Lancer le script de synchronisation principal
            script_path = os.path.join(
                os.path.dirname(__file__), "../grist_processor_working_all.py"
            )

            if log_callback:
                log_callback(f"Lancement du script: {script_path}")

            # Exécuter le script de synchronisation
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env_copy,
                cwd=os.path.dirname(__file__),
            )

            for line in iter(process.stdout.readline, ""):
                if not line.strip():
                    continue
                line = line.strip()
                output_lines.append(line)

                if line.startswith("Progression: "):
                    parts = line.split(": ", 1)[1].split(" - ")
                    progress_value = float(parts[0])
                    phase_name = parts[1] if len(parts) > 1 else ""
                    if progress_callback:
                        progress_callback(progress_value, f"{phase_name}")
                elif not line.startswith("Progression pourcentage:"):
                    if log_callback:
                        log_callback(line)

            stderr_output = process.stderr.read()

            if stderr_output and log_callback:
                for line in stderr_output.split("\n"):
                    if line.strip():
                        log_callback(f"ERREUR: {line.strip()}")

            process.wait()

            # Traiter les erreurs
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode,
                    process.args,
                    stderr=stderr_output
                )

            result = parse_output(output_lines)

            if progress_callback:
                progress_callback(99, "Finalisation...")

            if log_callback:
                log_callback(
                    "Synchronisation terminée: "
                    f"{result['success_count']} dossiers synchronisés"
                    f", {result['error_count']} erreurs"
                )

            if progress_callback:
                progress_callback(100, result["message"])

            return result

        except Exception as e:
            error_parts = extract_error_parts(e, output_lines)
            if error_parts:
                error_msg = f"Erreur lors de la synchronisation: {'; '.join(error_parts)}"
            elif isinstance(e, subprocess.CalledProcessError):
                error_msg = f"Erreur lors de la synchronisation: {str(e)}"
            else:
                error_msg = f"Erreur lors de la synchronisation: {str(e)}"

            if log_callback:
                log_callback(error_msg)
                log_callback(traceback.format_exc())

            return {
                "success": False,
                "message": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "traceback": traceback.format_exc(),
            }
        finally:
            engine = create_engine(DATABASE_URL)
            SessionLocal = sessionmaker(bind=engine)
            db_session = SessionLocal()

            sync_log = SyncLog(
                grist_user_id=config.get("grist_user_id"),
                grist_doc_id=config.get("grist_doc_id"),
                status="success" if result.get("success") else "error",
                message=result.get("message"),
                auto=auto,
                success_count=result.get("success_count", 0),
                error_count=result.get("error_count", 0),
            )
            db_session.add(sync_log)
            db_session.commit()
            db_session.close()

    def start_task(
        self,
        task_function: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> str:
        """Démarre une nouvelle tâche asynchrone"""
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"

        self.tasks[task_id] = {
            "status": "running",
            "progress": 0,
            "message": "Initialisation...",
            "start_time": time.time(),
            "logs": [],
        }

        # Démarrer la tâche dans un thread séparé
        thread = threading.Thread(
            target=self._run_task, args=(task_id, task_function, *args), kwargs=kwargs
        )
        thread.start()

        return task_id

    def _run_task(
        self,
        task_id: str,
        task_function: Callable[..., Any],
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Exécute une tâche avec gestion des erreurs"""
        try:
            # Ajouter le callback de progression
            kwargs["progress_callback"] = lambda progress, message: (
                self._update_progress(task_id, progress, message)
            )
            kwargs["log_callback"] = lambda message: self._add_log(task_id, message)

            result = task_function(*args, **kwargs)

            self.tasks[task_id].update(
                {
                    "status": "completed",
                    "progress": 100,
                    "message": "Tâche terminée avec succès",
                    "result": result,
                    "sync_reason": result.get("sync_reason", "synced"),
                    "end_time": time.time(),
                }
            )

            self._emit_update(task_id)

        except Exception as e:
            self.tasks[task_id].update(
                {
                    "status": "error",
                    "message": f"Erreur: {str(e)}",
                    "error": str(e),
                    "end_time": time.time(),
                }
            )

            self._emit_update(task_id)

    def _update_progress(
        self,
        task_id: str,
        progress: float,
        message: str
    ) -> None:
        """Met à jour la progression d'une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]["progress"] = progress
            self.tasks[task_id]["message"] = message
            self._emit_update(task_id)

    def _add_log(
        self,
        task_id: str,
        message: str
    ) -> None:
        """Ajoute un log à une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]["logs"].append(
                {"timestamp": time.time(), "message": message}
            )
            self._emit_update(task_id)

    def _emit_update(self, task_id: str) -> None:
        """Émet une mise à jour via notification callback"""
        self.notify("task_update", {"task_id": task_id, "task": self.tasks[task_id]})
        time.sleep(0)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Récupère les informations d'une tâche"""
        return self.tasks.get(task_id)
