# 🦄 One Trick Pony DS to Grist - Documentation Technique
# Partie 1 : Vue d'ensemble et architecture

## Vue d'ensemble du projet

**One Trick Pony DS to Grist** est une application Flask de synchronisation automatisée entre l'API Démarches Simplifiées (DS) et Grist. Le système récupère les données de démarches administratives françaises via GraphQL et les structure automatiquement dans des tableaux Grist.

### Architecture générale

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Interface Web  │────▶│  Application     │────▶│     API DS       │
│    Flask/DSFR    │     │     Flask        │     │    (GraphQL)     │
└──────────────────┘     └──────────────────┘     └──────────────────┘
                               │                            
                               ▼                            
                        ┌──────────────────┐               
                        │   Processeur     │               
                        │     Python       │               
                        └──────────────────┘               
                               │                            
                               ▼                            
                        ┌──────────────────┐               
                        │    API Grist     │               
                        │   (REST API)     │               
                        └──────────────────┘               
```

---

## 📁 Structure des fichiers du projet

### **Fichiers principaux de l'application**

1. **`app.py`** - Application Flask principale avec interface web
2. **`grist_processor_working_all.py`** - Processeur principal de synchronisation DS → Grist
3. **`requirements.txt`** - Dépendances Python du projet

### **Modules de requêtes API**

4. **`queries.py`** - Module principal d'orchestration des requêtes
5. **`queries_config.py`** - Configuration des connexions API
6. **`queries_graphql.py`** - Requêtes GraphQL vers l'API DS
7. **`queries_extract.py`** - Extraction et transformation des données
8. **`queries_util.py`** - Utilitaires pour le traitement des données

### **Modules spécialisés**

9. **`repetable_processor.py`** - Traitement des blocs répétables
10. **`schema_utils.py`** - Gestion des schémas de démarches

### **Templates HTML**

11. **`templates/base.html`** - Template de base DSFR
12. **`templates/index.html`** - Page de configuration
13. **`templates/execution.html`** - Page d'exécution et monitoring
14. **`templates/debug.html`** - Page de débogage

---

## 🏗️ Architecture détaillée des composants

### **Diagramme de flux de données**

```
[Interface Web Flask]
        ↓
[Configuration Manager] → [.env file]
        ↓
[Task Manager] → [Thread Pool]
        ↓
[Subprocess: grist_processor]
        ↓
[GraphQL Client] → [API DS]
        ↓
[Data Transformer]
        ↓
[Type Detector]
        ↓
[Grist Client] → [API Grist]
        ↓
[WebSocket Updates] → [Interface Web]
```

### **Communication inter-composants**

1. **Flask ↔ Processeur Python:**
   - Via subprocess avec environnement isolé
   - Communication par stdout/stderr
   - Parsing des logs pour progression

2. **Flask ↔ Interface Web:**
   - HTTP REST pour les données
   - WebSocket pour temps réel
   - JSON pour tous les échanges

3. **Processeur ↔ APIs externes:**
   - HTTPS avec authentification Bearer
   - Retry avec backoff exponentiel
   - Timeout configurables

---

## 🔄 Flux de traitement détaillé

### **Phase 1 : Initialisation et configuration**

1. **Chargement de l'environnement :**
   - `load_dotenv()` charge le fichier `.env`
   - Variables mappées : `DEMARCHES_API_TOKEN`, `GRIST_API_KEY`, etc.
   - Validation des paramètres requis

2. **Test de configuration :**
   - Requête GraphQL minimale vers DS
   - GET sur `/docs/{doc_id}` pour Grist
   - Vérification des permissions

### **Phase 2 : Récupération des données DS**

1. **Récupération de la démarche :**
   ```python
   demarche_data = get_demarche(demarche_number)
   ```
   - Requête GraphQL avec fragments
   - Récupère métadonnées et liste des dossiers
   - Pagination automatique si > 100

2. **Application des filtres (si configurés) :**
   - Conversion des filtres UI en format API
   - `DATE_DEPOT_DEBUT` → `createdSince` (ISO 8601)
   - `STATUTS_DOSSIERS` → `states` (array)
   - Utilisation de `get_demarche_dossiers_filtered()`

3. **Récupération détaillée par batch :**
   ```python
   for batch in batches:
       for dossier_number in batch:
           dossier = get_dossier(dossier_number)
   ```
   - Division en lots de 25-100 dossiers
   - Requêtes parallèles si activé
   - Gestion des timeouts et retry

### **Phase 3 : Détection et création de structure**

1. **Méthode avancée (schema_utils) :**
   ```python
   schema = get_demarche_schema(demarche_number)
   columns = create_columns_from_schema(schema)
   ```
   - Récupère les descripteurs sans données
   - Génère la structure complète
   - Plus rapide et plus fiable

2. **Méthode classique (échantillonnage) :**
   ```python
   columns = detect_column_types(sample_dossiers, problematic_ids)
   ```
   - Analyse 3 dossiers échantillons
   - Détecte les types par inspection
   - Fallback si schema_utils échoue

3. **Création des tables Grist :**
   - Table `dossiers` : Métadonnées principales
   - Table `champs` : Valeurs des champs
   - Table `annotations` : Notes des instructeurs
   - Table `repetable_rows` : Blocs répétables (si détectés)

### **Phase 4 : Transformation et insertion**

1. **Transformation des données :**
   ```python
   flat_data = dossier_to_flat_data(dossier, problematic_ids)
   ```
   - Sépare en 4 structures distinctes
   - Normalise les noms de colonnes
   - Convertit les types de données

2. **Insertion optimisée :**
   - Skip des dossiers déjà traités
   - Insertion par batch de 100-500 records
   - Parallélisation avec ThreadPoolExecutor
   - Retry automatique en cas d'échec

3. **Gestion des cas spéciaux :**
   - **Blocs répétables :** Table séparée avec index
   - **Champs géographiques :** GeoJSON en texte
   - **Fichiers :** URLs et métadonnées
   - **Labels :** JSON array en texte

### **Phase 5 : Monitoring et reporting**

1. **Logs en temps réel :**
   - WebSocket pour mises à jour instantanées
   - Buffer de 1000 lignes maximum
   - Horodatage de chaque message

2. **Indicateurs de progression :**
   - Pourcentage global
   - Nombre de dossiers traités
   - Temps écoulé/restant estimé

3. **Rapport final :**
   - Total succès/échecs
   - Durée totale
   - Erreurs détaillées si présentes

---

## 📊 Structure des données

### **Table `dossiers`**

| Colonne | Type | Description |
|---------|------|-------------|
| dossier_id | Text | ID unique GraphQL |
| number | Int | Numéro du dossier |
| state | Text | État (en_construction, etc.) |
| date_depot | DateTime | Date de dépôt |
| date_derniere_modification | DateTime | Dernière modification |
| date_traitement | DateTime | Date de traitement |
| demandeur_type | Text | PersonnePhysique/Morale |
| demandeur_nom | Text | Nom du demandeur |
| demandeur_prenom | Text | Prénom |
| demandeur_email | Text | Email |
| demandeur_siret | Text | SIRET entreprise |
| entreprise_raison_sociale | Text | Raison sociale |
| groupe_instructeur_label | Text | Nom du groupe |
| supprime_par_usager | Bool | Dossier supprimé |
| labels_json | Text | Labels en JSON |

### **Table `champs`**

| Colonne | Type | Description |
|---------|------|-------------|
| dossier_number | Int | Référence au dossier |
| champ_id | Text | ID du descripteur |
| [colonnes dynamiques] | Variable | Une colonne par champ détecté |

### **Table `annotations`**

| Colonne | Type | Description |
|---------|------|-------------|
| dossier_number | Int | Référence au dossier |
| [colonnes dynamiques] | Variable | Une colonne par annotation |

### **Table `repetable_rows`**

| Colonne | Type | Description |
|---------|------|-------------|
| dossier_number | Int | Référence au dossier |
| block_label | Text | Nom du bloc répétable |
| block_row_index | Int | Index de la ligne (0, 1, 2...) |
| block_row_id | Text | ID unique de la ligne |
| [colonnes dynamiques] | Variable | Champs du bloc |

---

## 🛠️ Mécanismes d'optimisation

### **1. Cache de colonnes**

```python
class ColumnCache:
    def __init__(self, client):
        self.columns_cache = {}  # {table_id: {column_id: column_type}}
```

- Évite les requêtes répétées à l'API Grist
- Rafraîchissement forcé disponible
- Réduit la latence de 50-70%

### **2. Détection incrémentale**

```python
existing_numbers = client.get_existing_dossier_numbers("dossiers")
new_dossiers = [d for d in dossiers if d["number"] not in existing_numbers]
```

- Récupère les dossiers déjà traités
- Skip automatique des doublons
- Permet les reprises après interruption

### **3. Traitement par lots (batching)**

```python
for i in range(0, len(dossiers), batch_size):
    batch = dossiers[i:i+batch_size]
    process_batch(batch)
```

- Réduit le nombre d'appels API
- Optimise l'utilisation mémoire
- Configurable via `BATCH_SIZE`

### **4. Parallélisation ThreadPool**

```python
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = [executor.submit(process_dossier, d) for d in batch]
    results = [f.result() for f in as_completed(futures)]
```

- Traitement concurrent des dossiers
- Configurable via `MAX_WORKERS`
- Amélioration 2-3x des performances

### **5. Filtrage côté serveur**

```python
filters = {
    "createdSince": "2024-01-01T00:00:00Z",
    "states": ["en_instruction", "accepte"]
}
```

- Réduit le volume de données transférées
- Filtre directement dans GraphQL
- Économise bande passante et temps

### **6. Gestion d'erreurs granulaire**

```python
for dossier in batch:
    try:
        process_dossier(dossier)
        success_count += 1
    except Exception as e:
        log_error(f"Dossier {dossier['number']}: {e}")
        failed_dossiers.add(dossier['number'])
        continue
```

- Continue même si un dossier échoue
- Tracking détaillé des échecs
- Permet le retraitement ciblé

# Partie 2 : Application Flask et interface web

## 1. **`app.py`** - Serveur Flask et orchestrateur principal

**Rôle :** Serveur web Flask qui fournit l'interface utilisateur et orchestre la synchronisation.

### **Imports et configuration initiale**
```python
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv, set_key
```
- Configure Flask avec une clé secrète pour les sessions
- Initialise SocketIO pour la communication temps réel
- Charge les variables d'environnement depuis `.env`

### **Classe `TaskManager`**
Gère l'exécution asynchrone des tâches de synchronisation :

#### **`__init__()`**
```python
def __init__(self):
    self.tasks = {}
    self.task_counter = 0
