"""
Séquenceur de synchronisations.

Ordonnance les synchronisations automatiques dans une file globale : une
seule synchronisation s'exécute à la fois. Une file par document Grist
conserve l'ordre des étapes d'un même document. Aucune surface HTTP : les
appelants (la planification) enfilent des étapes, l'état est conservé en
mémoire.
"""

import logging
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SYNCS = 1
MAX_FINISHED_STEPS = 100

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"


class _Step:
    """Étape interne du séquenceur : une synchronisation à exécuter."""

    def __init__(
        self,
        step_id: str,
        otp_config_id: int,
        grist_doc_id: str,
        fn: Callable[[], None] | None,
    ) -> None:
        self.step_id = step_id
        self.otp_config_id = otp_config_id
        self.grist_doc_id = grist_doc_id
        self.fn = fn
        self.status = STATUS_PENDING
        self.enqueued_at = datetime.now(timezone.utc)
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None


class SyncSequencer:
    """
    Ordonnanceur de synchronisations en mémoire.

    Les étapes s'exécutent une par une. Une configuration déjà en attente ou
    en cours n'est pas remise en file. Une étape dont l'appel lève une
    exception passe en erreur sans empêcher la suite de la file.
    """

    def __init__(self, max_concurrent_syncs: int = MAX_CONCURRENT_SYNCS) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_concurrent_syncs, thread_name_prefix="sync-sequencer"
        )
        self._lock = threading.Lock()
        self._queues: dict[str, deque[_Step]] = {}
        self._active_docs: set[str] = set()
        self._steps: list[_Step] = []
        self._step_counter = 0

    def enqueue(
        self, otp_config_id: int, grist_doc_id: str, fn: Callable[[], None]
    ) -> str:
        """
        Enfile une étape pour une configuration ; retourne son identifiant.
        Si la configuration est déjà en attente ou en cours, l'étape existante
        est retournée sans double enfilement.
        """
        with self._lock:
            for step in self._steps:
                if (
                    step.otp_config_id == otp_config_id
                    and step.status in (STATUS_PENDING, STATUS_RUNNING)
                ):
                    logger.info(
                        f"Config {otp_config_id} déjà en file ({step.step_id}), "
                        "enfilement ignoré"
                    )
                    return step.step_id

            self._step_counter += 1
            step = _Step(
                step_id=(
                    f"sync_{self._step_counter}"
                    f"_config_{otp_config_id}_doc_{grist_doc_id}"
                ),
                otp_config_id=otp_config_id,
                grist_doc_id=grist_doc_id,
                fn=fn,
            )
            self._steps.append(step)
            self._queues.setdefault(grist_doc_id, deque()).append(step)

            if grist_doc_id not in self._active_docs:
                self._active_docs.add(grist_doc_id)
                self._executor.submit(self._drain_doc, grist_doc_id)

            return step.step_id

    def snapshot(self) -> list[dict[str, Any]]:
        """Copie de l'état des étapes (lecture seule côté appelant)."""
        with self._lock:
            return [
                {
                    "step_id": step.step_id,
                    "otp_config_id": step.otp_config_id,
                    "grist_doc_id": step.grist_doc_id,
                    "status": step.status,
                    "enqueued_at": step.enqueued_at,
                    "started_at": step.started_at,
                    "finished_at": step.finished_at,
                }
                for step in self._steps
            ]

    def shutdown(self, wait: bool = True) -> None:
        """Arrête le pool d'exécution, en attendant les étapes en cours si demandé."""
        self._executor.shutdown(wait=wait)

    # --- Helpers privés ---

    def _drain_doc(self, grist_doc_id: str) -> None:
        """Exécute les étapes en file pour un document, une par une."""
        while True:
            with self._lock:
                queue = self._queues.get(grist_doc_id)
                if not queue:
                    self._active_docs.discard(grist_doc_id)
                    self._queues.pop(grist_doc_id, None)
                    return
                step = queue.popleft()
                step.status = STATUS_RUNNING
                step.started_at = datetime.now(timezone.utc)

            try:
                step.fn()
                with self._lock:
                    step.status = STATUS_DONE
            except Exception:
                logger.exception(
                    f"Échec de l'étape {step.step_id} "
                    f"(config {step.otp_config_id}, document {step.grist_doc_id})"
                )
                with self._lock:
                    step.status = STATUS_ERROR
            finally:
                with self._lock:
                    step.fn = None
                    step.finished_at = datetime.now(timezone.utc)
                    self._prune_finished_steps()

    def _prune_finished_steps(self) -> None:
        """Conserve uniquement les dernières étapes terminées."""
        finished_count = 0
        kept_reversed: list[_Step] = []
        for step in reversed(self._steps):
            if step.status in (STATUS_DONE, STATUS_ERROR):
                finished_count += 1
                if finished_count > MAX_FINISHED_STEPS:
                    continue
            kept_reversed.append(step)
        self._steps = list(reversed(kept_reversed))


# Singleton partagé par la planification et l'application
sequencer = SyncSequencer()
