
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

```env
# Configuration avancée
BATCH_SIZE='100'
MAX_WORKERS='3'
PARALLEL='True'
# 0=minimal, 1=normal, 2=verbose
LOG_LEVEL=1

# Flask
FLASK_SECRET_KEY=
# True = dev, False = prod
FLASK_DEBUG=False

DATABASE_URL=postgresql://user<:mot de passe ou vide>@host:port/db_name
ENCRYPTION_KEY='encrypt-key'
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

1. Assurez-vous que votre fichier `.env` contient la variable `DOCKER_DATABASE_URL` :

```bash
# Vérifiez que cette ligne existe dans votre fichier .env
DOCKER_DATABASE_URL=postgresql://otp_user:otp_password@db:5432/otp_ds
```

2. Lancer les services (PostgreSQL + Application) :

```bash
docker-compose up app
```

3. Pour arrêter les services :

```bash
docker-compose down
```

### Notes

- **PostgreSQL** : Lancé automatiquement via Docker (port 5433 vers le conteneur)
- **Logs** : Affichés dans le terminal

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