```
Initialise le dictionnaire des tâches et un compteur global.

#### **`start_task(task_function, *args, **kwargs)`**
```python
def start_task(self, task_function, *args, **kwargs):
    self.task_counter += 1
    task_id = f"task_{self.task_counter}"
    
    self.tasks[task_id] = {
        'status': 'running',
        'progress': 0,
        'message': 'Initialisation...',
        'start_time': time.time(),
        'logs': []
    }
    
    thread = threading.Thread(
        target=self._run_task,
        args=(task_id, task_function, *args),
        kwargs=kwargs
    )
    thread.start()
    return task_id
```
- Crée un identifiant unique pour la tâche
- Initialise la structure de suivi
- Démarre un thread séparé pour l'exécution
- Retourne l'ID pour le suivi client

#### **`_run_task(task_id, task_function, *args, **kwargs)`**
```python
def _run_task(self, task_id, task_function, *args, **kwargs):
    try:
        kwargs['progress_callback'] = lambda p, m: self._update_progress(task_id, p, m)
        kwargs['log_callback'] = lambda m: self._add_log(task_id, m)
        
        result = task_function(*args, **kwargs)
        
        self.tasks[task_id].update({
            'status': 'completed',
            'progress': 100,
            'message': 'Tâche terminée avec succès',
            'result': result,
            'end_time': time.time()
        })
    except Exception as e:
        self.tasks[task_id].update({
            'status': 'error',
            'message': f'Erreur: {str(e)}',
            'error': str(e),
            'end_time': time.time()
        })
    finally:
        self._emit_update(task_id)
```
- Exécute la fonction dans le thread
- Capture les callbacks de progression et de log
- Met à jour le statut (running → completed/error)
- Gère les exceptions et les stocke

#### **`_update_progress(task_id, progress, message)`**
Met à jour le pourcentage de progression et émet via WebSocket.

#### **`_add_log(task_id, message)`**
```python
def _add_log(self, task_id, message):
    if task_id in self.tasks:
        self.tasks[task_id]['logs'].append({
            'timestamp': time.time(),
            'message': message
        })
        # Limiter à 1000 lignes de log
        if len(self.tasks[task_id]['logs']) > 1000:
            self.tasks[task_id]['logs'] = self.tasks[task_id]['logs'][-1000:]
        self._emit_update(task_id)
```

#### **`_emit_update(task_id)`**
Envoie l'état complet de la tâche via WebSocket à tous les clients connectés.

### **Classe `ConfigManager`**
Gère la configuration persistante :

#### **`load_config()`**
```python
@staticmethod
def load_config():
    load_dotenv(ConfigManager.get_env_path(), override=True)
    
    config = {
        'ds_api_token': os.getenv('DEMARCHES_API_TOKEN', ''),
        'ds_api_url': os.getenv('DEMARCHES_API_URL', 'https://...'),
        'demarche_number': os.getenv('DEMARCHE_NUMBER', ''),
        'grist_base_url': os.getenv('GRIST_BASE_URL', ''),
        'grist_api_key': os.getenv('GRIST_API_KEY', ''),
        'grist_doc_id': os.getenv('GRIST_DOC_ID', ''),
        'batch_size': int(os.getenv('BATCH_SIZE', '25')),
        'max_workers': int(os.getenv('MAX_WORKERS', '2')),
        'parallel': os.getenv('PARALLEL', 'True').lower() == 'true'
    }
    return config
```
- Recharge le fichier `.env` avec `override=True`
- Convertit les types (string → int pour batch_size, etc.)
- Retourne un dictionnaire avec toutes les configurations

#### **`save_config(config)`**
```python
@staticmethod
def save_config(config):
    env_path = ConfigManager.get_env_path()
    
    # Créer le fichier s'il n'existe pas
    if not os.path.exists(env_path):
        with open(env_path, 'w') as f:
            f.write("# Configuration DS to Grist\n\n")
    
    # Mapping des clés
    env_mapping = {
        'ds_api_token': 'DEMARCHES_API_TOKEN',
        'ds_api_url': 'DEMARCHES_API_URL',
        'demarche_number': 'DEMARCHE_NUMBER',
        'grist_base_url': 'GRIST_BASE_URL',
        'grist_api_key': 'GRIST_API_KEY',
        'grist_doc_id': 'GRIST_DOC_ID',
        'batch_size': 'BATCH_SIZE',
        'max_workers': 'MAX_WORKERS',
        'parallel': 'PARALLEL'
    }
    
    for key, env_key in env_mapping.items():
        if key in config:
            value = str(config[key])
            set_key(env_path, env_key, value)
    
    return True
```

#### **`test_config(config)`**
```python
@staticmethod
def test_config(config):
    results = {}
    
    # Test connexion DS
    try:
        query = '{ demarche(number: %s) { id } }' % config['demarche_number']
        response = requests.post(
            config['ds_api_url'],
            json={"query": query},
            headers={"Authorization": f"Bearer {config['ds_api_token']}"},
            timeout=10
        )
        results['ds'] = {
            'success': response.status_code == 200,
            'message': 'Connexion réussie' if response.status_code == 200 
                      else f'Erreur {response.status_code}'
        }
    except Exception as e:
        results['ds'] = {'success': False, 'message': str(e)}
    
    # Test connexion Grist
    try:
        url = f"{config['grist_base_url']}/docs/{config['grist_doc_id']}"
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {config['grist_api_key']}"},
            timeout=10
        )
        results['grist'] = {
            'success': response.status_code == 200,
            'message': 'Connexion réussie' if response.status_code == 200 
                      else f'Erreur {response.status_code}'
        }
    except Exception as e:
        results['grist'] = {'success': False, 'message': str(e)}
    
    return results
