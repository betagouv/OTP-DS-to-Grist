# Tests d'intégration

Tests qui assemblent les vraies pièces de l'application (application Flask,
hooks de requête, gestionnaires d'erreurs, pipeline de synchronisation,
SocketIO) et vérifient qu'elles fonctionnent ensemble.

## Rôle

Détecter ce que les tests unitaires, fonction par fonction, ne voient pas :
l'ordre d'exécution des hooks Flask, les échanges entre eux au cours d'une
même requête, le format des réponses HTTP, ou une incompatibilité entre
bibliothèques (Flask, flask-socketio).

## Conventions

- Les requêtes passent par le client de test Flask (fixture `client`), avec
  l'application réelle importée depuis `app`.
- L'authentification par jeton widget est simulée par le `conftest.py` du
  dossier : le client est authentifié pour une identité par défaut, et une
  configuration est déjà chargeable pour elle, sans accès à la base.
- Seules les dépendances externes sont remplacées (base de données, API
  Grist, Démarches numériques) : par des mocks, ou par des faux qui
  conservent un état observable quand le test vérifie un résultat final
  plutôt que la façon dont il a été obtenu.
- Ces tests ne touchent jamais une vraie base : les tests sur base réelle
  sont dans `../db/`.
