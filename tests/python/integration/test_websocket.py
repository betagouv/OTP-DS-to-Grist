"""Test d'intégration WebSocket — détecte les régressions silencieuses

Utilise le vrai socketio de l'application pour vérifier que le serveur
accepte les connexions clients. Échoue si une incompatibilité de version
(Flask / flask-socketio) casse le pipeline SocketIO.
"""


def test_real_app_socketio_accepts_connection():
    """Le socketio réel accepte une connexion client — détecte régression Flask
    vs flask-socketio (AttributeError: 'session' property has no setter)"""
    from app import app
    from utils.socketio import socketio

    app.config["TESTING"] = True
    client = socketio.test_client(app)
    assert client.is_connected()
    client.disconnect()


def test_real_app_socketio_emit_and_receive():
    """Après connexion, une émission serveur est reçue par le client"""
    from app import app
    from utils.socketio import socketio

    app.config["TESTING"] = True
    client = socketio.test_client(app)

    with app.app_context():
        socketio.emit("task_update", {"task_id": "test-123"})

    received = client.get_received()
    assert len(received) == 1
    assert received[0]["name"] == "task_update"
    assert received[0]["args"][0]["task_id"] == "test-123"
    client.disconnect()