```

### **Fonction `run_synchronization_task(config, filters)`**
Exécute le processeur Python externe :

```python
def run_synchronization_task(config, filters, progress_callback=None, log_callback=None):
    script_path = os.path.join(script_dir, "grist_processor_working_all.py")
    
    # Copie de l'environnement pour isolation
    env_copy = os.environ.copy()
    
    # Configuration des variables d'environnement
    env_copy['DEMARCHES_API_TOKEN'] = config['ds_api_token']
    env_copy['DEMARCHES_API_URL'] = config['ds_api_url']
    env_copy['DEMARCHE_NUMBER'] = str(config['demarche_number'])
    env_copy['GRIST_BASE_URL'] = config['grist_base_url']
    env_copy['GRIST_API_KEY'] = config['grist_api_key']
    env_copy['GRIST_DOC_ID'] = config['grist_doc_id']
    env_copy['BATCH_SIZE'] = str(config.get('batch_size', 25))
    env_copy['MAX_WORKERS'] = str(config.get('max_workers', 2))
    env_copy['PARALLEL'] = str(config.get('parallel', True))
    
    # Gestion des filtres
    if filters.get('date_depot_debut'):
        env_copy['DATE_DEPOT_DEBUT'] = filters['date_depot_debut']
    if filters.get('date_depot_fin'):
        env_copy['DATE_DEPOT_FIN'] = filters['date_depot_fin']
    if filters.get('statuts_dossiers'):
        env_copy['STATUTS_DOSSIERS'] = ','.join(filters['statuts_dossiers'])
    if filters.get('groupes_instructeurs'):
        env_copy['GROUPES_INSTRUCTEURS'] = ','.join(map(str, filters['groupes_instructeurs']))
    
    # Création des filtres API optimisés
    api_filters = {}
    if filters.get('date_depot_debut'):
        api_filters['createdSince'] = f"{filters['date_depot_debut']}T00:00:00Z"
    if filters.get('date_depot_fin'):
        api_filters['createdUntil'] = f"{filters['date_depot_fin']}T23:59:59Z"
    if filters.get('statuts_dossiers'):
        api_filters['states'] = filters['statuts_dossiers']
    
    env_copy['API_FILTERS_JSON'] = json.dumps(api_filters)
    
    # Lancer le processus
    process = subprocess.Popen(
        [sys.executable, script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env_copy,
        cwd=script_dir
    )
    
    # Parsing de la progression
    progress_keywords = {
        "Récupération de la démarche": (15, "Récupération des données..."),
        "Démarche trouvée": (20, "Analyse des données..."),
        "Nombre de dossiers trouvés": (25, "Préparation du traitement..."),
        "Types de colonnes détectés": (35, "Analyse de la structure..."),
        "Table dossiers": (45, "Création des tables Grist..."),
        "Table champs": (50, "Configuration des champs..."),
        "Traitement du lot": (60, "Traitement des dossiers..."),
        "Dossiers traités avec succès": (90, "Finalisation..."),
        "Traitement terminé": (100, "Terminé!")
    }
    
    # Lecture ligne par ligne
    for line in process.stdout:
        if log_callback:
            log_callback(line.strip())
        
        # Détection de progression
        for keyword, (progress, message) in progress_keywords.items():
            if keyword in line:
                if progress_callback:
                    progress_callback(progress, message)
                break
        
        # Pattern [XX%]
        percent_match = re.search(r'\[(\d+)%\]', line)
        if percent_match:
            percent = int(percent_match.group(1))
            if progress_callback:
                progress_callback(percent, f"Progression: {percent}%")
    
    returncode = process.wait()
    
    if returncode == 0:
        return {"success": True, "message": "Synchronisation terminée avec succès"}
    else:
        return {"success": False, "message": f"Erreur lors du traitement (code {returncode})"}
```

### **Routes HTTP**

#### **`GET /` - Page de configuration**
```python
@app.route('/')
def index():
    config = ConfigManager.load_config()
    return render_template('index.html', config=config)
```

#### **`GET/POST /api/config` - API de configuration**
```python
@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'GET':
        config = ConfigManager.load_config()
        # Masquer les tokens pour l'affichage
        if config['ds_api_token']:
            config['ds_api_token_masked'] = '***'
            config['ds_api_token_exists'] = True
        else:
            config['ds_api_token_masked'] = ''
            config['ds_api_token_exists'] = False
        return jsonify(config)
    
    else:  # POST
        data = request.json
        # Validation et nettoyage
        if 'demarche_number' in data:
            try:
                data['demarche_number'] = int(data['demarche_number'])
            except:
                return jsonify({"error": "Numéro de démarche invalide"}), 400
        
        # Sauvegarde
        if ConfigManager.save_config(data):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Erreur de sauvegarde"}), 500
```

#### **`POST /api/sync` - Démarrage de synchronisation**
```python
@app.route('/api/sync', methods=['POST'])
def api_sync():
    # Vérification de la configuration
    server_config = ConfigManager.load_config()
    
    if not all([
        server_config.get('ds_api_token'),
        server_config.get('demarche_number'),
        server_config.get('grist_api_key'),
        server_config.get('grist_doc_id')
    ]):
        return jsonify({"error": "Configuration incomplète"}), 400
    
    # Récupération des filtres
    filters = request.json.get('filters', {})
    
    # Application des filtres dans l'environnement
    for key, value in filters.items():
        if value:
            os.environ[key.upper()] = str(value)
    
    # Démarrage de la tâche
    task_id = task_manager.start_task(
        run_synchronization_task, 
        server_config, 
        filters
    )
    
    return jsonify({
        "success": True,
        "task_id": task_id,
        "demarche_number": server_config['demarche_number']
    })
```

#### **`GET /api/task/<task_id>` - Statut d'une tâche**
```python
@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    task = task_manager.get_task(task_id)
    if task:
        return jsonify(task)
    else:
        return jsonify({"error": "Tâche non trouvée"}), 404
```

#### **`GET /debug` - Page de débogage**
```python
@app.route('/debug')
def debug():
    # Vérifier les fichiers requis
    required_files = [
        "grist_processor_working_all.py",
        "queries.py",
        "queries_config.py",
        # ...
    ]
    
    file_status = {}
    for file in required_files:
        file_path = os.path.join(script_dir, file)
        file_status[file] = os.path.exists(file_path)
    
    # Variables d'environnement masquées
    env_vars = {
        "DEMARCHES_API_TOKEN": "***" if os.getenv("DEMARCHES_API_TOKEN") else "Non défini",
        # ...
    }
    
    return render_template('debug.html', 
                          file_status=file_status,
                          env_vars=env_vars,
                          script_dir=script_dir)
```

### **Handlers WebSocket**

```python
@socketio.on('connect')
def handle_connect():
    logger.info('Client connecté')
    emit('connected', {'data': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client déconnecté')
```

---

## 2. Templates HTML

### **`templates/base.html`** - Template de base

Structure HTML avec Design System de l'État (DSFR) :

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>{% block title %}🦄 One Trick Pony DS to Grist{% endblock %}</title>
    
    <!-- DSFR CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@gouvfr/


# Partie 3 : Processeur principal et synchronisation

## **`grist_processor_working_all.py`** - Processeur de synchronisation

**Rôle :** Script principal qui extrait les données de DS et les insère dans Grist.

### **Configuration et logging**

```python
LOG_LEVEL = 1  # 0=minimal, 1=normal, 2=verbose

def log(message, level=1):
    """Fonction de log conditionnelle selon le niveau défini"""
    if level <= LOG_LEVEL:
        print(message)

def log_verbose(message):
    """Log uniquement en mode verbose"""
    log(message, 2)

def log_error(message):
    """Log d'erreur (toujours affiché)"""
    print(f"ERREUR: {message}")
```

### **Fonction `normalize_column_name(name, max_length=50)`**

Normalise les noms de colonnes pour Grist :

```python
def normalize_column_name(name, max_length=50):
    """
    Normalise un nom de colonne pour Grist en garantissant des identifiants valides.
    """
    if not name:
        return "column"
    
    # 1. Supprimer les espaces de début/fin et espaces multiples
    import re
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)
    
    # 2. Supprimer les accents
    import unicodedata
    name = unicodedata.normalize('NFKD', name)
    name = ''.join([c for c in name if not unicodedata.combining(c)])
    
    # 3. Convertir en minuscules et remplacer les caractères spéciaux
    name = name.lower()
    name = re.sub(r'[^a-z0-9_]', '_', name)
    
    # 4. Éliminer les underscores multiples consécutifs
    name = re.sub(r'_+', '_', name)
    
    # 5. Éliminer les underscores en début et fin
    name = name.strip('_')
    
    # 6. S'assurer que le nom commence par une lettre
    if not name or not name[0].isalpha():
        name = "col_" + (name or "")
    
    # 7. Tronquer si nécessaire avec hash pour unicité
    if len(name) > max_length:
        import hashlib
        hash_part = hashlib.md5(name.encode()).hexdigest()[:6]
        name = f"{name[:max_length-7]}_{hash_part}"
    
    return name
```

### **Fonction `convert_value(value, column_type)`**

Convertit les valeurs selon leur type Grist :

```python
def convert_value(value, column_type):
    """Convertit une valeur selon le type de colonne Grist"""
    if value is None:
        return None
        
    if column_type == "Text":
        # Tronquer les textes trop longs
        if isinstance(value, str) and len(value) > 1000:
            return value[:1000] + "..."
        return str(value)
    
    if column_type == "Int":
        try:
            # Gérer les flottants qui devraient être des entiers
            return int(float(value)) if value else None
        except (ValueError, TypeError):
            return None
    
    if column_type == "Numeric":
        try:
            return float(value) if value else None
        except (ValueError, TypeError):
            return None
    
    if column_type == "Bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["true", "1", "yes", "oui", "vrai"]
        return bool(value)
    
    if column_type == "DateTime":
        if isinstance(value, str) and value:
            # Essayer plusieurs formats de date
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ", 
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"
            ]
            for fmt in formats:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                except ValueError:
                    continue
        return value
    
    return value
```

### **Fonction `format_value_for_grist(value, value_type)`**

Formateur spécialisé pour l'API Grist :

```python
def format_value_for_grist(value, value_type):
    """Formate une valeur pour l'insertion dans Grist selon son type"""
    if value is None:
        return None

    if value_type == "DateTime":
        if isinstance(value, str):
            if value:
                # Conversion en timestamp Unix pour Grist
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"]:
                    try:
                        dt = datetime.strptime(value, fmt)
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        continue
            return value
        return value

    if value_type == "Text":
        if isinstance(value, str) and len(value) > 1000:
            return value[:1000] + "..."
        return str(value)

    if value_type in ["Int", "Numeric"]:
        try:
            if value_type == "Int":
                return int(float(value)) if value else None
            return float(value) if value else None
        except (ValueError, TypeError):
            return None

    if value_type == "Bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ["true", "1", "yes", "oui", "vrai"]
        return bool(value)

    return value
```

### **Classe `ColumnCache`**

Cache pour optimiser les requêtes de structure :

```python
class ColumnCache:
    """Cache pour les informations sur les colonnes de tables Grist"""
    
    def __init__(self, client):
        self.client = client
        self.columns_cache = {}  # {table_id: {column_id: column_type}}
    
    def get_columns(self, table_id, force_refresh=False):
        """
        Récupère les colonnes d'une table, en utilisant le cache si disponible.
        """
        if force_refresh or table_id not in self.columns_cache:
            # Appel API pour récupérer les colonnes
            url = f"{self.client.base_url}/docs/{self.client.doc_id}/tables/{table_id}/columns"
            response = requests.get(url, headers=self.client.headers)
            
            if response.status_code == 200:
                columns_data = response.json()
                # Parse et stocke en cache
                self.columns_cache[table_id] = {
                    col['id']: col.get('type', 'Text')
                    for col in columns_data.get('columns', [])
                }
            else:
                return {}
        
        return self.columns_cache.get(table_id, {})
    
    def refresh(self, table_id):
        """Force le rafraîchissement du cache pour une table"""
        return self.get_columns(table_id, force_refresh=True)
```

### **Classe `GristClient`**

Client API pour Grist avec méthodes spécialisées :

```python
class GristClient:
    def __init__(self, base_url, api_key, doc_id=None):
        self.base_url = base_url.rstrip('/')  # Enlever le / final
        self.api_key = api_key
        self.doc_id = doc_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        log(f"Initialisation du client Grist avec l'URL: {self.base_url}")
```

#### **`table_exists(table_id)`**
```python
def table_exists(self, table_id):
    """Vérifie si une table existe dans le document Grist."""
    try:
        tables_data = self.list_tables()
        
        # Vérification de la structure de tables_data
        if isinstance(tables_data, dict) and 'tables' in tables_data:
            tables = tables_data['tables']
        elif isinstance(tables_data, list):
            tables = tables_data
        else:
            log_verbose(f"Structure inattendue: {type(tables_data)}")
            return None
        
        # Recherche case-insensitive
        for table in tables:
            if isinstance(table, dict) and table.get('id', '').lower() == table_id.lower():
                log_verbose(f"Table {table_id} trouvée avec l'ID {table.get('id')}")
                return table
        
        log_verbose(f"Table {table_id} non trouvée")
        return None
        
    except Exception as e:
        log_error(f"Erreur lors de la recherche de la table {table_id}: {e}")
        return None
```

#### **`get_existing_dossier_numbers(table_id)`**
```python
def get_existing_dossier_numbers(self, table_id):
    """
    Récupère tous les numéros de dossiers existants dans la table.
    Retourne un set pour lookup O(1).
    """
    try:
        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            # Extraire les numéros de dossiers
            existing_numbers = set()
            for record in data.get('records', []):
                if 'fields' in record and 'number' in record['fields']:
                    existing_numbers.add(record['fields']['number'])
            
            log(f"Trouvé {len(existing_numbers)} dossiers existants dans {table_id}")
            return existing_numbers
        else:
            log_error(f"Erreur récupération dossiers existants: {response.status_code}")
            return set()
            
    except Exception as e:
        log_error(f"Exception récupération dossiers: {e}")
        return set()
```

#### **`create_table(table_id, columns)`**
```python
def create_table(self, table_id, columns):
    """Crée une nouvelle table avec les colonnes spécifiées."""
    url = f"{self.base_url}/docs/{self.doc_id}/tables"
    payload = {
        "id": table_id,
        "columns": columns
    }
    
    response = requests.post(url, headers=self.headers, json=payload)
    
    if response.status_code in [200, 201]:
        log(f"Table {table_id} créée avec succès")
        return True
    elif "already exists" in response.text.lower():
        log(f"Table {table_id} existe déjà")
        return True
    else:
        log_error(f"Erreur création table {table_id}: {response.text}")
        return False
```

#### **`add_records(table_id, records)`**
```python
def add_records(self, table_id, records):
    """Ajoute des enregistrements à une table par batch."""
    if not records:
        return 0
    
    url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
    
    # Diviser en batches si nécessaire (max 5000 par requête)
    batch_size = 5000
    total_added = 0
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i+batch_size]
        payload = {"records": [{"fields": record} for record in batch]}
        
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code in [200, 201]:
            total_added += len(batch)
            log_verbose(f"Ajouté {len(batch)} enregistrements à {table_id}")
        else:
            log_error(f"Erreur ajout records: {response.text}")
    
    return total_added
