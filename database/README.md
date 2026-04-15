# Base de données

Ce dossier contient la gestion de la base de données PostgreSQL.

## Rôle

Permet de gérer la configuration utilisateur et l'historique des synchronisations.

## Tables

- `otp_configurations` : Configuration de chaque utilisateur (tokens, filtres)
- `user_schedules` : Planification des synchronisations automatiques
- `sync_logs` : Historique des executions de synchronisation
