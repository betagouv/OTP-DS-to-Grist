"""Tests du séquenceur de synchronisations (sync.sequencer)."""

import threading
import time

from sync.sequencer import SyncSequencer

_TIMEOUT = 10.0


def _wait_until(predicate, timeout=_TIMEOUT):
    """Attend qu'un prédicat soit vrai (borné pour éviter les tests bloqués)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("Condition non atteinte dans le délai imparti")


def _all_statuses(sequencer, expected):
    snapshot = sequencer.snapshot()
    return len(snapshot) > 0 and all(s["status"] == expected for s in snapshot)


class TestSyncSequencer:
    """Comportement du séquenceur : séquentialité, parallélisme borné, dédup."""

    def test_etapes_dun_meme_document_s_executent_sequentiellement(self):
        """Deux étapes du même document ne se chevauchent jamais."""
        sequencer = SyncSequencer()
        events = []

        def _make_step(label):
            def fn():
                events.append(f"start:{label}")
                time.sleep(0.1)
                events.append(f"end:{label}")

            return fn

        try:
            sequencer.enqueue(1, "doc_a", _make_step("1"))
            sequencer.enqueue(2, "doc_a", _make_step("2"))

            _wait_until(lambda: _all_statuses(sequencer, "done"))
            assert events == ["start:1", "end:1", "start:2", "end:2"]
        finally:
            sequencer.shutdown(wait=True)

    def test_deux_documents_distincts_s_executent_en_parallèle(self):
        """Deux documents différents avancent simultanément (barrière à 2)."""
        sequencer = SyncSequencer()
        barrier = threading.Barrier(2, timeout=_TIMEOUT)

        def fn():
            barrier.wait()

        try:
            sequencer.enqueue(1, "doc_a", fn)
            sequencer.enqueue(2, "doc_b", fn)

            _wait_until(
                lambda: all(
                    s["status"] in ("done", "error") for s in sequencer.snapshot()
                )
            )
            # Une exécution séquentielle ferait expirer la barrière -> error
            assert _all_statuses(sequencer, "done")
        finally:
            sequencer.shutdown(wait=True)

    def test_plafond_de_documents_en_parallèle(self):
        """Jamais plus de MAX_CONCURRENT_DOCS documents en exécution."""
        sequencer = SyncSequencer()
        lock = threading.Lock()
        release = threading.Event()
        running = 0
        max_running = 0

        def fn():
            nonlocal running, max_running
            with lock:
                running += 1
                max_running = max(max_running, running)
            release.wait(timeout=_TIMEOUT)
            with lock:
                running -= 1

        try:
            for config_id in (1, 2, 3):
                sequencer.enqueue(config_id, f"doc_{config_id}", fn)

            _wait_until(lambda: max_running >= 2)
            # Laisse une éventuelle 3e étape démarrer si le plafond était cassé
            time.sleep(0.3)
            assert max_running == 2

            release.set()
            _wait_until(lambda: _all_statuses(sequencer, "done"))
            assert max_running == 2
        finally:
            release.set()
            sequencer.shutdown(wait=True)

    def test_pas_de_double_enfile_pour_une_même_config(self):
        """Une config déjà en cours n'est pas remise en file ; après fin, si."""
        sequencer = SyncSequencer()
        started = threading.Event()
        release = threading.Event()

        def blocking_fn():
            started.set()
            release.wait(timeout=_TIMEOUT)

        try:
            step_id_1 = sequencer.enqueue(1, "doc_a", blocking_fn)
            _wait_until(started.is_set)

            step_id_2 = sequencer.enqueue(1, "doc_a", blocking_fn)
            assert step_id_2 == step_id_1
            assert len(sequencer.snapshot()) == 1

            release.set()
            _wait_until(lambda: _all_statuses(sequencer, "done"))

            step_id_3 = sequencer.enqueue(1, "doc_a", lambda: None)
            assert step_id_3 != step_id_1
            _wait_until(lambda: _all_statuses(sequencer, "done"))
            assert len(sequencer.snapshot()) == 2
        finally:
            release.set()
            sequencer.shutdown(wait=True)

    def test_erreur_d_une_etape_n_empêche_pas_la_suite(self):
        """Une étape en échec passe en error ; la suivante s'exécute quand même."""
        sequencer = SyncSequencer()

        def boom():
            raise RuntimeError("échec simulé")

        try:
            sequencer.enqueue(1, "doc_a", boom)
            sequencer.enqueue(2, "doc_a", lambda: None)

            _wait_until(
                lambda: all(
                    s["status"] in ("done", "error") for s in sequencer.snapshot()
                )
            )
            statuses = {
                s["otp_config_id"]: s["status"] for s in sequencer.snapshot()
            }
            assert statuses == {1: "error", 2: "done"}
        finally:
            sequencer.shutdown(wait=True)

    def test_snapshot_et_ids_parlants(self):
        """Les ids suivent le format sync_N_config_X_doc_Y ; snapshot = copie."""
        sequencer = SyncSequencer()

        try:
            step_id_1 = sequencer.enqueue(42, "grist_xyz", lambda: None)
            assert step_id_1 == "sync_1_config_42_doc_grist_xyz"
            _wait_until(lambda: _all_statuses(sequencer, "done"))

            step_id_2 = sequencer.enqueue(7, "grist_xyz", lambda: None)
            assert step_id_2 == "sync_2_config_7_doc_grist_xyz"
            _wait_until(lambda: _all_statuses(sequencer, "done"))

            snapshot = sequencer.snapshot()
            assert len(snapshot) == 2
            entry = snapshot[0]
            assert entry["step_id"] == "sync_1_config_42_doc_grist_xyz"
            assert entry["otp_config_id"] == 42
            assert entry["grist_doc_id"] == "grist_xyz"
            assert entry["enqueued_at"] is not None
            assert entry["started_at"] is not None
            assert entry["finished_at"] is not None

            entry["status"] = "tampered"
            assert sequencer.snapshot()[0]["status"] == "done"
        finally:
            sequencer.shutdown(wait=True)

    def test_shutdown_attend_les_etapes_en_cours(self):
        """shutdown(wait=True) bloque jusqu'à la fin de l'étape en cours."""
        sequencer = SyncSequencer()
        finished = threading.Event()

        def fn():
            time.sleep(0.1)
            finished.set()

        sequencer.enqueue(1, "doc_a", fn)
        sequencer.shutdown(wait=True)

        assert finished.is_set()