```

#### **`ensure_columns(table_id, required_columns)`**
```python
def ensure_columns(self, table_id, required_columns):
    """S'assure que toutes les colonnes requises existent dans la table."""
    # Récupérer les colonnes existantes
    existing_columns = self.get_columns(table_id)
    existing_ids = set(existing_columns.keys())
    
    # Identifier les colonnes manquantes
    columns_to_add = []
    for col in required_columns:
        if col['id'] not in existing_ids:
            columns_to_add.append(col)
    
    if columns_to_add:
        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/columns"
        payload = {"columns": columns_to_add}
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code == 200:
            log(f"Ajouté {len(columns_to_add)} colonnes à {table_id}")
        else:
            log_error(f"Erreur ajout colonnes: {response.text}")
```

### **Fonction `detect_column_types(dossiers_data, problematic_ids)`**

Analyse automatique de la structure des données :

```python
def detect_column_types(dossiers_data, problematic_ids=None):
    """
    Détecte automatiquement les types de colonnes à partir des données.
    Analyse jusqu'à 3 dossiers échantillons.
    """
    if problematic_ids is None:
        problematic_ids = set()
    
    # Colonnes de base pour la table des dossiers
    dossier_columns = [
        {"id": "dossier_id", "type": "Text"},
        {"id": "number", "type": "Int"},
        {"id": "state", "type": "Text"},
        {"id": "date_depot", "type": "DateTime"},
        {"id": "date_derniere_modification", "type": "DateTime"},
        {"id": "date_traitement", "type": "DateTime"},
        {"id": "demandeur_type", "type": "Text"},
        {"id": "demandeur_civilite", "type": "Text"},
        {"id": "demandeur_nom", "type": "Text"},
        {"id": "demandeur_prenom", "type": "Text"},
        {"id": "demandeur_email", "type": "Text"},
        {"id": "demandeur_siret", "type": "Text"},
        {"id": "entreprise_raison_sociale", "type": "Text"},
        {"id": "usager_email", "type": "Text"},
        {"id": "groupe_instructeur_id", "type": "Text"},
        {"id": "groupe_instructeur_number", "type": "Int"},
        {"id": "groupe_instructeur_label", "type": "Text"},
        {"id": "supprime_par_usager", "type": "Bool"},
        {"id": "date_suppression", "type": "DateTime"},
        {"id": "prenom_mandataire", "type": "Text"},
        {"id": "nom_mandataire", "type": "Text"},
        {"id": "depose_par_un_tiers", "type": "Bool"},
        {"id": "label_names", "type": "Text"},
        {"id": "labels_json", "type": "Text"}
    ]
    
    # Colonnes de base pour les champs et annotations
    champ_columns = [
        {"id": "dossier_number", "type": "Int"},
        {"id": "champ_id", "type": "Text"},
    ]
    
    annotation_columns = [
        {"id": "dossier_number", "type": "Int"},
    ]
    
    # Dictionnaires pour stocker les colonnes uniques détectées
    unique_champ_columns = {}
    unique_annotation_columns = {}
    
    # Flags pour détecter la présence de structures spéciales
    has_repetable_blocks = False
    has_carto_fields = False
    
    # Analyser quelques dossiers pour détecter les types
    max_sample = min(3, len(dossiers_data))
    
    for i in range(max_sample):
        dossier = dossiers_data[i]
        
        # Transformer en données plates
        flat_data = dossier_to_flat_data(dossier, problematic_ids)
        
        # Analyser les champs
        for champ in flat_data.get("champs", []):
            for key, value in champ.items():
                if key not in ["dossier_number", "champ_id"] and key not in unique_champ_columns:
                    # Détection du type
                    col_type = detect_value_type(value)
                    unique_champ_columns[normalize_column_name(key)] = col_type
        
        # Analyser les annotations
        for annotation in flat_data.get("annotations", []):
            for key, value in annotation.items():
                if key != "dossier_number" and key not in unique_annotation_columns:
                    col_type = detect_value_type(value)
                    unique_annotation_columns[normalize_column_name(key)] = col_type
        
        # Détecter les blocs répétables
        if flat_data.get("repetable_rows"):
            has_repetable_blocks = True
        
        # Détecter les champs cartographiques
        if flat_data.get("carto_champs"):
            has_carto_fields = True
    
    # Ajouter les colonnes détectées
    for col_name, col_type in unique_champ_columns.items():
        champ_columns.append({"id": col_name, "type": col_type})
    
    for col_name, col_type in unique_annotation_columns.items():
        annotation_columns.append({"id": col_name, "type": col_type})
    
    result = {
        "dossier": dossier_columns,
        "champs": champ_columns,
        "annotations": annotation_columns,
        "has_repetable_blocks": has_repetable_blocks,
        "has_carto_fields": has_carto_fields
    }
    
    # Détecter les colonnes des blocs répétables si nécessaire
    if has_repetable_blocks:
        try:
            import repetable_processor as rp
            repetable_columns = rp.detect_repetable_columns_from_multiple_dossiers(dossiers_data)
            result["repetable_rows"] = repetable_columns
        except Exception as e:
            log_error(f"Erreur détection colonnes répétables: {str(e)}")
            # Structure de base en cas d'erreur
            result["repetable_rows"] = [
                {"id": "dossier_number", "type": "Int"},
                {"id": "block_label", "type": "Text"},
                {"id": "block_row_index", "type": "Int"},
                {"id": "block_row_id", "type": "Text"}
            ]
    
    return result

def detect_value_type(value):
    """Détecte le type d'une valeur pour Grist"""
    if value is None:
        return "Text"
    
    # DateTime
    if isinstance(value, str) and ("T" in value and ":" in value):
        return "DateTime"
    
    # Boolean
    if isinstance(value, bool) or value in ["true", "false", "True", "False"]:
        return "Bool"
    
    # Numeric
    if isinstance(value, (int, float)):
        if isinstance(value, int):
            return "Int"
        return "Numeric"
    
    # Essayer de parser en nombre
    if isinstance(value, str):
        try:
            float(value)
            if "." in value:
                return "Numeric"
            return "Int"
        except:
            pass
    
    return "Text"
```

### **Fonction `get_problematic_descriptor_ids(demarche_number)`**

Identifie les champs à ignorer :

```python
def get_problematic_descriptor_ids(demarche_number):
    """
    Récupère les IDs des descripteurs problématiques (HeaderSection, Explication).
    """
    from queries_config import API_TOKEN, API_URL
    import requests
    
    query = """
    query getDemarche($demarcheNumber: Int!) {
      demarche(number: $demarcheNumber) {
        activeRevision {
          champDescriptors {
            __typename
            id
            type
          }
        }
      }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        API_URL,
        json={"query": query, "variables": {"demarcheNumber": int(demarche_number)}},
        headers=headers
    )
    
    response.raise_for_status()
    result = response.json()
    
    problematic_ids = set()
    
    # Extraire les IDs des champs problématiques
    if (result.get("data") and 
        result["data"].get("demarche") and 
        result["data"]["demarche"].get("activeRevision")):
        
        descriptors = result["data"]["demarche"]["activeRevision"].get("champDescriptors", [])
        
        for descriptor in descriptors:
            if descriptor.get("type") in ["header_section", "explication"] or \
               descriptor.get("__typename") in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"]:
                problematic_ids.add(descriptor.get("id"))
    
    log(f"Nombre de descripteurs problématiques: {len(problematic_ids)}")
    return problematic_ids
```

# Partie 4 : Modules de requêtes et extraction

## 1. **`queries.py`** - Module d'orchestration

**Rôle :** Point d'entrée unifié pour toutes les opérations de requêtes.

```python
import os
import traceback
from pprint import pprint
from dotenv import load_dotenv

# Import des modules locaux
from queries_config import API_TOKEN
from queries_graphql import get_dossier, get_demarche, get_demarche_dossiers, get_dossier_geojson
from queries_util import format_complex_json_for_grist, associate_geojson_with_champs
from queries_extract import extract_champ_values, dossier_to_flat_data

# Exposer les fonctions principales pour l'importation
__all__ = [
    'get_dossier', 
    'get_demarche', 
    'get_demarche_dossiers', 
    'get_dossier_geojson',
    'extract_champ_values', 
    'dossier_to_flat_data', 
    'associate_geojson_with_champs',
    'format_complex_json_for_grist'
]
```

### **Script de test intégré**

```python
if __name__ == "__main__":
    try:
        # Charger les variables d'environnement
        load_dotenv()
        
        # Récupérer le numéro de démarche depuis le fichier .env
        demarche_number = os.getenv("DEMARCHE_NUMBER")
        if demarche_number:
            demarche_number = int(demarche_number)
            print(f"Récupération de la démarche {demarche_number}...")
            
            # Récupérer la démarche
            demarche_data = get_demarche(demarche_number)
            
            print("\nInformations de la démarche:")
            print(f"Titre: {demarche_data['title']}")
            print(f"État: {demarche_data['state']}")
            
            # Vérifier si des dossiers ont été récupérés
            dossiers = []
            if 'dossiers' in demarche_data and 'nodes' in demarche_data['dossiers']:
                dossiers = demarche_data['dossiers']['nodes']
            
            print(f"Nombre de dossiers récupérés: {len(dossiers)}")
            
            # Si des dossiers ont été trouvés, afficher le détail du premier
            if dossiers:
                dossier = dossiers[0]
                dossier_number = dossier["number"]
                print(f"\nAffichage détaillé du dossier {dossier_number}:")
                
                # Récupérer toutes les données du dossier
                detailed_dossier = get_dossier(dossier_number)
                
                # Transformer les données du dossier
                flat_data = dossier_to_flat_data(detailed_dossier)
                
                # Afficher les différentes sections
                print("\n--- Informations du dossier ---")
                pprint(flat_data["dossier"])
                
                print("\n--- Champs ---")
                for champ in flat_data["champs"][:10]:  # Limiter pour lisibilité
                    pprint(champ)
                
                print("\n--- Blocs répétables ---")
                for row in flat_data["repetable_rows"][:5]:
                    pprint(row)
                
                # Option : exporter vers un fichier JSON
                import json
                with open(f"dossier_{dossier_number}_flat_data.json", "w", encoding="utf-8") as f:
                    json.dump(flat_data, f, ensure_ascii=False, indent=2)
                print(f"\nDonnées exportées dans dossier_{dossier_number}_flat_data.json")
        
        else:
            print("Aucun numéro de démarche trouvé dans .env")
            
    except Exception as e:
        print(f"Erreur: {e}")
        traceback.print_exc()
```

---

## 2. **`queries_config.py`** - Configuration des APIs

**Rôle :** Centralise la configuration des connexions API.

```python
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration de l'API Démarches Simplifiées
API_TOKEN = os.getenv("DEMARCHES_API_TOKEN")
API_URL = os.getenv("DEMARCHES_API_URL", "https://www.demarches-simplifiees.fr/api/v2/graphql")

# Headers HTTP pour les requêtes
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Validation de la configuration
if not API_TOKEN:
    print("⚠️ ATTENTION: DEMARCHES_API_TOKEN non défini dans le fichier .env")
```

---

## 3. **`queries_graphql.py`** - Requêtes GraphQL

**Rôle :** Contient toutes les requêtes GraphQL et leur exécution.

### **Fragments GraphQL réutilisables**

```python
# Fragments communs pour les entités
COMMON_FRAGMENTS = """
fragment PersonneMoraleFragment on PersonneMorale {
    siret
    siegeSocial
    naf
    libelleNaf
    address {
        ...AddressFragment
    }
    entreprise {
        siren
        raisonSociale
        nomCommercial
    }
}

