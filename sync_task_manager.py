import time
import threading
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from utils.sync_result_parser import parse_output

class SyncTaskManager:
    """
    Gestionnaire de synchronisations asynchrones avec callbacks de notification
    pour les mises à jour en temps réel
    """

    def __init__(self, notify_callback=None):
        self.tasks = {}
        self.task_counter = 0
        self.notify_callback = notify_callback

    def notify(self, event_type, data):
        """Méthode publique pour les notifications"""
        if self.notify_callback:
            self.notify_callback(event_type, data)

    def start_sync(self, server_config):
        """Démarre une nouvelle synchronisation avec la configuration donnée"""
        return self.start_task(self.run_synchronization_task, server_config)

    def run_synchronization_task(
        self, config, progress_callback=None, log_callback=None
    ):
        """
        Exécute la synchronisation avec callbacks pour le suivi en temps réel
        """
        try:
            if progress_callback:
                progress_callback(5, "Préparation de l'environnement...")

            # Mettre à jour les variables d'environnement avec la configuration
            env_mapping = {
                "ds_api_token": "DEMARCHES_API_TOKEN",
                "demarche_number": "DEMARCHE_NUMBER",
                "grist_base_url": "GRIST_BASE_URL",
                "grist_api_key": "GRIST_API_KEY",
                "grist_doc_id": "GRIST_DOC_ID",
                "grist_user_id": "GRIST_USER_ID",
                # Filtres depuis la configuration DB
                "filter_date_start": "DATE_DEPOT_DEBUT",
                "filter_date_end": "DATE_DEPOT_FIN",
                "filter_statuses": "STATUTS_DOSSIERS",
                "filter_groups": "GROUPES_INSTRUCTEURS",
            }

            # Copie de l'environnement pour éviter la pollution globale
            env_copy = os.environ.copy()

            if progress_callback:
                progress_callback(10, "Configuration des variables d'environnement...")

            # Mettre à jour les variables d'environnement avec les filtres
            if config.get("filter_date_start"):
                env_copy["DATE_DEPOT_DEBUT"] = config["filter_date_start"]
            if config.get("filter_date_end"):
                env_copy["DATE_DEPOT_FIN"] = config["filter_date_end"]
            if config.get("filter_statuses"):
                env_copy["STATUTS_DOSSIERS"] = config["filter_statuses"]
            if config.get("filter_groups"):
                env_copy["GROUPES_INSTRUCTEURS"] = config["filter_groups"]

            # Appliquer la configuration à l'environnement
            for key, env_key in env_mapping.items():
                if key in config:
                    env_copy[env_key] = config[key]

            # Appliquer les variables d'environnement pour ce thread
            os.environ.update(env_copy)

            if progress_callback:
                progress_callback(
                    15, "Chargement des données depuis Démarches Simplifiées..."
                )

            # Définir les filtres dans la copie d'environnement (pas dans l'environnement global)
            for config_key, env_key in env_mapping.items():
                env_copy[env_key] = str(config.get(config_key, ""))

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
                os.path.dirname(__file__), "grist_processor_working_all.py"
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

            output_lines = []
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
            if isinstance(e, subprocess.CalledProcessError):
                error_msg = f"Erreur lors de la synchronisation: {e.stderr.strip() or str(e)}"
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

    def start_task(self, task_function, *args, **kwargs):
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

    def _run_task(self, task_id, task_function, *args, **kwargs):
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

    def _update_progress(self, task_id, progress, message):
        """Met à jour la progression d'une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]["progress"] = progress
            self.tasks[task_id]["message"] = message
            self._emit_update(task_id)

    def _add_log(self, task_id, message):
        """Ajoute un log à une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]["logs"].append(
                {"timestamp": time.time(), "message": message}
            )
            self._emit_update(task_id)

    def _emit_update(self, task_id):
        """Émet une mise à jour via notification callback"""
        self.notify("task_update", {"task_id": task_id, "task": self.tasks[task_id]})
        time.sleep(0)

    def get_task(self, task_id):
        """Récupère les informations d'une tâche"""
        return self.tasks.get(task_id)
