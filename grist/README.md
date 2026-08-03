# grist

Ce dossier contient le client HTTP pour l'API Grist, extrait de
`grist_processor_working_all.py` pour centraliser la responsabilité
d'interaction avec Grist.

## Contenu

- `client.py` : classe `GristClient` (interactions API Grist : tables, enregistrements,
  métadonnées de synchro, SCIM `/Me`).

## Dépendances

- `utils.log` pour les fonctions de log partagées.