fragment PersonnePhysiqueFragment on PersonnePhysique {
    civilite
    nom
    prenom
    email
}

fragment AddressFragment on Address {
    label
    type
    streetAddress
    postalCode
    cityName
}

fragment FileFragment on File {
    __typename
    filename
    contentType
    checksum
    byteSize: byteSizeBigInt
    url
    createdAt
}

fragment GeoAreaFragment on GeoArea {
    id
    source
    description
    geometry @include(if: $includeGeometry) {
        type
        coordinates
    }
    ... on ParcelleCadastrale {
        commune
        numero
        section
        prefixe
        surface
    }
}
"""

# Fragments spécialisés pour les territoires
SPECIALIZED_FRAGMENTS = """
fragment PaysFragment on Pays {
    name
    code
}

fragment RegionFragment on Region {
    name
    code
}

fragment DepartementFragment on Departement {
    name
    code
}

fragment CommuneFragment on Commune {
    name
    code
    postalCode
}
"""

# Fragments pour les champs
CHAMP_FRAGMENTS = """
fragment ChampFragment on Champ {
    id
    champDescriptorId
    __typename
    label
    stringValue
    updatedAt
    prefilled
    ... on DateChamp {
        date
    }
    ... on DatetimeChamp {
        datetime
    }
    ... on CheckboxChamp {
        checked: value
    }
    ... on YesNoChamp {
        selected: value
    }
    ... on DecimalNumberChamp {
        decimalNumber: value
    }
    ... on IntegerNumberChamp {
        integerNumber: value
    }
    ... on CiviliteChamp {
        civilite: value
    }
    ... on LinkedDropDownListChamp {
        primaryValue
        secondaryValue
    }
    ... on MultipleDropDownListChamp {
        values
    }
    ... on PieceJustificativeChamp {
        files {
            ...FileFragment
        }
    }
    ... on AddressChamp {
        address {
            ...AddressFragment
        }
        commune {
            ...CommuneFragment
        }
        departement {
            ...DepartementFragment
        }
    }
    ... on Siret
# 🦄 One Trick Pony DS to Grist - Documentation Technique
# Partie 5 : Modules spécialisés et configuration complète

## 1. **`repetable_processor.py`** - Traitement des blocs répétables

**Rôle :** Module spécialisé pour les structures répétables dans les formulaires DS.

### **Fonction `should_skip_field(field, problematic_ids=None)`**

```python
def should_skip_field(field, problematic_ids=None):
    """
    Détermine si un champ doit être ignoré.
    Utilise la même logique que dossier_to_flat_data pour la cohérence.
    """
    # Ignorer par type
    if field.get("__typename") in ["HeaderSectionChamp", "ExplicationChamp"]:
        return True
    
    # Ignorer par ID problématique
    if problematic_ids and field.get("id") in problematic_ids:
        return True
    
    # Ignorer par type de champ (au cas où)
    if field.get("type") in ["header_section", "explication"]:
        return True
    
    return False
```

### **Fonction `normalize_key(key_string)`**

```python
def normalize_key(key_string):
    """
    Normalise une clé en supprimant les caractères spéciaux et en convertissant 
    en minuscules pour garantir une correspondance cohérente.
    """
    import re
    
    # Convertir en chaîne si ce n'est pas déjà le cas
    if not isinstance(key_string, str):
        key_string = str(key_string)
    
    # Remplacer les caractères problématiques par des underscores
    normalized = re.sub(r'[^\w_]', '_', key_string)
    
    # Convertir en minuscules et supprimer les underscores multiples
    normalized = re.sub(r'_+', '_', normalized.lower())
    
    return normalized
```

### **Fonction `extract_repetable_blocks(dossier, problematic_ids=None)`**

```python
def extract_repetable_blocks(dossier, problematic_ids=None):
    """
    Extrait tous les blocs répétables d'un dossier et les transforme
    en structure plate pour insertion dans Grist.
    """
    if problematic_ids is None:
        problematic_ids = set()
    
    repetable_rows = []
    dossier_number = dossier.get("number")
    
    # Parcourir tous les champs
    for champ in dossier.get("champs", []):
        if champ.get("__typename") == "RepetitionChamp":
            block_label = champ.get("label", "")
            rows = champ.get("rows", [])
            
            # Traiter chaque ligne du bloc répétable
            for row_index, row in enumerate(rows):
                row_data = {
                    "dossier_number": dossier_number,
                    "block_label": block_label,
                    "block_row_index": row_index,
                    "block_row_id": row.get("id")
                }
                
                # Extraire tous les champs de la ligne
                for field in row.get("champs", []):
                    if should_skip_field(field, problematic_ids):
                        continue
                    
                    # Extraire la valeur selon le type de champ
                    field_label = field.get("label", "")
                    field_name = normalize_column_name(field_label)
                    
                    typename = field.get("__typename", "")
                    
                    # Extraction selon le type
                    if typename == "CheckboxChamp":
                        value = field.get("checked", False)
                    elif typename == "DateChamp":
                        value = field.get("date")
                    elif typename == "DatetimeChamp":
                        value = field.get("datetime")
                    elif typename in ["DecimalNumberChamp", "IntegerNumberChamp"]:
                        value = field.get("value")
                    elif typename == "MultipleDropDownListChamp":
                        values = field.get("values", [])
                        value = ", ".join(values) if values else None
                    elif typename == "LinkedDropDownListChamp":
                        primary = field.get("primaryValue", "")
                        secondary = field.get("secondaryValue", "")
                        value = f"{primary} - {secondary}" if secondary else primary
                    elif typename == "PieceJustificativeChamp":
                        files = field.get("files", [])
                        if files:
                            value = json.dumps([{
                                "filename": f.get("filename"),
                                "url": f.get("url")
                            } for f in files], ensure_ascii=False)
                        else:
                            value = None
                    else:
                        # Valeur par défaut
                        value = field.get("stringValue") or field.get("value")
                    
                    row_data[field_name] = value
                
                repetable_rows.append(row_data)
    
    # Traiter aussi les annotations répétables si présentes
    for annotation in dossier.get("annotations", []):
        if annotation.get("__typename") == "RepetitionChamp":
            block_label = annotation.get("label", "")
            rows = annotation.get("rows", [])
            
            for row_index, row in enumerate(rows):
                row_data = {
                    "dossier_number": dossier_number,
                    "block_label": f"[Annotation] {block_label}",
                    "block_row_index": row_index,
                    "block_row_id": row.get("id")
                }
                
                for field in row.get("champs", []):
                    if not should_skip_field(field, problematic_ids):
                        field_name = normalize_column_name(field.get("label", ""))
                        value = field.get("stringValue") or field.get("value")
                        row_data[field_name] = value
                
                repetable_rows.append(row_data)
    
    return repetable_rows
```

```

### **Fonction `detect_repetable_columns_from_multiple_dossiers(dossiers_data)`**

```python
def detect_repetable_columns_from_multiple_dossiers(dossiers_data):
    """
    Analyse plusieurs dossiers pour détecter toutes les colonnes possibles
    dans les blocs répétables.
    """
    # Colonnes de base toujours présentes
    base_columns = [
        {"id": "dossier_number", "type": "Int"},
        {"id": "block_label", "type": "Text"},
        {"id": "block_row_index", "type": "Int"},
        {"id": "block_row_id", "type": "Text"}
    ]
    
    # Dictionnaire pour collecter toutes les colonnes uniques
    unique_columns = {}
    
    # Analyser chaque dossier
    for dossier in dossiers_data[:5]:  # Limiter à 5 dossiers pour la performance
        repetable_rows = extract_repetable_blocks(dossier)
        
        # Collecter toutes les clés uniques
        for row in repetable_rows:
            for key, value in row.items():
                # Skip les colonnes de base
                if key in ["dossier_number", "block_label", "block_row_index", "block_row_id"]:
                    continue
                
                # Si on n'a pas encore vu cette colonne
                if key not in unique_columns:
                    # Détecter le type
                    col_type = detect_value_type(value)
                    unique_columns[key] = col_type
    
    # Construire la liste finale des colonnes
    columns = base_columns.copy()
    for col_name, col_type in unique_columns.items():
        columns.append({
            "id": col_name,
            "type": col_type
        })
    
    log(f"Détecté {len(unique_columns)} colonnes uniques dans les blocs répétables")
    return columns

def detect_value_type(value):
    """Détecte le type Grist approprié pour une valeur."""
    if value is None:
        return "Text"
    
    # DateTime
    if isinstance(value, str) and ("T" in value and ":" in value):
        try:
            datetime.strptime(value.split("T")[0], "%Y-%m-%d")
            return "DateTime"
        except:
            pass
    
    # Boolean
    if isinstance(value, bool) or value in ["true", "false", True, False]:
        return "Bool"
    
    # Numeric
    if isinstance(value, (int, float)):
        if isinstance(value, int):
            return "Int"
        return "Numeric"
    
    # Essayer de parser en nombre
    if isinstance(value, str):
        try:
            float_val = float(value)
            if "." in value:
                return "Numeric"
            return "Int"
        except:
            pass
    
    return "Text"
```

### **Fonction `process_repetable_rows_for_grist(client, repetable_data, table_id, dossier_number)`**

```python
def process_repetable_rows_for_grist(client, repetable_data, table_id, dossier_number):
    """
    Traite et insère les données de blocs répétables dans Grist.
    """
    if not repetable_data:
        log_verbose(f"Pas de données répétables pour le dossier {dossier_number}")
        return True
    
    try:
        # Vérifier que la table existe
        if not client.table_exists(table_id):
            log_error(f"Table {table_id} n'existe pas")
            return False
        
        # Récupérer les colonnes existantes
        existing_columns = client.get_columns(table_id)
        required_columns = set()
        
        # Collecter toutes les colonnes nécessaires
        for row in repetable_data:
            required_columns.update(row.keys())
        
        # Identifier les colonnes manquantes
        missing_columns = []
        for col_name in required_columns:
            if col_name not in existing_columns:
                # Déterminer le type en analysant les valeurs
                col_type = "Text"  # Défaut
                for row in repetable_data:
                    if col_name in row and row[col_name] is not None:
                        col_type = detect_value_type(row[col_name])
                        break
                
                missing_columns.append({
                    "id": col_name,
                    "type": col_type
                })
        
        # Ajouter les colonnes manquantes
        if missing_columns:
            client.ensure_columns(table_id, missing_columns)
            log(f"Ajouté {len(missing_columns)} colonnes à {table_id}")
        
        # Préparer les enregistrements pour Grist
        records = []
        for row_data in repetable_data:
            # Convertir les valeurs selon leur type
            record = {}
            for key, value in row_data.items():
                if value is not None:
                    # Conversion selon le type de la colonne
                    col_type = existing_columns.get(key, "Text")
                    record[key] = format_value_for_grist(value, col_type)
                else:
                    record[key] = None
            
            records.append(record)
        
        # Insérer les enregistrements
        if records:
            added = client.add_records(table_id, records)
            log_verbose(f"Ajouté {added} lignes répétables pour le dossier {dossier_number}")
            return True
        
        return True
        
    except Exception as e:
        log_error(f"Erreur traitement blocs répétables dossier {dossier_number}: {e}")
        import traceback
        traceback.print_exc()
        return False
```

---

## 2. **`schema_utils.py`** - Gestion avancée des schémas

**Rôle :** Récupération et création de schémas complets sans avoir besoin de données.

### **Fonction `get_demarche_schema(demarche_number)`**

```python
def get_demarche_schema(demarche_number):
    """
    Récupère le schéma complet d'une démarche avec tous ses descripteurs de champs,
    sans dépendre des dossiers existants.
    """
    if not API_TOKEN:
        raise ValueError("Le token d'API n'est pas configuré")
    
    # Requête GraphQL spécifique pour récupérer les descripteurs
    query = """
    query getDemarcheSchema($demarcheNumber: Int!) {
        demarche(number: $demarcheNumber) {
            id
            number
            title
            activeRevision {
                id
                champDescriptors {
                    ...ChampDescriptorFragment
                    ... on RepetitionChampDescriptor {
                        champDescriptors {
                            ...ChampDescriptorFragment
                        }
                    }
                }
                annotationDescriptors {
                    ...ChampDescriptorFragment
                    ... on RepetitionChampDescriptor {
                        champDescriptors {
                            ...ChampDescriptorFragment
                        }
                    }
                }
            }
        }
    }
    
    fragment ChampDescriptorFragment on ChampDescriptor {
        __typename
        id
        type
        label
        description
        required
        ... on DropDownListChampDescriptor {
            options
            otherOption
        }
        ... on MultipleDropDownListChampDescriptor {
            options
        }
        ... on LinkedDropDownListChampDescriptor {
            options
        }
        ... on PieceJustificativeChampDescriptor {
            fileTemplate {
                filename
            }
        }
        ... on ExplicationChampDescriptor {
            collapsibleExplanationEnabled
            collapsibleExplanationText
        }
    }
    """
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        API_URL,
        json={"query": query, "variables": {"demarcheNumber": int(demarche_number)}},
        headers=headers
    )
    
    response.raise_for_status()
    result = response.json()
    
    # Vérifier les erreurs
    if "errors" in result:
        filtered_errors = []
        for error in result["errors"]:
            error_message = error.get("message", "")
            if "permissions" not in error_message.lower():
                filtered_errors.append(error_message)
        
        if filtered_errors:
            raise Exception(f"GraphQL errors: {', '.join(filtered_errors)}")
    
    # Vérifier que les données sont présentes
    if not result.get("data") or not result["data"].get("demarche"):
        raise Exception(f"Aucune donnée de démarche trouvée pour le numéro {demarche_number}")
    
    demarche = result["data"]["demarche"]
    
    # Vérifier que activeRevision existe
    if not demarche.get("activeRevision"):
        raise Exception(f"Aucune révision active trouvée pour la démarche {demarche_number}")
    
    return demarche
