
# 🚀 Déploiement

## Sur scalingo

1. Créer un add-on Postgres
    1. Depuis l'onglet Overview, dans la section Addons, cliquez sur Manage, puis Add an addon et enfin choisissez Postgresql et le reste des options
2. Via git push
    1. Avoir une [clé publique ssh](https://doc.scalingo.com/platform/getting-started/setup-ssh-linux) dans le [compte utilisateur scalingo](https://dashboard.scalingo.com/account/keys)
    2. Ajouter la remote (ici nommé `scalingo`) : `git remote add scalingo <url-du-dépot-distant-de-scalingo>`
        1. Pour trouver l'url, rendez-vous dans l'onglet deploy, section Configuration
    4. Récupérer les informations du dépôt scalingo distant : `git fetch scalingo`
    3. Pousser / déployer la référence locale : `git push scalingo <branch-local>:main`

Via github : ❌ Pas les droits pour pointer la bonne organisation pour l'instant

Ajouter les variables d'environnement :

* ENCRYPTION_KEY
* FLASK_SECRET_KEY
* LOG_LEVEL
* DATABASE_URL (**automatiquement renseigné par Scalingo**)
* SCALINGO_POSTGRESQL_URL (**automatiquement renseigné par Scalingo**)
* GRIST_BASE_URL_WHITELIST

### Liste blanche des instances Grist

`GRIST_BASE_URL_WHITELIST` est **obligatoire** : l'application refuse de démarrer
si elle est absente. Elle limite les documents Grist utilisables aux domaines
autorisés.

Format : domaines séparés par des virgules. `*.suffixe` couvre tous les
sous-domaines. Le schéma, le port et le chemin sont ignorés (comparaison sur
l'hôte seul).

Valeur recommandée (instances connues du réseau) :

```
GRIST_BASE_URL_WHITELIST=*.gouv.fr,drajes.getgrist.com,grist.dataregion.fr,grist.toutatice.fr,igrist.sdis66.fr
```

### Fuseau horaire et synchronisation automatique

Les conteneurs Scalingo tournent par défaut en temps UTC. Pour que les
synchronisations automatiques s'exécutent à une heure locale cohérente,
définir :

* `TZ` : fuseau horaire système du conteneur (ex: `TZ=Europe/Paris`)
* `SYNC_TZ` : fuseau horaire utilisé pour planifier la synchronisation
  automatique (défaut `Europe/Paris`)
* `SYNC_HOUR` : heure de la synchronisation quotidienne (0-23)
* `SYNC_MINUTE` : minute de la synchronisation quotidienne (0-59)

### Note à propos de DATABASE_URL

Il est nécessaire de bien s'assurer que le protocol est bien `postgresql://` au lieu de juste `postgres://` (incompatible avec SQLAlchemy)

### Debug

Scalingo n'affiche que certaines informations par défaut. Pour avoir plus d'informations :
1. Installer le paquet [scalingo-cli](https://doc.scalingo.com/tools/cli/start)
2. Être authentifié via un token scalingo (configuration dans l'espace utilisateur) : `export SCALINGO_API_TOKEN=<le-token>`
3. Puis afficher les derniers logs : `scalingo logs -a nom-de-lapp`

Si nécessaire, *redémarrer* l'application par exemple après un changement d'environnement : `scalingo restart -a nom-de-lapp`
