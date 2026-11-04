# Configuration

Ce dossier contient la gestion centralisée de la configuration de l'application.

## Rôle

Permet de gérer la configuration utilisateur depuis la base de données, avec chiffrement des données sensibles.
À découper si besoin dans ce même dossier.

## Utilisation

La configuration est liée à un utilisateur Grist (`grist_user_id`) et un document (`grist_doc_id`).
Cela permet à plusieurs utilisateurs d'avoir leur propre configuration pour le même document.
     1	
     2	## Utilisation des configurations par IP
     3	
     4	Pour l'exploitation (`poe inspect`, voir `tools/`), l'application retient quelle IP
     5	a utilisé quelle configuration, et la date du dernier passage (table
     6	`otp_config_ips`, une ligne par couple). Un passage est noté au chargement des
     7	configurations, à la création d'une configuration et au lancement d'une
     8	synchronisation manuelle, seulement après une authentification réussie : les
     9	accès refusés n'apparaissent que dans les logs.
    10	
    11	Un même couple n'est réécrit qu'au bout de 4 h (mémoire du process), et un échec
    12	d'écriture ne fait jamais échouer la requête. La suppression d'une configuration
    13	supprime ses couples.