```

### **Fonction `get_problematic_descriptor_ids_from_schema(demarche_schema)`**

```python
def get_problematic_descriptor_ids_from_schema(demarche_schema):
    """
    Extrait les IDs des descripteurs problématiques (HeaderSection, Explication)
    directement depuis le schéma de la démarche.
    """
    problematic_ids = set()
    
    # Fonction récursive pour explorer les descripteurs
    def explore_descriptors(descriptors):
        for descriptor in descriptors:
            if descriptor.get("__typename") in ["HeaderSectionChampDescriptor", "ExplicationChampDescriptor"] or \
               descriptor.get("type") in ["header_section", "explication"]:
                problematic_ids.add(descriptor.get("id"))
            
            # Explorer les descripteurs dans les blocs répétables
            if descriptor.get("__typename") == "RepetitionChampDescriptor" and "champDescriptors" in descriptor:
                explore_descriptors(descriptor["champDescriptors"])
    
    # Explorer les descripteurs de champs et d'annotations
    if demarche_schema.get("activeRevision"):
        if "champDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(demarche_schema["activeRevision"]["champDescriptors"])
        
        if "annotationDescriptors" in demarche_schema["activeRevision"]:
            explore_descriptors(demarche_schema["activeRevision"]["annotationDescriptors"])
    
    return problematic_ids
```

### **Fonction `create_columns_from_schema(demarche_schema)`**

```python
def create_columns_from_schema(demarche_schema):
    """
    Crée les définitions de colonnes à partir du schéma de la démarche,
    en filtrant les champs problématiques.
    """
    # IMPORT LOCAL pour éviter la dépendance circulaire
    from grist_processor_working_all import normalize_column_name, log, log_verbose, log_error
    
    # Récupérer les IDs des descripteurs problématiques à filtrer
    problematic_ids = get_problematic_descriptor_ids_from_schema(demarche_schema)
    log(f"Identificateurs de {len(problematic_ids)} descripteurs problématiques à filtrer")
    
    # Colonnes fixes pour la table des dossiers
    dossier_columns = [
        {"id": "dossier_id", "type": "Text"},
        {"id": "number", "type": "Int"},
        {"id": "state", "type": "Text"},
        {"id": "date_depot", "type": "DateTime"},
        {"id": "date_derniere_modification", "type": "DateTime"},
        {"id": "date_traitement", "type": "DateTime"},
        {"id": "demandeur_type", "type": "Text"},
        {"id": "demandeur_civilite", "type": "Text"},
        {"id": "demandeur_nom", "type": "Text"},
        {"id": "demandeur_prenom", "type": "Text"},
        {"id": "demandeur_email", "type": "Text"},
        {"id": "demandeur_siret", "type": "Text"},
        {"id": "entreprise_raison_sociale", "type": "Text"},
        {"id": "usager_email", "type": "Text"},
        {"id": "groupe_instructeur_id", "type": "Text"},
        {"id": "groupe_instructeur_number", "type": "Int"},
        {"id": "groupe_instructeur_label", "type": "Text"},
        {"id": "supprime_par_usager", "type": "Bool"},
        {"id": "date_suppression", "type": "DateTime"},
        {"id": "prenom_mandataire", "type": "Text"},
        {"id": "nom_mandataire", "type": "Text"},
        {"id": "depose_par_un_tiers", "type": "Bool"},
        {"id": "label_names", "type": "Text"},
        {"id": "labels_json", "type": "Text"}
    ]
    
    # Colonnes de base pour les autres tables
    champ_columns = [
        {"id": "dossier_number", "type": "Int"},
        {"id": "champ_id", "type": "Text"},
    ]
    
    annotation_columns = [
        {"id": "dossier_number", "type": "Int"},
    ]
    
    repetable_columns = [
        {"id": "dossier_number", "type": "Int"},
        {"id": "block_label", "type": "Text"},
        {"id": "block_row_index", "type": "Int"},
        {"id": "block_row_id", "type": "Text"},
    ]
    
    # Variables pour suivre la présence de structures spéciales
    has_repetable_blocks = False
    has_carto_fields = False
    
    # Fonction pour mapper le type de descripteur vers le type Grist
    def map_descriptor_type_to_grist(descriptor):
        type_mapping = {
            "text": "Text",
            "textarea": "Text",
            "email": "Text",
            "phone": "Text",
            "url": "Text",
            "drop_down_list": "Text",
            "multiple_drop_down_list": "Text",
            "linked_drop_down_list": "Text",
            "pays": "Text",
            "regions": "Text",
            "departements": "Text",
            "communes": "Text",
            "epci": "Text",
            "address": "Text",
            "carte": "Text",
            "piece_justificative": "Text",
            "siret": "Text",
            "rna": "Text",
            "rnf": "Text",
            "integer_number": "Int",
            "decimal_number": "Numeric",
            "checkbox": "Bool",
            "yes_no": "Bool",
            "date": "DateTime",
            "datetime": "DateTime",
            "dossier_link": "Int",
            "titre_identite": "Text",
            "iban": "Text",
            "civilite": "Text",
            "engagement_juridique": "Text",
            "cojo": "Text",
            "expression_reguliere": "Text",
            "mesri": "Text",
            "pole_emploi": "Text",
            "dgfip": "Text",
            "cnaf": "Text",
            "annuaire_education": "Text"
        }
        
        descriptor_type = descriptor.get("type", "text")
        return type_mapping.get(descriptor_type, "Text")
    
    # Fonction récursive pour traiter les descripteurs
    def process_descriptors(descriptors, target_columns, is_repetable=False):
        for descriptor in descriptors:
            descriptor_id = descriptor.get("id")
            
            # Skip si c'est un descripteur problématique
            if descriptor_id in problematic_ids:
                continue
            
            typename = descriptor.get("__typename", "")
            label = descriptor.get("label", "")
            
            # Si c'est un bloc répétable
            if typename == "RepetitionChampDescriptor":
                nonlocal has_repetable_blocks
                has_repetable_blocks = True
                
                # Traiter les champs à l'intérieur du bloc répétable
                if "champDescriptors" in descriptor:
                    for child_descriptor in descriptor["champDescriptors"]:
                        if child_descriptor.get("id") not in problematic_ids:
                            child_label = child_descriptor.get("label", "")
                            normalized_name = normalize_column_name(child_label)
                            grist_type = map_descriptor_type_to_grist(child_descriptor)
                            
                            # Ajouter à la table des répétables
                            if not any(col["id"] == normalized_name for col in repetable_columns):
                                repetable_columns.append({
                                    "id": normalized_name,
                                    "type": grist_type
                                })
            
            # Si c'est un champ cartographique
            elif descriptor.get("type") == "carte":
                nonlocal has_carto_fields
                has_carto_fields = True
                # Les champs carto sont stockés comme Text (JSON)
                normalized_name = normalize_column_name(label)
                if not any(col["id"] == normalized_name for col in target_columns):
                    target_columns.append({
                        "id": normalized_name,
                        "type": "Text"
                    })
            
            # Champ standard
            else:
                normalized_name = normalize_column_name(label)
                grist_type = map_descriptor_type_to_grist(descriptor)
                
                # Ajouter à la liste cible si pas déjà présent
                if not any(col["id"] == normalized_name for col in target_columns):
                    target_columns.append({
                        "id": normalized_name,
                        "type": grist_type
                    })
    
    # Traiter les descripteurs de champs
    if demarche_schema.get("activeRevision"):
        if "champDescriptors" in demarche_schema["activeRevision"]:
            process_descriptors(
                demarche_schema["activeRevision"]["champDescriptors"],
                champ_columns
            )
        
        # Traiter les descripteurs d'annotations
        if "annotationDescriptors" in demarche_schema["activeRevision"]:
            process_descriptors(
                demarche_schema["activeRevision"]["annotationDescriptors"],
                annotation_columns
            )
    
    # Préparer le résultat
    result = {
        "dossier": dossier_columns,
        "champs": champ_columns,
        "annotations": annotation_columns,
        "has_repetable_blocks": has_repetable_blocks,
        "has_carto_fields": has_carto_fields
    }
    
    if has_repetable_blocks:
        result["repetable_rows"] = repetable_columns
    
    log(f"Structure détectée depuis le schéma:")
    log(f"  - {len(champ_columns)} colonnes de champs")
    log(f"  - {len(annotation_columns)} colonnes d'annotations")
    if has_repetable_blocks:
        log(f"  - {len(repetable_columns)} colonnes de blocs répétables")
    
    return result
