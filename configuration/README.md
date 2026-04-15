# Configuration

Ce dossier contient la gestion centralisée de la configuration de l'application.

## Rôle

Permet de gérer la configuration utilisateur depuis la base de données, avec chiffrement des données sensibles.
À découper si besoin dans ce même dossier.

## Utilisation

La configuration est liée à un utilisateur Grist (`grist_user_id`) et un document (`grist_doc_id`).
Cela permet à plusieurs utilisateurs d'avoir leur propre configuration pour le même document.
