# Base de données

Ce dossier contient la gestion de la base de données PostgreSQL.

## Rôle

Permet de gérer la configuration utilisateur et l'historique des synchronisations.

Fournit la fabrique de sessions SQLAlchemy partagée par l'application : un seul
engine (et donc un seul pool de connexions) par process. Les modules ouvrent leurs
sessions via `database.session.SessionLocal` plutôt que de créer leur propre engine.

Le schéma est décrit par les modèles ORM (`database/models.py`) et appliqué par
les migrations Alembic de `migrations/` (voir son README), au déploiement et
au lancement de `poe dev`, jamais au démarrage de l'application.

## Tables

- `otp_configurations` : Configuration de chaque utilisateur (tokens, filtres)
- `user_schedules` : Planification des synchronisations automatiques
- `sync_logs` : Historique des executions de synchronisation
- `ip_blocklist` : Bannissements d'IP en cours (nombre de bannissements, fin de ban)
