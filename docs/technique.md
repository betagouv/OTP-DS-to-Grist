# 🦄 One Trick Pony DS to Grist - Documentation Technique

## Vue d'ensemble du projet

**One Trick Pony DS to Grist** est une application Flask de synchronisation automatisée entre l'API Démarches Simplifiées (DS) et Grist. Le système récupère les données de démarches administratives françaises via GraphQL et les structure automatiquement dans des tableaux Grist.

### Architecture générale

```
                         ┌──────────────────┐                         
                         │  Base de données │                         
                         │     PostGresql   │                         
                         └──────────────────┘                         
                                  ▲
                                  │
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

## 🔄 Synchronisation Automatique

### **Vue d'ensemble**
La synchronisation automatique utilise **APScheduler** pour exécuter les synchronisations selon un planning prédéfini. Elle permet de maintenir les données Grist à jour sans intervention manuelle.

### **Architecture du Scheduler**

```
[Interface Web Flask]
        ↓
[Activation Planning] → [Base de données: user_schedules]
        ↓
[APScheduler Background]
        ↓
[Job: scheduled_sync_job()]
        ↓
[Subprocess: grist_processor]
        ↓
[Mise à jour Grist + Logs]
```

### **Composants Clés**

1. **APScheduler** : Planificateur en arrière-plan intégré à Flask
2. **Base de données** : Table `user_schedules` pour persister les plannings
3. **Job automatique** : `scheduled_sync_job()` exécute la synchronisation
4. **Logs de suivi** : Table `sync_logs` pour historiser les exécutions

### **Flux d'Exécution**

```
Activation Planning
        ↓
reload_scheduler_jobs() → APScheduler.add_job()
        ↓
Minuit (CronTrigger) → scheduled_sync_job(config_id)
        ↓
Chargement config DB → run_synchronization_task()
        ↓
Subprocess grist_processor → Mise à jour Grist
        ↓
Logs + Notifications → Interface Web
```

### **Gestion des Conflits**

- **Décalage temporel** : +15 minutes entre jobs sur le même document
- **Verrouillage** : Un job par configuration simultanément
- **Idempotence** : Les synchronisations peuvent être relancées sans duplication

### **Configuration**

| Paramètre | Valeur par défaut | Description                           |
|-----------|-------------------|---------------------------------------|
| Fréquence | Quotidienne       | Minuit chaque jour                    |
| Décalage  | 15 minutes        | Entre configurations du même document |
| Timeout   | 2 heures          | Durée maximale d'une synchronisation  |
| Retry     | Automatique       | En cas d'échec réseau                 |

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

## 💽 Base de données

Elle est utilisée pour stocker la configuration utilisateur.

| ds_api_token | demarche_number | grist_base_url | grist_api_key | grist_doc_id | grist_user_id |
|--------------|-----------------|----------------|---------------|--------------|---------------|

Elle permet la persistence des données, qui sont chargées en fonction du `grist_doc_id` & du `grist_user_id` de l'utilisateur courant (nécessite un contexte grist / d'être dans un widget + autorisation complet au document).

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

