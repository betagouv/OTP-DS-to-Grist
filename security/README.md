# Sécurité

Ce dossier regroupe les protections de l'application contre les requêtes abusives et les accès non autorisés. Les mécanismes sont indépendants les uns des autres.

## Blocage des adresses IP

Une adresse IP ayant émis trop de visites répétées et suspectes est bannie temporairement. La durée du bannissement augmente à chaque récidive. Les ressources statiques ne sont pas comptées.

## Restriction des domaines Grist

L'application n'appelle que les domaines Grist déclarés dans l'environnement (variable `GRIST_BASE_URL_WHITELIST`). Toute URL de base dont le domaine n'y figure pas est refusée. Ce garde-fou est indépendant de l'authentification ; il est aussi appliqué lors de la validation du jeton widget.

## Authentification par jeton widget

L'API et les pages de l'application n'acceptent que les requêtes portant le jeton widget délivré par Grist au chargement du document (en-tête `X-Grist-Widget-Token`).

Vérifications effectuées sur chaque requête :
- l'identité portée par le jeton widget (utilisateur et document) doit correspondre à la configuration concernée par la requête ;
- un jeton widget réservé en lecture est refusé ;
- lorsqu'une clé API Grist est fournie, le serveur l'utilise pour demander à Grist l'accès au document concerné ; la clé doit donner un accès propriétaire ou éditeur sur ce document, sinon elle est refusée (une clé de compte de service invité sur le document est donc acceptée) ;
- l'URL de base Grist est soumise à la liste blanche des domaines.

Les pages HTML d'interface sont les seules servies sans jeton widget : une navigation de navigateur ne peut pas joindre l'en-tête. Toute autre route exige le jeton widget.

## Sync programmée

La synchronisation programmée est déclenchée côté serveur, en dehors de toute requête HTTP : aucune route n'y est dédiée.