```

### **Fonction `update_grist_tables_from_schema(client, demarche_schema)`**

```python
def update_grist_tables_from_schema(client, demarche_schema):
    """
    Met à jour ou crée les tables Grist basées sur le schéma de la démarche.
    """
    from grist_processor_working_all import log, log_error
    
    try:
        # Générer les définitions de colonnes depuis le schéma
        columns_def = create_columns_from_schema(demarche_schema)
        
        # Liste des tables à créer/mettre à jour
        tables_to_update = [
            ("dossiers", columns_def["dossier"]),
            ("champs", columns_def["champs"]),
            ("annotations", columns_def["annotations"])
        ]
        
        # Ajouter la table des répétables si nécessaire
        if columns_def.get("has_repetable_blocks") and columns_def.get("repetable_rows"):
            tables_to_update.append(("repetable_rows", columns_def["repetable_rows"]))
        
        # Créer ou mettre à jour chaque table
        for table_id, columns in tables_to_update:
            if client.table_exists(table_id):
                # La table existe, s'assurer que toutes les colonnes sont présentes
                client.ensure_columns(table_id, columns)
                log(f"Table {table_id} mise à jour avec {len(columns)} colonnes")
            else:
                # Créer la table
                if client.create_table(table_id, columns):
                    log(f"Table {table_id} créée avec {len(columns)} colonnes")
                else:
                    log_error(f"Échec de création de la table {table_id}")
                    return False
        
        return True
        
    except Exception as e:
        log_error(f"Erreur lors de la mise à jour des tables depuis le schéma: {e}")
        import traceback
        traceback.print_exc()
        return False
```

---

## 3. Configuration et déploiement

### **`requirements.txt`** - Dépendances Python

```
# Framework web et communication temps réel
Flask==2.3.3
Flask-SocketIO==5.3.6
python-socketio==5.8.0
eventlet==0.33.3

# Gestion de l'environnement et configuration
python-dotenv==1.0.0

# Communication HTTP et APIs
requests==2.31.0

# Manipulation de dates
python-dateutil==2.8.2

# Modules Python standard utilisés (déjà inclus):
# - concurrent.futures : Parallélisation
# - threading : Gestion des threads
# - queue : Files d'attente
# - subprocess : Exécution de processus externes
# - json : Manipulation JSON
# - base64 : Encodage/décodage Base64
# - hashlib : Génération de hash
# - unicodedata : Normalisation de caractères
# - re : Expressions régulières
```

### **Variables d'environnement (.env)**

```bash
# === Configuration API Démarches Simplifiées ===
DEMARCHES_API_TOKEN=votre_token_ici
DEMARCHES_API_URL=https://www.demarches-simplifiees.fr/api/v2/graphql
DEMARCHE_NUMBER=12345

# === Configuration API Grist ===
GRIST_BASE_URL=https://grist.numerique.gouv.fr/api
GRIST_API_KEY=votre_cle_api_grist
GRIST_DOC_ID=id_du_document_grist

# === Paramètres de traitement ===
# Taille des lots pour le traitement (25-500)
BATCH_SIZE=50

# Nombre de workers pour le traitement parallèle (1-10)
MAX_WORKERS=3

# Activer le traitement parallèle (True/False)
PARALLEL=True

# Niveau de log (0=minimal, 1=normal, 2=verbose)
LOG_LEVEL=1

# === Filtres optionnels ===
# Dates au format YYYY-MM-DD
DATE_DEPOT_DEBUT=2024-01-01
DATE_DEPOT_FIN=2024-12-31

# Statuts séparés par des virgules
# Valeurs possibles: en_construction, en_instruction, accepte, refuse, classe_sans_suite
STATUTS_DOSSIERS=en_instruction,accepte

# Numéros de groupes instructeurs séparés par des virgules
GROUPES_INSTRUCTEURS=1,2,3

