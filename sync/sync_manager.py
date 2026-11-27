import time
import threading
import os
import subprocess
import sys
import traceback
from typing import Callable, Any
from datetime import datetime, timezone
from sync.sync_result_parser import (
    SYNC_ERRORS_PREFIX,
    SYNC_LOG_VALUES_PREFIX,
    parse_output,
    read_sync_errors,
    timestamped_error,
)
from sync.environment_config import build_environment
from sync.filters import build_filters_cache_key
from sync.incremental import (
    dates_to_env,
    dates_to_request,
    last_sync_with_dates,
    needs_full_sync,
)
from sync.error_parser import (
    error_message,
    extract_error_parts,
    stderr_error_messages,
)
from sync.sequencer import STATUS_PENDING, STATUS_RUNNING, SyncSequencer

from database.models import SyncLog
from database.session import SessionLocal
from configuration.config_manager import ConfigManager
from grist.utils import (
    GristKeyAccessError,
    GristUnavailableError,
    require_owner_access,
)
from utils.constants import (
    DATABASE_URL,
    EXIT_CODE_EXTERNAL_API_ERROR,
    EXIT_CODE_GRIST_READ_ERROR,
)
from utils.log import log_sync_errors

# Nombre maximal de logs retenus par tâche en mémoire serveur
MAX_LOGS_PER_TASK = 2000

# Longueur maximale du message d'erreur présenté à l'utilisateur (affiché par
# le front sous la barre de progression) : au-delà, le texte est tronqué.
# Le détail complet (stderr, tracebacks) reste dans les logs de la tâche.
MAX_ERROR_MESSAGE_LENGTH = 500

# Champs de configuration nécessaires à une synchronisation
REQUIRED_SYNC_FIELDS = [
    "ds_api_token",
    "demarche_number",
    "grist_api_key",
    "grist_doc_id",
    "grist_user_id",
]


class SyncSeriesAlreadyRunningError(Exception):
    """Une série de synchronisations est déjà en cours pour cet utilisateur et ce document."""


