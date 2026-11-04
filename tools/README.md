# Outils d'exploitation

Ce dossier regroupe des outils en ligne de commande, lancés en local, pour observer
et dépanner les instances déployées (production, test). Ils ne font pas partie de
l'application : `app.py` ne les charge jamais.

## Instances Scalingo

Une instance est désignée par un nom court (`prod`, `test`…). Son application et sa
région Scalingo viennent de l'environnement (`.env`, non versionné), jamais du code
ni de la documentation :

```
SCALINGO_<INSTANCE>_APP=<nom de l'application Scalingo>
SCALINGO_<INSTANCE>_REGION=<région, vide pour la région par défaut de la CLI>
```

Ajouter une instance revient à ajouter ces deux variables. L'agent opencode `@logs`
s'appuie sur la même convention.

## `poe inspect`

Rassemble ce que la base sait d'une adresse IP (`--ip`), d'une configuration
(`--config`) ou d'une démarche (`--demarche`) : état de blocage, réglages et planning
des configurations, synchros des dernières 24 h, et lien entre IP et configurations.
Les secrets ne sont jamais affichés.

Le lien IP ↔ configuration vient de la table `otp_config_ips` (dernière utilisation
après authentification, voir `configuration/README.md`) et, avec `--app`, des requêtes
des logs dont l'URL porte un `otp_config_id`, refusées comprises. Sur une instance où
la migration de cette table n'est pas encore appliquée, seuls les logs servent, et un
avertissement le signale.

Avec `--app`, les logs d'accès gunicorn de l'instance sont aussi lus (24 dernières
heures par défaut, `--since 30m|4h|2d` ; `--errors` pour les seules réponses 4xx et
5xx) : requêtes, dernière requête et refus (401/403) par IP et par configuration. Les
logs ne portent l'IP du client que si l'instance définit `GUNICORN_CMD_ARGS` (format
décrit dans `tools/access_log.py`).

Sans `--app`, la base locale (`DATABASE_URL`) est interrogée. Avec `--app <instance>`,
l'outil ouvre lui-même un tunnel `scalingo db-tunnel` vers la base de l'instance et le
referme à la fin. La connexion est en lecture seule : toute écriture est refusée
par PostgreSQL. La CLI `scalingo` doit être installée et authentifiée.
