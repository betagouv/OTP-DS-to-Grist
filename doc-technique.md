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