class SyncManager:
    """
    Gestionnaire de synchronisations asynchrones avec callbacks de notification
    pour les mises à jour en temps réel
    """

    def __init__(self, notify_callback: Callable[..., Any] | None = None):
        self.tasks = {}
        self.task_counter = 0
        self.notify_callback = notify_callback
        self._broadcast_offset: dict[str, int] = {}
        # Séries « Tout synchroniser » par (utilisateur Grist, document Grist) :
        # chacune a sa propre séquence, distincte de celle des synchros
        # automatiques (sync.sequencer.sequencer)
        self._series: dict[tuple[str, str], SyncSequencer] = {}
        self._series_lock = threading.Lock()

    def notify(self, event_type: str, data: dict[str, Any]) -> None:
        """Méthode publique pour les notifications"""
        if self.notify_callback:
            self.notify_callback(event_type, data)

    def start_sync(
        self,
        server_config: dict[str, Any],
        auto: bool = False,
        force_full_sync: bool = False,
    ) -> str:
        """Démarre une nouvelle synchronisation avec la configuration donnée"""
        return self.start_task(
            self.run_synchronization_task,
            server_config,
            auto=auto,
            force_full_sync=force_full_sync,
            config=server_config,
        )

    def start_sync_series(
        self, series_key: tuple[str, str], configs: list[dict[str, Any]]
    ) -> list[str]:
        """
        Démarre une série de synchronisations (« Tout synchroniser ») : les
        configurations passent une par une, dans l'ordre, dans une séquence
        propre à la série. Une erreur n'arrête pas les suivantes. Retourne les
        identifiants de tâche, dans l'ordre des configurations.
        Lève SyncSeriesAlreadyRunningError si une série de la même clé
        (utilisateur, document) n'est pas terminée.
        """
        with self._series_lock:
            current_series = self._series.get(series_key)
            if current_series and _has_unfinished_steps(current_series):
                raise SyncSeriesAlreadyRunningError()

            series = SyncSequencer()
            self._series[series_key] = series

            task_ids = [
                self._create_task(status="queued", message="En attente…", config=config)
                for config in configs
            ]
            for task_id, config in zip(task_ids, configs):
                self._emit_update(task_id)
                series.enqueue(
                    otp_config_id=config["otp_config_id"],
                    grist_doc_id=config["grist_doc_id"],
                    fn=lambda task_id=task_id, config=config: self._run_queued_task(
                        task_id, config, task_ids
                    ),
                )

            # Le pool exécute encore les étapes en file, puis libère son thread
            series.shutdown(wait=False)

        return task_ids

    def shutdown_series(self) -> None:
        """
        Arrêt de l'application : pour chaque série, seule la synchro en cours
        est attendue, celles en attente sont annulées.
        """
        with self._series_lock:
            all_series = list(self._series.values())

        for series in all_series:
            series.shutdown(cancel_pending=True)

    def sync_state(self, grist_user_id: str, grist_doc_id: str) -> list[dict[str, Any]]:
        """
        État complet (logs retenus compris) des synchros d'un utilisateur sur un
        document, dans l'ordre de création : la synchro en cours, ou toutes
        celles d'une série non terminée. Permet à une page rouverte de reprendre
        l'affichage.
        """
        # Copie : les threads de synchro modifient self.tasks en parallèle
        return [
            {"task_id": task_id, "task": {**task, "logs": list(task["logs"])}}
            for task_id, task in list(self.tasks.items())
            if task.get("grist_user_id") == grist_user_id
            and task.get("grist_doc_id") == grist_doc_id
        ]

    def run_synchronization_task(
        self,
        config: dict[str, Any],
        *,
        progress_callback: Callable[[float, str], None],
        log_callback: Callable[[str], None] | None = None,
        auto: bool = False,
        force_full_sync: bool = False,
    ) -> dict[str, Any]:
        """
        Exécute la synchronisation avec callbacks pour le suivi en temps réel
        """

        output_lines = []
        # Erreurs de la synchro, horodatées à leur réception, dans l'ordre
        errors: list[dict[str, str]] = []
        # Celles que le script ne peut pas émettre dans sa ligne SYNC_ERRORS
        unemitted_errors: list[dict[str, str]] = []

        # Pré-définition en cas d'erreur
        result = {"success": False, "message": "", "success_count": 0, "error_count": 0}
        # Empreinte des filtres et décision de synchro complète, enregistrées
        # dans sync_logs ; None si la synchro échoue avant leur calcul
        filters_key: str | None = None
        full_sync: bool | None = None

        try:
            # Refuser tôt une clé Grist qui ne permet pas de synchroniser le
            # document : le sous-processus ne ferait que récolter des refus
            # d'écriture. Grist injoignable est aussi un refus, mais transitoire :
            # son code d'erreur ne désactive pas la synchro planifiée.
            grist_api_key = config.get("grist_api_key")
            if grist_api_key:
                try:
                    require_owner_access(
                        config.get("grist_base_url") or "",
                        grist_api_key,
                        str(config.get("grist_doc_id") or ""),
                    )
                except GristKeyAccessError as error:
                    if isinstance(error, GristUnavailableError):
                        message = (
                            f"{error} : l'accès de la clé API Grist au document "
                            "n'a pas pu être vérifié."
                        )
                        error_code = EXIT_CODE_GRIST_READ_ERROR
                    else:
                        message = (
                            "La clé API Grist enregistrée n'a pas les droits "
                            "de propriétaire sur le document Grist."
                        )
                        error_code = EXIT_CODE_EXTERNAL_API_ERROR
                    if log_callback:
                        log_callback(f"ERREUR: {message}")
                    errors.append(_timestamped_error(message))
                    unemitted_errors.append(errors[-1])
                    result = {
                        "success": False,
                        "message": message,
                        "success_count": 0,
                        "error_count": 0,
                        "error_code": error_code,
                    }
                    return result

            # Copie de l'environnement pour le sous-processus
            env_copy = build_environment(config)

            # Synchro complète ou incrémentale : décidée ici, d'après la
            # dernière synchro de la configuration qui a laissé des dates ; le
            # sous-processus reçoit seulement les dates à demander à DN
            filters_key = build_filters_cache_key(env_copy)
            previous = _last_sync_with_dates(config.get("otp_config_id"))
            full_sync = needs_full_sync(
                previous,
                config["demarche_number"],
                filters_key,
                forced=force_full_sync,
            )
            dates = dates_to_request(previous, full_sync)
            env_copy = {**env_copy, **dates_to_env(dates)}

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

            progress_callback(1, "Lancement du script de synchronisation...")

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
                # Lignes techniques : ni erreurs à capturer, ni logs pour le client
                if line.startswith((SYNC_LOG_VALUES_PREFIX, SYNC_ERRORS_PREFIX)):
                    continue

                message = error_message(line)
                if message is not None:
                    errors.append(_timestamped_error(message))

                if line.startswith("Progression: "):
                    parts = line.split(": ", 1)[1].split(" - ")
                    progress_value = float(parts[0])
                    phase_name = parts[1] if len(parts) > 1 else ""
                    progress_callback(progress_value, phase_name)
                elif not line.startswith("Progression pourcentage:"):
                    if log_callback:
                        log_callback(line)

            stderr_output = process.stderr.read()
            unemitted_errors.extend(
                _timestamped_error(message)
                for message in stderr_error_messages(stderr_output)
            )
            errors.extend(unemitted_errors)

            if stderr_output and log_callback:
                for line in stderr_output.split("\n"):
                    if line.strip():
                        log_callback(f"ERREUR: {line.strip()}")

            process.wait()

            # Traiter les erreurs
            if process.returncode != 0:
                raise subprocess.CalledProcessError(
                    process.returncode, process.args, stderr=stderr_output
                )

            result = parse_output(output_lines)

            # Valeurs de fin de sync illisibles : prévenir l'utilisateur
            # sans faire échouer une sync dont les dossiers sont synchronisés.
            if result.get("sync_log_values_error") and log_callback:
                log_callback(
                    "Valeurs de fin de synchronisation (SYNC_LOG_VALUES) illisibles : "
                    "durée et dates non enregistrées"
                )

            progress_callback(99, "Finalisation...")

            if log_callback:
                log_callback(
                    "Synchronisation terminée: "
                    f"{result['success_count']} dossiers synchronisés"
                    f", {result['error_count']} erreurs"
                )

            progress_callback(100, result["message"])

            return result

        except Exception as e:
            error_parts = extract_error_parts(e, output_lines)
            if error_parts:
                summary = _truncate("; ".join(error_parts))
                error_msg = f"Erreur lors de la synchronisation: {summary}"
            else:
                error_msg = f"Erreur lors de la synchronisation: {str(e)}"

            if log_callback:
                log_callback(error_msg)
                log_callback(traceback.format_exc())

            result = {
                "success": False,
                "message": error_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "traceback": traceback.format_exc(),
                "success_count": result.get("success_count", 0),
                "error_count": result.get("error_count", 0),
                "error_code": getattr(e, "returncode", 1),
            }

            return result
        finally:
            failed = not result.get("success")
            if failed:
                mode = "auto" if auto else "manuelle"
                log_sync_errors(
                    f"Synchro {mode} en échec pour config "
                    f"{config.get('otp_config_id')} "
                    f"(démarche {config.get('demarche_number')}) : "
                    f"{result.get('message')}",
                    errors,
                )

            sync_log = SyncLog(
                grist_user_id=config.get("grist_user_id"),
                grist_doc_id=config.get("grist_doc_id"),
                otp_config_id=config.get("otp_config_id"),
                demarche_number=config.get("demarche_number"),
                status="error" if failed else "success",
                message=result.get("message"),
                auto=auto,
                success_count=result.get("success_count", 0),
                error_count=result.get("error_count", 0),
                duration_seconds=result.get("duration_seconds"),
                force_full_sync=full_sync,
                filters_hash=filters_key,
                modified_dossiers_since=_as_datetime(
                    result.get("modified_dossiers_since")
                ),
                deleted_dossiers_since=_as_datetime(
                    result.get("deleted_dossiers_since")
                ),
                errors=(
                    _sync_log_errors(output_lines, unemitted_errors)
                    if failed
                    else None
                ),
            )
            db_session = SessionLocal()
            try:
                db_session.add(sync_log)
                db_session.commit()
            finally:
                db_session.close()

            try:
                ConfigManager(DATABASE_URL).fetch_and_store_grist_user_email(
                    config.get("otp_config_id"),
                    config.get("grist_base_url"),
                    config.get("grist_api_key"),
                )
            except Exception as e:
                if log_callback:
                    log_callback(f"Enregistrement de l'email Grist ignoré: {e}")

    def start_task(
        self,
        task_function: Callable[..., Any],
        *args: Any,
        config: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """Démarre une nouvelle tâche asynchrone"""
        task_id = self._create_task(
            status="running", message="Initialisation...", config=config
        )

        # Démarrer la tâche dans un thread séparé
        thread = threading.Thread(
            target=self._run_task, args=(task_id, task_function, *args), kwargs=kwargs
        )
        thread.start()

        return task_id

    def _create_task(
        self, status: str, message: str, config: dict[str, Any] | None = None
    ) -> str:
        """
        Enregistre une nouvelle tâche dans l'état donné ; retourne son identifiant.
        La configuration synchronisée, si fournie, désigne le propriétaire de la
        tâche (utilisateur et document Grist) et sa démarche.
        """
        config = config or {}
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"

        self.tasks[task_id] = {
            "grist_user_id": config.get("grist_user_id"),
            "grist_doc_id": config.get("grist_doc_id"),
            "demarche_number": config.get("demarche_number"),
            "status": status,
            "progress": 0,
            "message": message,
            "start_time": time.time(),
            "logs": [],
            "log_base": 0,
        }

        return task_id

    def _run_queued_task(
        self, task_id: str, config: dict[str, Any], series_task_ids: list[str]
    ) -> None:
        """
        Exécute, à son tour dans la série, une synchronisation mise en attente.
        Les tâches terminées de la série restent consultables (sync_state)
        jusqu'à la fin de la dernière, puis sont toutes retirées.
        """
        self.tasks[task_id].update(
            {
                "status": "running",
                "message": "Initialisation...",
                "start_time": time.time(),
            }
        )
        self._emit_update(task_id)
        self._run_task(
            task_id, self.run_synchronization_task, config, auto=False, keep_task=True
        )

        if task_id == series_task_ids[-1]:
            for series_task_id in series_task_ids:
                self._remove_task(series_task_id)

    def _run_task(
        self,
        task_id: str,
        task_function: Callable[..., Any],
        *args: Any,
        keep_task: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Exécute une tâche avec gestion des erreurs. Une fois terminée, la tâche
        est retirée, sauf avec keep_task (l'appelant s'en charge).
        """
        try:
            # Ajouter le callback de progression
            kwargs["progress_callback"] = lambda progress, message: (
                self._update_progress(task_id, progress, message)
            )
            kwargs["log_callback"] = lambda message: self._add_log(task_id, message)

            result = task_function(*args, **kwargs)

            is_success = result.get("success", False)
            self.tasks[task_id].update(
                {
                    "status": "completed" if is_success else "error",
                    "progress": 100,
                    "message": "Tâche terminée avec succès"
                    if is_success
                    else result.get("message", "Erreur"),
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

        finally:
            if not keep_task:
                self._remove_task(task_id)

    def _remove_task(self, task_id: str) -> None:
        """Oublie une tâche terminée."""
        self.tasks.pop(task_id, None)
        self._broadcast_offset.pop(task_id, None)

    def _update_progress(self, task_id: str, progress: float, message: str) -> None:
        """Met à jour la progression d'une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]["progress"] = progress
            self.tasks[task_id]["message"] = message
            self._emit_update(task_id)

    def _add_log(self, task_id: str, message: str) -> None:
        """Ajoute un log à une tâche"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            # Position absolue du log : le client fusionne sans doublon les logs
            # d'un état complet (sync_state) et ceux des envois en delta
            index = task["log_base"] + len(task["logs"])
            task["logs"].append(
                {"timestamp": time.time(), "message": message, "index": index}
            )
            if len(task["logs"]) > MAX_LOGS_PER_TASK:
                trimmed = len(task["logs"]) - MAX_LOGS_PER_TASK
                del task["logs"][:trimmed]
                task["log_base"] += trimmed
            self._emit_update(task_id)

    def _emit_update(self, task_id: str) -> None:
        """Émet une mise à jour via notification callback (logs en delta)"""
        task = self.tasks[task_id]
        next_index = task["log_base"] + len(task["logs"])
        broadcasted = self._broadcast_offset.get(task_id, 0)
        cut = max(0, broadcasted - task["log_base"])
        self._broadcast_offset[task_id] = next_index
        task_payload = {**task, "logs": task["logs"][cut:]}
        self.notify("task_update", {"task_id": task_id, "task": task_payload})
        time.sleep(0)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """Récupère les informations d'une tâche"""
        return self.tasks.get(task_id)


def missing_sync_fields(config: dict[str, Any]) -> list[str]:
    """Champs nécessaires à la synchronisation, absents ou vides dans la configuration."""
    return [field for field in REQUIRED_SYNC_FIELDS if not config.get(field)]


# --- Helpers privés (module) ---


def _last_sync_with_dates(otp_config_id: int | None) -> SyncLog | None:
    """Dernière synchronisation de la configuration qui a laissé des dates à la
    suivante ; None s'il n'y en a pas."""
    if otp_config_id is None:
        return None

    with SessionLocal() as db:
        return last_sync_with_dates(db, otp_config_id)


def _as_datetime(value: str | None) -> datetime | None:
    """Date émise par le sous-processus (ISO 8601, UTC), au format de la base."""
    return datetime.fromisoformat(value) if value else None


def _has_unfinished_steps(series: SyncSequencer) -> bool:
    """Indique si une série a encore des étapes en attente ou en cours."""
    return any(
        step["status"] in (STATUS_PENDING, STATUS_RUNNING) for step in series.snapshot()
    )


def _timestamped_error(message: str) -> dict[str, str]:
    """Erreur de synchro horodatée à sa réception, message borné."""
    return timestamped_error(_truncate(message))


def _truncate(text: str) -> str:
    """Texte borné à MAX_ERROR_MESSAGE_LENGTH caractères, terminé par « … »
    s'il est coupé."""
    if len(text) <= MAX_ERROR_MESSAGE_LENGTH:
        return text

    return text[: MAX_ERROR_MESSAGE_LENGTH - 1].rstrip() + "…"


def _sync_log_errors(
    output_lines: list[str], unemitted_errors: list[dict[str, str]]
) -> dict:
    """Erreurs enregistrées dans sync_logs : celles émises par le script, suivies
    dans les erreurs générales de celles qu'il ne peut pas émettre (stderr, refus
    de la clé), messages bornés."""
    emitted = read_sync_errors(output_lines)
    return {
        **emitted,
        "dossiers": [_truncated_error(error) for error in emitted["dossiers"]],
        "general": [
            _truncated_error(error)
            for error in emitted["general"] + unemitted_errors
        ],
    }


def _truncated_error(error: dict[str, str]) -> dict[str, str]:
    """Erreur au message borné."""
    return {**error, "message": _truncate(error["message"])}
