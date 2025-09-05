# 🦄 One Trick Pony DS to Grist - Installation Locale

## 📋 Guide d'installation et d'utilisation en local

Ce guide détaille comment installer et utiliser **One Trick Pony DS to Grist** sur votre machine locale pour le développement, les tests ou un déploiement on-premise.

## 🎯 Prérequis

### Logiciels requis
- **Python 3.9+** ([Télécharger Python](https://www.python.org/downloads/))
- **Git** ([Télécharger Git](https://git-scm.com/downloads/))
- **Un éditeur de code** (VS Code, PyCharm, etc.)

### Accès API requis
- **Compte Démarches Simplifiées** avec droits d'accès API
- **Instance Grist** accessible (grist.numerique.gouv.fr ou auto-hébergée)
- **Token API Démarches Simplifiées** valide
- **Clé API Grist** avec droits d'écriture

## 🚀 Installation

### 1. Cloner le repository

```bash
git clone https://github.com/votre-organisation/one-trick-pony-ds-grist.git
cd one-trick-pony-ds-grist
```

### 2. Utiliser l'environnement virtuel Python

```bash
# Création de l'environnement virtuel & activation (macOS/Linux)
poetry env activate
```

### 3. Installer les dépendances

```bash
poetry install --no-root
```

### 4. Configuration des variables d'environnement

Créez un fichier `.env` à la racine du projet :

```bash
cp .env.example .env
```

Éditez le fichier `.env` avec vos paramètres :

```env
# Configuration Démarches Simplifiées
DEMARCHES_API_TOKEN='VOTRE_TOKEN_DS_ICI'
DEMARCHES_API_URL='https://www.demarches-simplifiees.fr/api/v2/graphql'
DEMARCHE_NUMBER='NUMERO_DE_VOTRE_DEMARCHE'

# Configuration Grist
GRIST_BASE_URL='https://grist.numerique.gouv.fr/api'
GRIST_API_KEY='VOTRE_CLE_API_GRIST'
GRIST_DOC_ID='ID_DE_VOTRE_DOCUMENT_GRIST'

# Configuration avancée
BATCH_SIZE='100'
MAX_WORKERS='3'
PARALLEL='True'

# Filtres (optionnels)
DATE_DEPOT_DEBUT=
DATE_DEPOT_FIN=
STATUTS_DOSSIERS=
GROUPES_INSTRUCTEURS=

# Flask (développement local)
FLASK_SECRET_KEY='dev-key-change-in-production-2024'
```

## 🔑 Obtention des tokens API

### Token Démarches Simplifiées

1. **Connectez-vous** à votre compte DS administrateur
2. **Accédez** aux paramètres de votre compte
3. **Générez** un nouveau token API dans la section "Jeton d'accès"
4. **Copiez** le token généré (format : `MGQ...`)

### Clé API Grist

1. **Connectez-vous** à votre instance Grist
2. **Accédez** à votre profil utilisateur
3. **Générez** une nouvelle clé API
4. **Copiez** la clé générée (format : `17...`)

### ID Document Grist

1. **Ouvrez** votre document Grist de destination
2. **Copiez l'ID** depuis l'URL : `https://grist.../doc/ID_DOCUMENT_ICI`
3. L'ID ressemble à : `mYMMb...`

## ▶️ Lancement de l'application

### Mode développement

```bash
# Activer l'environnement virtuel si pas déjà fait
poetry env activate

# Lancer l'application
poetry run python app.py
```

L'application sera accessible sur : **http://localhost:5000**

### Mode production locale

```bash
# Variables d'environnement pour la production
export FLASK_ENV=production  # Windows: set FLASK_ENV=production

# Lancer avec gunicorn (recommandé pour la production)
pip install gunicorn
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
```

## 🎛️ Utilisation de l'interface

### 1. Page de configuration (`/`)

- **Vérifiez** que tous les paramètres sont correctement affichés
- **Testez** les connexions DS et Grist
- **Modifiez** la configuration si nécessaire (mode local uniquement)

### 2. Page d'exécution (`/execution`)

1. **Configurez les filtres** selon vos besoins :
   - Dates de dépôt (début/fin)
   - Statuts des dossiers
   - Groupes instructeurs

2. **Lancez la synchronisation**
3. **Suivez la progression** en temps réel
4. **Consultez les logs** détaillés

### 3. Page de débogage (`/debug`)

- **Vérifiez** l'état des fichiers système
- **Consultez** les variables d'environnement
- **Testez** la connectivité WebSocket

## 🔧 Configuration avancée

### Paramètres de performance

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

### Filtres par défaut

Configurez des filtres permanents dans `.env` :

```env
# Exemple : seulement les dossiers acceptés depuis janvier 2024
STATUTS_DOSSIERS='accepte'
DATE_DEPOT_DEBUT='2024-01-01'

# Exemple : groupe instructeur spécifique
GROUPES_INSTRUCTEURS='120400'
```

## 🐛 Dépannage

### Problèmes courants

#### Erreur : "Module not found"
```bash
# Solution : Vérifier l'environnement virtuel
pip list
pip install -r requirements.txt
```

#### Erreur : "Token invalid"
```bash
# Solutions :
# 1. Vérifier la validité du token DS
# 2. Vérifier les droits d'accès à la démarche
# 3. Régénérer le token si expiré
```

#### Erreur : "Document not found" (Grist)
```bash
# Solutions :
# 1. Vérifier l'ID du document Grist
# 2. Vérifier les droits d'accès au document
# 3. Vérifier que la clé API est valide
```

#### Application lente/timeout
```bash
# Solutions :
# 1. Réduire BATCH_SIZE dans .env
# 2. Réduire MAX_WORKERS dans .env
# 3. Vérifier la connexion internet
# 4. Augmenter les timeouts dans le code
```

### Logs de débogage

Activez les logs détaillés :

```python
# Dans app.py, modifier le niveau de log
logging.basicConfig(level=logging.DEBUG)
```

### Tests de connectivité

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

## 🔄 Mise à jour

### Mise à jour du code

```bash
# Récupérer les dernières modifications
git pull origin main

# Mettre à jour les dépendances
pip install -r requirements.txt --upgrade

# Redémarrer l'application
python app.py
```

### Sauvegarde de la configuration

```bash
# Sauvegarder votre fichier .env
cp .env .env.backup

# Ou versioning avec Git (ATTENTION : exclure les tokens)
git add .env.example
git commit -m "Mise à jour configuration exemple"
```

## 📁 Structure des fichiers

```
one-trick-pony-ds-grist/
├── app.py                          # Application Flask principale
├── grist_processor_working_all.py  # Moteur de traitement
├── queries.py                      # Module de requêtes
├── queries_*.py                    # Modules spécialisés
├── repetable_processor.py          # Traitement blocs répétables
├── schema_utils.py                 # Gestion des schémas
├── requirements.txt                # Dépendances Python
├── .env                           # Configuration locale (À CRÉER)
├── .env.example                   # Exemple de configuration
├── .gitignore                     # Fichiers ignorés par Git
└── templates/                     # Templates HTML
    ├── base.html                  # Template de base
    ├── index.html                 # Page configuration
    ├── execution.html             # Page exécution
    └── debug.html                 # Page débogage
```

## 🚀 Déploiement on-premise

### Avec Docker (optionnel)

Créez un `Dockerfile` :

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"]
```

Build et run :

```bash
docker build -t ds-to-grist .
docker run -p 5000:5000 --env-file .env ds-to-grist
```

### Avec systemd (Linux)

Créez un service systemd :

```ini
# /etc/systemd/system/ds-to-grist.service
[Unit]
Description=DS to Grist Sync Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/one-trick-pony-ds-grist
Environment=PATH=/path/to/one-trick-pony-ds-grist/venv/bin
EnvironmentFile=/path/to/one-trick-pony-ds-grist/.env
ExecStart=/path/to/one-trick-pony-ds-grist/venv/bin/gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Activation :

```bash
sudo systemctl daemon-reload
sudo systemctl enable ds-to-grist
sudo systemctl start ds-to-grist
```

### Développement local

- **Logs** : Consultez la console pour les erreurs
- **Debug** : Utilisez la page `/debug` pour diagnostiquer
- **Tests** : Testez chaque composant individuellement

### Communauté

- **Code source** : DRAAF Occitanie - Licence ouverte avec citation

---

**Prochaines étapes :**
1. Testez la synchronisation avec quelques dossiers
2. Ajustez les paramètres selon vos besoins
3. Explorez les données dans Grist
4. Configurez des synchronisations automatiques

---

*Développé par la DRAAF Occitanie - Version locale*
