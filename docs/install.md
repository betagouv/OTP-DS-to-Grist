
# Prérequis

## Logiciels requis
- **Python 3.13+** ([Télécharger Python](https://www.python.org/downloads/))
- **Poetry** ([Guide d'installation](https://python-poetry.org/docs/#installation))
- **Postgresql** (Installé et activé) ([Télécharger Postgresql](https://www.postgresql.org/download/))
- **Git** ([Télécharger Git](https://git-scm.com/downloads/))
- **Un éditeur de code** (VS Code, PyCharm, etc.)

## Accès API requis
- **Compte Démarches Simplifiées** avec droits d'accès API
- **Instance Grist** accessible (grist.numerique.gouv.fr si vous êtes agent public, ou auto-hébergée)
- **Token API Démarches Simplifiées** valide
- **Clé API Grist** avec droits d'écriture

# Installation

## 1. Cloner le repository

```bash
git clone https://github.com/votre-organisation/one-trick-pony-ds-grist.git
cd one-trick-pony-ds-grist
```

## 2. Utiliser l'environnement virtuel Python

```bash
# Création de l'environnement virtuel & activation (macOS/Linux)
poetry env activate
```

## 3. Installer les dépendances

```bash
poetry install
poetry install --with dev # Pour profiter des outils de développement
```

## 4. Créer la base de données

```bash
createdb otp
```

## 4. Configuration des variables d'environnement

Créez un fichier `.env` à la racine du projet :

```bash
cp .env.example .env
```

Éditez le fichier `.env` avec vos paramètres.

Configuration PostgreSQL (Docker)
```env
POSTGRES_DB=db_name
POSTGRES_USER=user
POSTGRES_PASSWORD=
DOCKER_DATABASE_URL=postgresql://user@localhorst:5432/db_name
```

Configuration PostgreSQL (sans Docker)
```env
DATABASE_URL=postgresql://user<:mot de passe ou vide>@host:port/db_name
```

Configuration avancée
```env
BATCH_SIZE='100'
MAX_WORKERS='3'
PARALLEL='True'
# 0=minimal, 1=normal, 2=verbose
LOG_LEVEL=1

# Flask
FLASK_SECRET_KEY=
# True = dev, False = prod
FLASK_DEBUG=False

ENCRYPTION_KEY='encrypt-key'

# API Démarches Simplifiées
DEMARCHES_API_URL=https://www.demarches-simplifiees.fr/api/v2/graphql
DEMARCHES_API_TOKEN=VotreTokenAPI
DEMARCHE_NUMBER=123456

# API Grist
GRIST_API_KEY=VotreCleAPI
GRIST_BASE_URL=https://docs.getgrist.com/api
GRIST_DOC_ID=VotreDocID
```

### FLASK_SECRET_KEY

1. Générer un secret pour flask : `poe generate-secret`
2. Copier coller le retour de la commande dans `.env`

### ENCRYPTION_KEY

1. Générer un secret pour flask : `poe generate-encryption-key`
2. Copier coller le retour de la commande dans `.env`

# ▶️ Lancement de l'application

## Mode développement sans Docker

```bash
# Activer l'environnement virtuel si pas déjà fait
source $(poetry env info --path)/bin/activate

# Lancer l'application de développement
poe dev
```

L'application sera accessible sur : **http://localhost:5000**

### Tests

```bash
# Tests Python
poe test

# Tests JavaScript
npm run test
```

## Mode développement avec Docker

### Prérequis

- **Docker** ([Télécharger Docker](https://www.docker.com/products/docker-desktop))
- **Docker Compose** (inclus avec Docker Desktop)

### Configuration

1. Copiez le fichier d'exemple et configurez les variables d'environnement :
   ```bash
   cp .env.example .env
   ```
   Puis éditez `.env` avec vos valeurs.

> **Note importante** : Avec `network_mode: host`, le container partage le réseau de la machine hôte. Cela permet d'accéder aux services locaux (Grist sur port 8484, PostgreSQL sur port 5433) via `localhost`.

2. Lancer les services (PostgreSQL + Application) :

```bash
docker-compose up app
```

3. Pour arrêter les services :

```bash
docker-compose down
```

### Tests

```bash
# Tests Python
docker-compose run --rm app poe test

# Tests JavaScript
docker-compose run --rm app npm run test
```

### Dépannage Docker

```bash
# Rebuild de l'image après modification des dépendances
docker-compose build app

# Voir les logs en temps réel
docker-compose logs -f app

# Accéder au conteneur en interactif
docker-compose run --rm app bash
```

## Mode production locale

```bash
# Variables d'environnement pour la production
export FLASK_ENV=production  # Windows: set FLASK_ENV=production

# Lancer avec gunicorn (recommandé pour la production)
pip install gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
```

## GitHub Codespaces

Le projet peut être développé directement dans GitHub Codespaces sans installation locale.

### Configuration requise

Avant de créer un Codespace, configurez les secrets nécessaires :

1. Allez sur **https://github.com/settings/codespaces**
2. Ajoutez ces secrets :

| Secret |
|--------|
| `POSTGRES_DB` |
| `POSTGRES_USER` |
| `POSTGRES_PASSWORD` |
| `DOCKER_DATABASE_URL` |
| `ENCRYPTION_KEY` |
| `FLASK_SECRET_KEY` |

### Création d'un Codespace

1. Allez sur la page du dépôt GitHub
2. Cliquez sur le bouton **Code** → puis **Codespaces**
3. Cliquez sur **+**
4. VS Code s'ouvrira dans le navigateur avec l'environnement configuré

### Utilisation

- L'application est automatiquement lancé
- PostgreSQL est configuré et lancé automatiquement
- Les ports sont exposés (5000 pour Flask, 5433 pour PostgreSQL)
- Il est nécessaire de rendre l'url du port 5000 en Visibilité public, pour pouvoir l'utiliser comme widget
- Pour accéder à l'application, utilisez le lien dans la notification ou l'onglet "Ports"


# 🔧 Configuration avancée

## Paramètres de performance

Dans le fichier `.env`, ajustez selon votre matériel :

```env
# Traitement par lots
BATCH_SIZE='50'          # Plus petit = moins de mémoire, plus lent
                         # Plus grand = plus de mémoire, plus rapide

# Workers parallèles
MAX_WORKERS='2'          # Basé sur le nombre de cœurs CPU
                         # Recommandé : nombre de cœurs - 1

# Traitement parallèle
PARALLEL='True'          # True = plus rapide, False = séquentiel
```

## Filtres par défaut

Configurez des filtres permanents dans `.env` :

```env
# Exemple : seulement les dossiers acceptés depuis janvier 2024
STATUTS_DOSSIERS='accepte'
DATE_DEPOT_DEBUT='2024-01-01'

# Exemple : groupe instructeur spécifique
GROUPES_INSTRUCTEURS='120400'
```

# 🐛 Dépannage

## Problèmes courants

### Erreur : "Module not found"

Solution : Vérifier l'environnement virtuel

```bash
pip list
pip install -r requirements.txt
```

### Erreur : "Token invalid"

Solutions :

1. Vérifier la validité du token DS
2. Vérifier les droits d'accès à la démarche
3. Régénérer le token si expiré

### Erreur : "Document not found" (Grist)

Solutions :

1. Vérifier l'ID du document Grist
2. Vérifier les droits d'accès au document
3. Vérifier que la clé API est valide

### Application lente/timeout

Solutions :

1. Réduire BATCH_SIZE dans .env
2. Réduire MAX_WORKERS dans .env
3. Vérifier la connexion internet
4. Augmenter les timeouts dans le code

## Logs de débogage

Activez les logs détaillés :

```python
# Dans app.py, modifier le niveau de log
logging.basicConfig(level=logging.DEBUG)
```

## Tests de connectivité

```bash
# Test basique Python
python -c "import requests; print('Requests OK')"

# Test GraphQL DS
curl -H "Authorization: Bearer VOTRE_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"query": "{ demarches(first: 1) { nodes { number title } } }"}' \
     https://www.demarches-simplifiees.fr/api/v2/graphql

# Test API Grist
curl -H "Authorization: Bearer VOTRE_CLE_API" \
     https://grist.numerique.gouv.fr/api/docs/VOTRE_DOC_ID
```
