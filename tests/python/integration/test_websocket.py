"""Test d'intégration WebSocket — détecte les régressions silencieuses

Utilise le vrai socketio de l'application pour vérifier que le serveur
accepte les connexions clients. Échoue si une incompatibilité de version
(Flask / flask-socketio) casse le pipeline SocketIO.
"""


def test_real_app_socketio_accepts_connection():
    """Le socketio réel accepte une connexion client — détecte régression Flask
    vs flask-socketio (AttributeError: 'session' property has no setter)"""
    from app import app
    from sync.live_tracking import socketio

    app.config["TESTING"] = True
    client = socketio.test_client(app)
    assert client.is_connected()
    client.disconnect()


def test_real_app_socketio_emit_and_receive():
    """Après connexion, une émission serveur est reçue par le client"""
    from app import app
    from sync.live_tracking import socketio

    app.config["TESTING"] = True
    client = socketio.test_client(app)

    with app.app_context():
        socketio.emit("task_update", {"task_id": "test-123"})

    received = client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "task_update"
    assert received[0]["args"][0]["task_id"] == "test-123"
    client.disconnect()


class TestSyncState:
    """Message sync_state : état complet renvoyé en accusé de réception."""

    def setup_method(self):
        from app import app, sync_manager
        from sync.live_tracking import socketio

        app.config["TESTING"] = True
        # Instance réelle de l'application : le handler la reçoit à l'init
        self.manager = sync_manager
        self.created_task_ids = []
        self.client = socketio.test_client(app)

    def teardown_method(self):
        self.client.disconnect()
        for task_id in self.created_task_ids:
            self.manager._remove_task(task_id)

    def _create_task(self, config=None):
        task_id = self.manager._create_task(
            status="running", message="Initialisation...", config=config
        )
        self.created_task_ids.append(task_id)

        return task_id

    def _owned_config(self, user, doc):
        return {"grist_user_id": user, "grist_doc_id": doc, "demarche_number": "123"}

    def test_returns_tasks_of_user_and_document(self):
        """Seules les synchros de l'utilisateur et du document sont renvoyées"""
        mine = self._create_task(self._owned_config("userA", "docA"))
        self._create_task(self._owned_config("userB", "docA"))

        state = self.client.emit(
            "sync_state",
            {"grist_user_id": "userA", "grist_doc_id": "docA"},
            callback=True,
        )

        assert [entry["task_id"] for entry in state] == [mine]
        assert state[0]["task"]["demarche_number"] == "123"

    def test_empty_without_tasks(self):
        """Aucune synchro en cours : liste vide"""
        state = self.client.emit(
            "sync_state",
            {"grist_user_id": "userA", "grist_doc_id": "docA"},
            callback=True,
        )

        assert state == []

    def test_without_identifiers_matches_nothing(self):
        """Sans identifiants, aucune synchro, même sans propriétaire, n'est renvoyée"""
        self._create_task()

        assert self.client.emit("sync_state", None, callback=True) == []
        assert self.client.emit("sync_state", {}, callback=True) == []
