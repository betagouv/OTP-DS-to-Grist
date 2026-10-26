"""
Point d'entrée du serveur de développement (tâche `poe dev`).

Deux processus, deux rôles :

- le processus du reloader ne fait que surveiller les fichiers. Il ne patche pas
  gevent et n'importe pas l'application : sinon son fork rencontre un assert
  obsolète de `gevent.threading._ForkHooks`, qui pollue les logs sans conséquence ;
- le processus qui sert réellement l'appli applique `gevent.monkey.patch_all()`
  avant d'importer `app`, comme le fait gunicorn avec `--worker-class gevent`.

C'est cet ordre qui garantit que le séquenceur (`sync.sequencer`) instancie ses
verrous et son pool de threads avec des primitives déjà patchées. Sans lui, le
séquenceur est construit en `threading` natif puis mélangé aux primitives gevent
au lancement du reloader : la synchro planifiée se bloque.
"""

import os

from dotenv import load_dotenv

# Même port que le bloc `__main__` d'app.py.
PORT = 5000

# .env est chargé ici, avant tout import d'app : c'est ici que la présence d'un
# reloader se décide. app.py rappellera load_dotenv plus tard sans effet
# (override=False par défaut) : les exports du shell gardent la priorité.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"


def _serve() -> None:
    """Patche gevent puis démarre le serveur, sans reloader."""
    import gevent.monkey

    gevent.monkey.patch_all()

    import logging

    from app import app, socketio

    # Désactiver les logs de werkzeug pour les requêtes statiques
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    print("🦄 One Trick Pony DS to Grist - Version Flask")
    print(f"🌐 Application disponible sur: http://localhost:{PORT}")
    print("🔌 WebSocket activé pour les mises à jour en temps réel")

    # use_reloader=False : le reloader appartient au processus parent, et
    # flask-socketio ne doit pas re-patcher un runtime déjà patché.
    socketio.run(app, host="0.0.0.0", port=PORT, debug=DEBUG, use_reloader=False)


if __name__ == "__main__":
    if DEBUG and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        # Processus parent : rechargement des fichiers seulement.
        from werkzeug._reloader import run_with_reloader

        run_with_reloader(_serve)
    else:
        _serve()