# === Configuration Flask (production) ===
FLASK_SECRET_KEY=generate-strong-random-key-here-for-production
FLASK_ENV=production
```

---

## 4. Gestion des erreurs et métriques

### **Gestion des erreurs multi-niveaux**

```python
def make_graphql_request_with_retry(query, variables, max_retries=3):
    """
    Exécute une requête GraphQL avec retry automatique et backoff exponentiel.
    """
    for attempt in range(max_retries):
        try:
            response = requests.post(
                API_URL,
                json={"query": query, "variables": variables},
                headers=HEADERS,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            
            # Rate limiting - attendre avant de réessayer
            if response.status_code == 429:
                sleep_time = 2 ** attempt  # Backoff exponentiel: 1, 2, 4 secondes
                log(f"Rate limit atteint, attente de {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            
            # Erreur serveur - réessayer
            if response.status_code >= 500:
                log(f"Erreur serveur {response.status_code}, tentative {attempt + 1}/{max_retries}")
                time.sleep(1)
                continue
            
            # Erreur client - ne pas réessayer
            if 400 <= response.status_code < 500:
                raise Exception(f"Erreur client {response.status_code}: {response.text}")
                
        except requests.exceptions.Timeout:
            if attempt == max_retries - 1:
                raise
            log(f"Timeout, tentative {attempt + 1}/{max_retries}")
            time.sleep(1)
        
        except requests.exceptions.ConnectionError:
            if attempt == max_retries - 1:
                raise
            log(f"Erreur de connexion, tentative {attempt + 1}/{max_retries}")
            time.sleep(2)
    
    raise Exception(f"Échec après {max_retries} tentatives")
```

### **Collecte de métriques**

```python
class MetricsCollector:
    """Collecteur de métriques pour le monitoring."""
    
    def __init__(self):
        self.metrics = {
            "start_time": None,
            "end_time": None,
            "total_dossiers": 0,
            "dossiers_success": 0,
            "dossiers_failed": 0,
            "api_calls": 0,
            "api_errors": 0,
            "grist_inserts": 0,
            "grist_errors": 0,
            "processing_times": [],
            "error_types": {}
        }
    
    def start(self):
        self.metrics["start_time"] = time.time()
    
    def end(self):
        self.metrics["end_time"] = time.time()
        self.metrics["duration"] = self.metrics["end_time"] - self.metrics["start_time"]
    
    def record_dossier(self, success, processing_time=None):
        self.metrics["total_dossiers"] += 1
        if success:
            self.metrics["dossiers_success"] += 1
        else:
            self.metrics["dossiers_failed"] += 1
        
        if processing_time:
            self.metrics["processing_times"].append(processing_time)
    
    def record_error(self, error_type):
        self.metrics["api_errors"] += 1
        if error_type not in self.metrics["error_types"]:
            self.metrics["error_types"][error_type] = 0
        self.metrics["error_types"][error_type] += 1
    
    def get_summary(self):
        """Retourne un résumé des métriques."""
        if self.metrics["processing_times"]:
            avg_time = sum(self.metrics["processing_times"]) / len(self.metrics["processing_times"])
        else:
            avg_time = 0
        
        return {
            "duration_seconds": self.metrics.get("duration", 0),
            "total_dossiers": self.metrics["total_dossiers"],
            "success_rate": (self.metrics["dossiers_success"] / self.metrics["total_dossiers"] * 100) 
                           if self.metrics["total_dossiers"] > 0 else 0,
            "average_processing_time": avg_time,
            "api_errors": self.metrics["api_errors"],
            "error_types": self.metrics["error_types"]
        }
```

---

## 5. Débogage et résolution de problèmes

### **Problèmes courants et solutions**

#### **1. "Token d'API non configuré"**
```bash
# Vérifier le fichier .env
cat .env | grep DEMARCHES_API_TOKEN

# Le token doit être sans espaces ni guillemets
DEMARCHES_API_TOKEN=votre_token_ici  # ✅ Correct
DEMARCHES_API_TOKEN="votre_token"     # ❌ Incorrect
```

#### **2. "Aucun dossier trouvé"**
```python
# Vérifier le numéro de démarche
print(f"Démarche numéro: {demarche_number}")

# Tester sans filtres d'abord
os.environ.pop('DATE_DEPOT_DEBUT', None)
os.environ.pop('DATE_DEPOT_FIN', None)
os.environ.pop('STATUTS_DOSSIERS', None)
```

#### **3. "Erreur de permission"**
```python
# Vérifier les droits du token
query = """
query testPermissions($demarcheNumber: Int!) {
    demarche(number: $demarcheNumber) {
        id
        title
    }
}
"""
# Si cette requête échoue, le token n'a pas accès à la démarche
```

#### **4. "Table already exists"**
```python
# C'est normal si les tables existent déjà
# Le script vérifie et ajoute les colonnes manquantes
# Pas d'action requise
```

### **Mode debug verbose**

```python
# Dans grist_processor_working_all.py
LOG_LEVEL = 2  # Active tous les logs

# Dans app.py pour Flask
app.config['DEBUG'] = True
logging.basicConfig(level=logging.DEBUG)
```

### **Vérification de l'état du système**

```python
def system_check():
    """Vérifie la configuration et l'état du système."""
    checks = {
        "env_file": os.path.exists('.env'),
        "api_token": bool(os.getenv('DEMARCHES_API_TOKEN')),
        "grist_key": bool(os.getenv('GRIST_API_KEY')),
        "required_files": all([
            os.path.exists(f) for f in [
                'grist_processor_working_all.py',
                'queries.py',
                'queries_config.py',
                'queries_extract.py',
                'queries_graphql.py',
                'queries_util.py',
                'repetable_processor.py',
                'schema_utils.py'
            ]
        ])
    }
    
    # Test de connectivité
    try:
        response = requests.get('https://www.demarches-simplifiees.fr', timeout=5)
        checks['ds_reachable'] = response.status_code == 200
    except:
        checks['ds_reachable'] = False
    
    try:
        response = requests.get(os.getenv('GRIST_BASE_URL', 'https://grist.numerique.gouv.fr'), timeout=5)
        checks['grist_reachable'] = response.status_code < 500
    except:
        checks['grist_reachable'] = False
    
    return checks
```

---

## 6. Optimisations et bonnes pratiques

### **Optimisation des performances**

```python
# 1. Utiliser le cache de colonnes
column_cache = ColumnCache(client)
columns = column_cache.get_columns(table_id)  # Utilise le cache

# 2. Traitement par lots optimal
OPTIMAL_BATCH_SIZE = 50  # Compromis entre mémoire et nombre de requêtes

# 3. Parallélisation intelligente
cpu_count = os.cpu_count()
OPTIMAL_WORKERS = min(cpu_count - 1, 4)  # Laisser un CPU libre

# 4. Skip des dossiers déjà traités
existing = client.get_existing_dossier_numbers("dossiers")
new_dossiers = [d for d in dossiers if d["number"] not in existing]
```

### **Sécurité**

```python
# 1. Ne jamais logger les tokens complets
def mask_token(token):
    if len(token) > 8:
        return token[:4] + "..." + token[-4:]
    return "***"

# 2. Valider toutes les entrées utilisateur
def validate_demarche_number(value):
    if not value or not str(value).isdigit():
        raise ValueError("Numéro de démarche invalide")
    return int(value)

# 3. Utiliser HTTPS pour toutes les communications
assert API_URL.startswith('https://'), "L'API doit utiliser HTTPS"
assert GRIST_BASE_URL.startswith('https://'), "Grist doit utiliser HTTPS"

# 4. Timeout sur toutes les requêtes
DEFAULT_TIMEOUT = 30  # secondes
```

### **Monitoring en production**

```python
# 1. Logs structurés
import json
import logging

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName
        }
        return json.dumps(log_data)

# 2. Health check endpoint
@app.route('/health')
def health_check():
    checks = system_check()
    status = 'healthy' if all(checks.values()) else 'unhealthy'
    return jsonify({
        "status": status,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    }), 200 if status == 'healthy' else 503

# 3. Métriques Prometheus (si utilisé)
from prometheus_client import Counter, Histogram, generate_latest

sync_counter = Counter('ds_to_grist_syncs_total', 'Total synchronizations')
sync_duration = Histogram('ds_to_grist_sync_duration_seconds', 'Sync duration')
dossier_counter = Counter('ds_to_grist_dossiers_total', 'Total dossiers processed', ['status'])

@app.route('/metrics')
def metrics():
    return generate_latest()
```

---

## 7. Guide de déploiement en production

### **Configuration avec Gunicorn**

```python
# gunicorn_config.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "eventlet"
worker_connections = 1000
timeout = 120
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
preload_app = True
accesslog = "/var/log/ds-to-grist/access.log"
errorlog = "/var/log/ds-to-grist/error.log"
loglevel = "info"
```

### **Script de démarrage systemd**

```ini
# /etc/systemd/system/ds-to-grist.service
[Unit]
Description=DS to Grist Synchronization Service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/ds-to-grist
Environment="PATH=/opt/ds-to-grist/venv/bin"
ExecStart=/opt/ds-to-grist/venv/bin/gunicorn -c gunicorn_config.py app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **Configuration Nginx**

```nginx
# /etc/nginx/sites-available/ds-to-grist
server {
    listen 80;
    server_name ds-to-grist.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ds-to-grist.example.com;
    
    ssl_certificate /etc/letsencrypt/live/ds-to-grist.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ds-to-grist.example.com/privkey.pem;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
    
    location /socket.io {
        proxy_pass http://127.0.0.1:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### **Sauvegarde et restauration**

```bash
#!/bin/bash
# backup.sh - Script de sauvegarde

BACKUP_DIR="/backup/ds-to-grist"
DATE=$(date +%Y%m%d_%H%M%S)

# Sauvegarder la configuration
cp /opt/ds-to-grist/.env $BACKUP_DIR/.env.$DATE

# Sauvegarder les logs
tar czf $BACKUP_DIR/logs_$DATE.tar.gz /var/log/ds-to-grist/

# Rotation des sauvegardes (garder 30 jours)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Sauvegarde terminée: $DATE"
```

---

## 8. Évolutions et extensions possibles

### **Ajout de webhooks DS**

```python
@app.route('/webhook/ds', methods=['POST'])
def webhook_ds():
    """Webhook pour recevoir les notifications de DS."""
    # Vérifier la signature HMAC
    signature = request.headers.get('X-DS-Signature')
    if not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 401
    
    # Traiter l'événement
    event = request.json
    event_type = event.get('event_type')
    
    if event_type == 'dossier.created':
        dossier_number = event['dossier']['number']
        # Déclencher une synchronisation partielle
        task_id = task_manager.start_task(sync_single_dossier, dossier_number)
        return jsonify({"task_id": task_id}), 202
    
    return jsonify({"status": "ok"}), 200
```

### **Export vers d'autres formats**

```python
def export_to_excel(dossiers_data, filename):
    """Exporte les données vers Excel."""
    import pandas as pd
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Feuille dossiers
        df_dossiers = pd.DataFrame([d['dossier'] for d in dossiers_data])
        df_dossiers.to_excel(writer, sheet_name='Dossiers', index=False)
        
        # Feuille champs
        all_champs = []
        for d in dossiers_data:
            all_champs.extend(d['champs'])
        df_champs = pd.DataFrame(all_champs)
        df_champs.to_excel(writer, sheet_name='Champs', index=False)
        
        # Feuille répétables
        all_repetables = []
        for d in dossiers_data:
            all_repetables.extend(d.get('repetable_rows', []))
        if all_repetables:
            df_repetables = pd.DataFrame(all_repetables)
            df_repetables.to_excel(writer, sheet_name='Blocs répétables', index=False)
    
    return filename
```

### **Synchronisation bidirectionnelle**

```python
def sync_from_grist_to_ds(client, dossier_number, updates):
    """
    Synchronise les modifications de Grist vers DS (si l'API le permet).
    """
    # Récupérer les données modifiées depuis Grist
    grist_data = client.get_records("dossiers", {"number": dossier_number})
    
    # Préparer la mutation GraphQL pour DS
    mutation = """
    mutation updateDossier($input: UpdateDossierInput!) {
        updateDossier(input: $input) {
            dossier {
                id
                number
            }
            errors
        }
    }
    """
    
    # Note: Cette fonctionnalité dépend de l'API DS
    # qui peut ne pas supporter les mutations
    pass
```

---

## Conclusion

Cette documentation complète couvre tous les aspects techniques du projet "One Trick Pony DS to Grist", depuis l'architecture jusqu'au déploiement en production. Le système est conçu pour être :

- **Robuste** : Gestion d'erreurs multi-niveaux, retry automatique
- **Performant** : Optimisations multiples, traitement parallèle
- **Maintenable** : Code modulaire, bien documenté
- **Évolutif** : Architecture permettant l'ajout de fonctionnalités
- **Sécurisé** : Gestion appropriée des secrets, validation des données

Le projet peut être déployé en production et s'adapter à différents volumes de données et cas d'usage.# 🦄 One Trick Pony DS to Grist - Documentation Technique
# Partie 5 : Modules spécialisés et configuration

## 1. **`repetable_processor.py`** - Traitement des blocs répétables

**Rôle :** Module spécialisé pour les structures répétables dans les formulaires DS.

### **Fonction `should_skip_field(field, problematic_ids=None)`**

```python
def should_skip_field(field, problematic_ids=None):
    """
    Détermine si un champ doit être ignoré.
    Utilise la même logique que dossier_to_flat_data pour la cohérence.
    """
    # Ignorer par type
    if field.get("__typename") in ["HeaderSectionChamp", "ExplicationChamp"]:
        return True
    
    # Ignorer par ID problématique
    if problematic_ids and field.get("id") in problematic_ids:
        return True
    
    # Ignorer par type de champ (au cas où)
    if field.get("type") in ["header_section", "explication"]:
        return True
    
    return False
```

### **Fonction `normalize_key(key_string)`**

```python
def normalize_key(key_string):
    """
    Normalise une clé en supprimant les caractères spéciaux et en convertissant 
    en minuscules pour garantir une correspondance cohérente.
    """
    import re
    
    # Convertir en chaîne si ce n'est pas déjà le cas
    if not isinstance(key_string, str):
        key_string = str(key_string)
    
    # Remplacer les caractères problématiques par des underscores
    normalized = re.sub(r'[^\w_]', '_', key_string)
    
    # Convertir en minuscules et supprimer les underscores multiples
    normalized = re.sub(r'_+', '_', normalized.lower())
    
    return normalized
```

### **Fonction `extract_repetable_blocks(dossier, problematic_ids=None)`**

```python
def extract_repetable_blocks(dossier, problematic_ids=None):
    """
    Extrait tous les blocs répétables d'un dossier et les transforme
    en structure plate pour insertion dans Grist.
    """
    if problematic_ids is None:
        problematic_ids = set()
    
    repetable_rows = []
    dossier_number = dossier.get("number")
    
    # Parcourir tous les champs
    for champ in dossier.get("champs", []):
        if champ.get("__typename") == "RepetitionChamp":
            block_label = champ.get("label", "")
            rows = champ.get("rows", [])
            
            # Traiter chaque ligne du bloc répétable
            for row_index, row in enumerate(rows):
                row_data = {
                    "dossier_number": dossier_number,
                    "block_label": block_label,
                    "block_row_index": row_index,
                    "block_row_id": row.get("id")
                }
                
                # Extraire tous les champs de la ligne
                for fiel
