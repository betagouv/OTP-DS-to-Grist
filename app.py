"""
Application Flask optimisée pour la synchronisation Démarches Simplifiées vers Grist
Version corrigée avec sauvegarde et persistence des configurations
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, Response
from flask_socketio import SocketIO, emit
import os
import sys
import json
import time
import threading
import queue
import subprocess
from datetime import datetime
from dotenv import load_dotenv, set_key
import requests
from werkzeug.serving import WSGIRequestHandler

# Configuration de l'application Flask
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production-2024')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Configuration du logging pour Flask
import logging
import atexit
import subprocess
import re
from sqlalchemy import (create_engine)
from sqlalchemy.orm import sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from zoneinfo import ZoneInfo
from database.database_manager import DatabaseManager
from database.models import OtpConfiguration, UserSchedule, SyncLog
from configuration.config_manager import ConfigManager
from sync_task_manager import SyncTaskManager
from constants import DEMARCHES_API_URL

# Instance globale du scheduler APScheduler
scheduler = BackgroundScheduler(executors={
    'default': ThreadPoolExecutor(max_workers=2)
})

# Déterminer le répertoire du script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Chargement des variables d'environnement
load_dotenv()

class TaskManager:
    """Gestionnaire de tâches asynchrones avec WebSocket pour les mises à jour en temps réel"""
    
    def __init__(self):
        self.tasks = {}
        self.task_counter = 0
    
    def start_task(self, task_function, *args, **kwargs):
        """Démarre une nouvelle tâche asynchrone"""
        self.task_counter += 1
        task_id = f"task_{self.task_counter}"
        
        self.tasks[task_id] = {
            'status': 'running',
            'progress': 0,
            'message': 'Initialisation...',
            'start_time': time.time(),
            'logs': []
        }
        
        # Démarrer la tâche dans un thread séparé
        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, task_function, *args),
            kwargs=kwargs
        )
        thread.start()
        
        return task_id
    
    def _run_task(self, task_id, task_function, *args, **kwargs):
        """Exécute une tâche avec gestion des erreurs"""
        try:
            # Ajouter le callback de progression
            kwargs['progress_callback'] = lambda progress, message: self._update_progress(task_id, progress, message)
            kwargs['log_callback'] = lambda message: self._add_log(task_id, message)
            
            result = task_function(*args, **kwargs)
            
            self.tasks[task_id].update({
                'status': 'completed',
                'progress': 100,
                'message': 'Tâche terminée avec succès',
                'result': result,
                'end_time': time.time()
            })
            
            self._emit_update(task_id)
            
        except Exception as e:
            self.tasks[task_id].update({
                'status': 'error',
                'message': f'Erreur: {str(e)}',
                'error': str(e),
                'end_time': time.time()
            })
            
            self._emit_update(task_id)
    
    def _update_progress(self, task_id, progress, message):
        """Met à jour la progression d'une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]['progress'] = progress
            self.tasks[task_id]['message'] = message
            self._emit_update(task_id)
    
    def _add_log(self, task_id, message):
        """Ajoute un log à une tâche"""
        if task_id in self.tasks:
            self.tasks[task_id]['logs'].append({
                'timestamp': time.time(),
                'message': message
            })
            self._emit_update(task_id)
    
    def _emit_update(self, task_id):
        """Émet une mise à jour via WebSocket"""
        socketio.emit('task_update', {
            'task_id': task_id,
            'task': self.tasks[task_id]
        })
    
    def get_task(self, task_id):
        """Récupère les informations d'une tâche"""
        return self.tasks.get(task_id)

# Instance globale du gestionnaire de tâches
task_manager = TaskManager()

class ConfigManager:
    """Gestionnaire de configuration optimisé avec sauvegarde robuste"""
    
    @staticmethod
    def get_env_path():
        """Retourne le chemin vers le fichier .env"""
        return os.path.join(script_dir, '.env')
    
    @staticmethod
    def load_config():
        """Charge la configuration depuis le fichier .env"""
        # Recharger le fichier .env pour avoir les dernières valeurs
        load_dotenv(ConfigManager.get_env_path(), override=True)
        
        config = {
            'ds_api_token': os.getenv('DEMARCHES_API_TOKEN', ''),
            'ds_api_url': os.getenv('DEMARCHES_API_URL', 'https://demarche.numerique.gouv.fr/api/v2/graphql'),
            'demarche_number': os.getenv('DEMARCHE_NUMBER', ''),
            'grist_base_url': os.getenv('GRIST_BASE_URL', 'https://grist.numerique.gouv.fr/api'),
            'grist_api_key': os.getenv('GRIST_API_KEY', ''),
            'grist_doc_id': os.getenv('GRIST_DOC_ID', ''),
            'batch_size': int(os.getenv('BATCH_SIZE', '25')),
            'max_workers': int(os.getenv('MAX_WORKERS', '2')),
            'parallel': os.getenv('PARALLEL', 'True').lower() == 'true'
        }
        return config
    
    @staticmethod
    def save_config(config):
        """Sauvegarde la configuration dans le fichier .env"""
        env_path = ConfigManager.get_env_path()
        
        try:
            # Mapping des clés pour le fichier .env
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
            
            # Sauvegarder chaque valeur dans le fichier .env
            for config_key, env_key in env_mapping.items():
                if config_key in config and config[config_key] is not None:
                    value = str(config[config_key])
                    # Ne pas sauvegarder les valeurs vides ou masquées
                    if value and value != '***':
                        set_key(env_path, env_key, value)
                        # Mettre à jour aussi la variable d'environnement actuelle
                        os.environ[env_key] = value
                        logger.info(f"Sauvegardé {env_key} = {value[:10]}..." if 'token' in env_key.lower() or 'key' in env_key.lower() else f"Sauvegardé {env_key} = {value}")
            
            # Recharger le fichier .env pour vérification
            load_dotenv(env_path, override=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la configuration: {str(e)}")
            return False

            if user_schedule:
                user_schedule.enabled = False
                db.commit()
                logger.info(f"Planning désactivé pour config {otp_config_id} à cause d'erreur")
        except Exception as disable_e:
            logger.error(f"Erreur lors de la désactivation du planning: {str(disable_e)}")

        # Logger l'erreur
        try:
            otp_config = db.query(OtpConfiguration).filter_by(
                id=otp_config_id
            ).first()

            if otp_config:
                sync_log = SyncLog(
                    grist_user_id=otp_config.grist_user_id,
                    grist_doc_id=otp_config.grist_doc_id,
                    status="error",
                    message=f"Erreur scheduler: {str(e)}"
                )
                db.add(sync_log)
                db.commit()

                # Émettre notification d'erreur
                socketio.emit('sync_error', {
                    'grist_user_id': otp_config.grist_user_id,
                    'grist_doc_id': otp_config.grist_doc_id,
                    'message': f"Erreur de synchronisation planifiée: {str(e)}",
                    'timestamp': datetime.now(timezone.utc).isoformat()
                })
        except Exception as log_error:
            logger.error(f"Erreur lors du logging de l'erreur scheduler: {str(log_error)}")

    finally:
        db.close()


def reload_scheduler_jobs():
    """
    Recharge tous les jobs actifs du scheduler selon les plannings activés.
    Exécutée au démarrage et après activation/désactivation de plannings,
    pour éviter des jobs persistant pour des configs modifiées ou supprimées
    """
    logger.info("Rechargement des jobs du scheduler...")

    try:
        # Supprimer tous les jobs existants
        scheduler.remove_all_jobs()

        # Récupérer tous les plannings activés
        db = SessionLocal()
        tz = ZoneInfo(SYNC_TZ) if SYNC_TZ != 'UTC' else None
        try:
            active_schedules = db.query(
                UserSchedule
            ).filter_by(
                enabled=True
            ).filter(
                UserSchedule.otp_config_id.isnot(None)
            ).all()

            # Trier tous les plannings par otp_config_id pour espacement global
            sorted_schedules = sorted(
                active_schedules,
                key=lambda s: s.otp_config_id
            )

            for i, schedule in enumerate(sorted_schedules):
                # Vérifier que la configuration existe encore
                otp_config = db.query(OtpConfiguration).filter_by(
                    id=schedule.otp_config_id
                ).first()
                if not otp_config:
                    logger.warning(f"Configuration manquante pour schedule {schedule.id}, skipping")
                    continue

                total_offset = SYNC_MINUTE + i * 5
                minute = total_offset % 60
                hour_offset = total_offset // 60
                hour = (SYNC_HOUR + hour_offset) % 24
                job_id = f"scheduled_sync_{schedule.otp_config_id}"
                scheduler.add_job(
                    func=scheduled_sync_job,
                    trigger=CronTrigger(
                        hour=hour,
                        minute=minute,
                        timezone=tz
                    ),
                    args=[schedule.otp_config_id],
                    id=job_id,
                    name=f"Sync planifiée pour config {schedule.otp_config_id}",
                    replace_existing=True,
                    max_instances=1
                )
                logger.info(
                    f"Job ajouté pour schedule {schedule.id} "
                    f"(config {schedule.otp_config_id}, démarche {otp_config.demarche_number}) "
                    f"à {hour:02d}:{minute:02d} (document {otp_config.grist_doc_id})"
                )

        finally:
            db.close()

        logger.info(f"Scheduler rechargé avec {len(scheduler.get_jobs())} jobs actifs")

    except Exception as e:
        logger.error(f"Erreur lors du rechargement des jobs scheduler: {str(e)}")


# Configuration de l'application Flask
app = Flask(__name__)
app.secret_key = os.environ.get(
    'FLASK_SECRET_KEY',
    'dev-key-change-in-production-2024'
)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# Configuration du logging pour Flask
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Démarrage du scheduler au niveau module
if not scheduler.running:
    scheduler.start()
    reload_scheduler_jobs()
    logger.info("Scheduler APScheduler démarré au chargement du module")
    atexit.register(lambda: scheduler.shutdown(wait=True))


# Callback d'injection pour les notifications WebSocket
def socketio_notify_callback(event_type, data):
    socketio.emit(event_type, data)


# Instance globale du gestionnaire de synchronisations
sync_task_manager = SyncTaskManager(
    notify_callback=socketio_notify_callback
)


def test_demarches_api(api_token, demarche_number=None):
    """Teste la connexion à l'API Démarches Simplifiées"""
    try:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        if demarche_number:
            query = """
            query getDemarche($demarcheNumber: Int!) {
                demarche(number: $demarcheNumber) {
                    id
                    number
                    title
                }
            }
            """
            variables = {"demarcheNumber": int(demarche_number)}
            response = requests.post(api_url, json={"query": query, "variables": variables}, headers=headers, timeout=10)
        else:
            query = """
            query {
                demarches(first: 1) {
                    nodes {
                        number
                        title
                    }
                }
            }
            """
            response = requests.post(api_url, json={"query": query}, headers=headers, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if "errors" in result:
                return False, f"Erreur API: {'; '.join([e.get('message', 'Erreur inconnue') for e in result['errors']])}"
            
            if demarche_number and "data" in result and "demarche" in result["data"]:
                demarche = result["data"]["demarche"]
                if demarche:
                    return True, f"Connexion réussie! Démarche trouvée: {demarche.get('title', 'Sans titre')}"
                else:
                    return False, f"Démarche {demarche_number} non trouvée."
            elif "data" in result:
                return True, "Connexion à l'API Démarches Simplifiées réussie!"
            else:
                return False, "Réponse API inattendue."
        else:
            return False, f"Erreur de connexion à l'API: {response.status_code} - {response.text}"
    except requests.exceptions.Timeout:
        return False, "Timeout: L'API met trop de temps à répondre"
    except Exception as e:
        return False, f"Erreur de connexion: {str(e)}"

def test_grist_api(base_url, api_key, doc_id):
    """Teste la connexion à l'API Grist"""
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        if not base_url.endswith('/api'):
            base_url = f"{base_url}/api" if base_url else "https://grist.numerique.gouv.fr/api"
        url = f"{base_url}/docs/{doc_id}"
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            try:
                doc_info = response.json()
                doc_name = doc_info.get('name', doc_id)
                return True, f"Connexion à Grist réussie! Document: {doc_name}"
            except:
                return True, f"Connexion à Grist réussie! Document ID: {doc_id}"
        else:
            return False, f"Erreur de connexion à Grist: {response.status_code} - {response.text}"
    except requests.exceptions.Timeout:
        return False, "Timeout: L'API Grist met trop de temps à répondre"
    except Exception as e:
        return False, f"Erreur de connexion: {str(e)}"

def get_available_groups(api_token, api_url, demarche_number):
    """Récupère les groupes instructeurs disponibles"""
    if not all([api_token, api_url, demarche_number]):
        return []
    
    try:
        query = """
        query getDemarche($demarcheNumber: Int!) {
            demarche(number: $demarcheNumber) {
                groupeInstructeurs {
                    id
                    number
                    label
                }
            }
        }
        """
        
        variables = {"demarcheNumber": int(demarche_number)}
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(api_url, json={"query": query, "variables": variables}, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return []
        
        result = response.json()
        if "errors" in result:
            return []
        
        groupes = result.get("data", {}).get("demarche", {}).get("groupeInstructeurs", [])
        return [(groupe.get("number"), groupe.get("label")) for groupe in groupes]
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des groupes instructeurs: {str(e)}")
        return []


def run_synchronization_task(config, filters, progress_callback=None, log_callback=None):
    """Exécute la synchronisation avec callbacks pour le suivi en temps réel"""
    try:
        if progress_callback:
            progress_callback(5, "Préparation de l'environnement...")
        
        # ✅ NOUVEAU : Afficher les filtres effectivement utilisés
        if log_callback:
            log_callback("=== CONFIGURATION DES FILTRES ===")
            
            # Vérifier et afficher les variables d'environnement actuelles
            date_debut = os.getenv("DATE_DEPOT_DEBUT", "").strip()
            date_fin = os.getenv("DATE_DEPOT_FIN", "").strip()
            statuts = os.getenv("STATUTS_DOSSIERS", "").strip()
            groupes = os.getenv("GROUPES_INSTRUCTEURS", "").strip()
            
            if date_debut:
                log_callback(f"✓ Filtre date début: {date_debut}")
            else:
                log_callback("○ Date début: AUCUN FILTRE (tous les dossiers)")
                
            if date_fin:
                log_callback(f"✓ Filtre date fin: {date_fin}")
            else:
                log_callback("○ Date fin: AUCUN FILTRE (tous les dossiers)")
                
            if statuts:
                log_callback(f"✓ Filtre statuts: {statuts}")
            else:
                log_callback("○ Statuts: AUCUN FILTRE (tous les statuts)")
                
            if groupes:
                log_callback(f"✓ Filtre groupes: {groupes}")
            else:
                log_callback("○ Groupes: AUCUN FILTRE (tous les groupes)")
            
            log_callback("=== FIN CONFIGURATION FILTRES ===")
        
        # Mettre à jour les variables d'environnement avec la configuration
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
        
        # Sauvegarder la configuration principale
        for config_key, env_key in env_mapping.items():
            if config_key in config and config[config_key]:
                os.environ[env_key] = str(config[config_key])
        
        # ⚠️ NE PAS écraser les filtres ici car ils ont déjà été définis dans api_start_sync
        # Les variables DATE_DEPOT_DEBUT, DATE_DEPOT_FIN, STATUTS_DOSSIERS, GROUPES_INSTRUCTEURS
        # sont déjà correctement définies dans api_start_sync
        
        if progress_callback:
            progress_callback(10, "Démarrage du processeur...")
        
        # Chemin vers le script de traitement
        script_path = os.path.join(script_dir, "grist_processor_working_all.py")
        
        if not os.path.exists(script_path):
            raise Exception(f"Script de traitement non trouvé: {script_path}")
        
        # Créer une copie de l'environnement actuel pour le sous-processus
        env_copy = os.environ.copy()
        
        # Afficher dans les logs les variables d'environnement transmises au sous-processus
        if log_callback:
            log_callback("Variables transmises au processeur:")
            log_callback(f"  DATE_DEPOT_DEBUT = '{env_copy.get('DATE_DEPOT_DEBUT', '')}'")
            log_callback(f"  DATE_DEPOT_FIN = '{env_copy.get('DATE_DEPOT_FIN', '')}'")
            log_callback(f"  STATUTS_DOSSIERS = '{env_copy.get('STATUTS_DOSSIERS', '')}'")
            log_callback(f"  GROUPES_INSTRUCTEURS = '{env_copy.get('GROUPES_INSTRUCTEURS', '')}'")
        
        # Lancer le processus avec l'environnement mis à jour
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env_copy,  # Utiliser l'environnement mis à jour
            cwd=script_dir
        )
        
        # Mots-clés pour estimer la progression
        progress_keywords = {
            "Récupération de la démarche": (15, "Récupération des données de la démarche..."),
            "Démarche trouvée": (20, "Démarche trouvée - Analyse des données..."),
            "Nombre de dossiers trouvés": (25, "Dossiers trouvés - Préparation du traitement..."),
            "Types de colonnes détectés": (35, "Analyse de la structure des données..."),
            "Table dossiers": (45, "Création/mise à jour des tables Grist..."),
            "Table champs": (50, "Configuration des champs..."),
            "Traitement du lot": (60, "Traitement des dossiers..."),
            "Dossiers traités avec succès": (90, "Finalisation du traitement..."),
            "Traitement terminé": (100, "Traitement terminé!")
        }
        
        current_progress = 10
        
        # Lire la sortie en temps réel
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
                
            # Ajouter le log
            if log_callback:
                log_callback(line.strip())
            
            # Mettre à jour la progression
            for keyword, (value, status_text) in progress_keywords.items():
                if keyword in line and value > current_progress:
                    current_progress = value
                    if progress_callback:
                        progress_callback(current_progress, status_text)
                    break
            
            # Détecter le pourcentage dans les lignes de progression
            if "Progression:" in line and "/" in line:
                try:
                    # Extraire X/Y du texte "Progression: X/Y dossiers"
                    parts = line.split("Progression:")[1].strip().split("/")
                    current = int(parts[0].strip())
                    total = int(parts[1].split()[0].strip())
                    
                    if total > 0:
                        batch_progress = 60 + (30 * (current / total))
                        if batch_progress > current_progress:
                            current_progress = batch_progress
                            if progress_callback:
                                progress_callback(current_progress, f"Traitement: {current}/{total} dossiers")
                except:
                    pass
        
        # Lire les erreurs
        stderr_output = process.stderr.read()
        if stderr_output and log_callback:
            for line in stderr_output.split('\n'):
                if line.strip():
                    log_callback(f"ERREUR: {line.strip()}")
        
        # Attendre la fin du processus
        returncode = process.wait()
        
        if progress_callback:
            progress_callback(100, "Traitement terminé!")
        
        if returncode == 0:
            if log_callback:
                log_callback("✅ Traitement terminé avec succès!")
            return {"success": True, "message": "Synchronisation terminée avec succès"}
        else:
            if log_callback:
                log_callback(f"❌ Erreur lors du traitement (code {returncode})")
            return {"success": False, "message": f"Erreur lors du traitement (code {returncode})"}
        
    except Exception as e:
        error_msg = f"Erreur lors de la synchronisation: {str(e)}"
        if log_callback:
            log_callback(error_msg)
        return {"success": False, "message": error_msg}

# Routes Flask
CHANGELOG_PATH = os.path.join(os.path.dirname(__file__), "CHANGELOG.md")
BASE_URL = "https://github.com/betagouv/OTP-DS-to-Grist/blob/main/CHANGELOG.md"


@app.context_processor
def inject_version_info():
    version = os.getenv("APP_VERSION")
    if not version:
        return dict(version_display="v inconnu", release_url="#")

    version_clean = version[1:] if version.startswith("v") else version
    fallback_anchor = version_clean.replace(".", "")

    # 0.6 → 0\.6(\.0)?
    version_pattern = re.escape(version_clean)
    if version_clean.count(".") == 1:
        version_pattern += r"(?:\.0)?"

    pattern = re.compile(
        rf"^## \[(?P<version>{version_pattern})\]\([^)]+\) \((?P<date>\d{{4}}-\d{{2}}-\d{{2}})\)"
    )

    anchor = fallback_anchor

    try:
        with open(CHANGELOG_PATH, encoding="utf-8") as f:
            for line in f:
                match = pattern.match(line)
                if match:
                    version_from_title = match.group("version").replace(".", "")
                    date = match.group("date")
                    anchor = f"{version_from_title}-{date}"
                    break
    except FileNotFoundError:
        pass

    return dict(
        version_display=f"v {version_clean}",
        release_url=f"{BASE_URL}#{anchor}",
    )


@app.route('/')
def index():
    """Page d'accueil avec configuration"""
    config = ConfigManager.load_config()
    return render_template('index.html', config=config)

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """API pour la gestion de la configuration"""
    if request.method == 'GET':
        config = ConfigManager.load_config()
        # Pour l'affichage, masquer les informations sensibles mais garder un indicateur si elles existent
        if config['ds_api_token']:
            config['ds_api_token_masked'] = '***'
            config['ds_api_token_exists'] = True
        else:
            config['ds_api_token_masked'] = ''
            config['ds_api_token_exists'] = False
            
        if config['grist_api_key']:
            config['grist_api_key_masked'] = '***'
            config['grist_api_key_exists'] = True
        else:
            config['grist_api_key_masked'] = ''
            config['grist_api_key_exists'] = False
        
        return jsonify(config)
    
    elif request.method == 'POST':
        try:
            new_config = request.get_json()

            otp_config_id = new_config.get('otp_config_id')
            if otp_config_id:
                # Update existant
                existing_config = config_manager.load_config_by_id(
                    otp_config_id
                )

                # Fusionner les champs sensibles seulement si fournis
                # les autres toujours
                sensitive_keys = ['ds_api_token', 'grist_api_key']
                for key, value in new_config.items():
                    if key in sensitive_keys:
                        if value:  # Seulement si fourni (non vide)
                            existing_config[key] = value
                    else:
                        # Toujours mettre à jour, même vide
                        existing_config[key] = value
                # Supprimer otp_config_id du dict avant sauvegarde
                existing_config.pop('otp_config_id', None)
                success = config_manager.save_config(existing_config)

                return (
                    jsonify({
                        "success": True,
                        "message": "Configuration mise à jour avec succès",
                        "otp_config_id": otp_config_id
                    }),
                    200
                ) if success else (
                    jsonify({
                        "success": False,
                        "message": "Erreur lors de la mise à jour"
                    }),
                    500
                )
            else:
                # Création - champs minimum pour sauvegarde partielle
                required_fields = [
                    'ds_api_token',
                    'demarche_number',
                    'grist_base_url',
                    'grist_doc_id',
                    'grist_user_id'
                ]

                for field in required_fields:
                    if not new_config.get(field):
                        return jsonify(
                            {
                                "success": False,
                                "message": f"Le champ {field} est requis"
                            }
                        ), 400
                success = config_manager.save_config(new_config)
                if success:
                    db = SessionLocal()
                    try:
                        otp_config = db.query(OtpConfiguration).filter_by(
                            grist_user_id=new_config.get('grist_user_id'),
                            grist_doc_id=new_config.get('grist_doc_id')
                        ).first()
                        otp_config_id = otp_config.id if otp_config else None
                    finally:
                        db.close()
                    return jsonify({
                        "success": True,
                        "message": "Configuration sauvegardée avec succès",
                        "otp_config_id": otp_config_id
                    })
                else:
                    return jsonify(
                        {
                            "success": False,
                            "message": "Erreur lors de la sauvegarde"
                        }
                    ), 500

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {str(e)}")
            return jsonify({"success": False, "message": f"Erreur: {str(e)}"}), 500

@app.route('/api/test-connection', methods=['POST'])
def api_test_connection():
    """API pour tester les connexions"""
    data = request.get_json()
    connection_type = data.get('type')
    
    if connection_type == 'demarches':
        success, message = test_demarches_api(
            data.get('api_token'),
            data.get('api_url'),
            data.get('demarche_number')
        )
    elif connection_type == 'grist':
        success, message = test_grist_api(
            data.get('base_url'),
            data.get('api_key'),
            data.get('doc_id')
        )
    else:
        return jsonify({"success": False, "message": "Type de connexion invalide"}), 400
    
    return jsonify({"success": success, "message": message})

@app.route('/api/groups')
def api_groups():
    """API pour récupérer les groupes instructeurs"""
    config = ConfigManager.load_config()
    groups = get_available_groups(
        config['ds_api_token'],
        config['ds_api_url'],
        config['demarche_number']
    )
    return jsonify(groups)

@app.route('/api/sync-report', methods=['GET'])
def api_sync_report():
    """Route pour récupérer le rapport des synchronisations des dernières 24h"""
    db = SessionLocal()
    try:
        # Logs des dernières 24h avec jointures pour récupérer config_id, schedule_id, demarche
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        logs_query = db.query(
            SyncLog,
            OtpConfiguration.id.label('config_id'),
            UserSchedule.id.label('schedule_id'),
            OtpConfiguration.demarche_number
        ).join(
            OtpConfiguration,
            (SyncLog.grist_user_id == OtpConfiguration.grist_user_id) &
            (SyncLog.grist_doc_id == OtpConfiguration.grist_doc_id)
        ).join(
            UserSchedule,
            UserSchedule.otp_config_id == OtpConfiguration.id
        ).filter(SyncLog.timestamp >= cutoff).order_by(SyncLog.timestamp.asc()).all()

        logs_data = []
        for log, config_id, schedule_id, demarche_number in logs_query:
            logs_data.append({
                "timestamp": log.timestamp.isoformat(),
                "status": log.status,
                "message": log.message,
                "grist_user_id": log.grist_user_id,
                "grist_doc_id": log.grist_doc_id,
                "config_id": config_id,
                "schedule_id": schedule_id,
                "demarche": demarche_number
            })

        return jsonify({"logs": logs_data})
    except Exception as e:
        logger.error(f"Erreur récupération rapport sync: {str(e)}")
        return jsonify({
            "error": "Une erreur interne est survenue lors de la récupération du rapport de synchronisation."
        }), 500
    finally:
        db.close()


@app.route('/api/reload-scheduler', methods=['POST'])
def api_reload_scheduler():
    """Route pour recharger manuellement les jobs du scheduler"""
    db = SessionLocal()
    try:
        reload_scheduler_jobs()

        # Récupérer les détails des jobs
        jobs = scheduler.get_jobs()
        jobs_details = []

        for job in jobs:
            if job.id.startswith('scheduled_sync_'):
                config_id = job.args[0]
                # Récupérer les détails de la config
                config = db.query(OtpConfiguration).filter_by(id=config_id).first()
                if config:
                    # Récupérer l'ID du schedule
                    schedule = db.query(UserSchedule).filter_by(otp_config_id=config_id).first()
                    schedule_id = schedule.id if schedule else None

                    jobs_details.append({
                        "schedule_id": schedule_id,
                        "config_id": config_id,
                        "demarche": config.demarche_number,
                        "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                        "document": config.grist_doc_id
                    })

        return jsonify({
            "success": True,
            "message": "Scheduler rechargé avec succès",
            "jobs": jobs_details
        })
    except Exception as e:
        logger.error(f"Erreur rechargement scheduler: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Une erreur interne est survenue lors du rechargement du scheduler."
        }), 500
    finally:
        db.close()


@app.route('/api/start-sync', methods=['POST'])
def api_start_sync():
    """API pour démarrer la synchronisation - Version sécurisée"""
    try:
        data = request.get_json()
        
        # Ignorer la config envoyée par le client, utiliser celle de Railway
        server_config = ConfigManager.load_config()
        filters = data.get('filters', {})
        
        # Validation simple de la configuration serveur
        required_fields = ['ds_api_token', 'demarche_number', 'grist_api_key', 'grist_doc_id']
        missing_fields = []
        
        for field in required_fields:
            if not server_config.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            return jsonify({
                "success": False, 
                "message": f"Configuration incomplète. Champs manquants: {', '.join(missing_fields)}",
                "missing_fields": missing_fields
            }), 400
        
        # ✅ FORCER la mise à jour des variables d'environnement
        # Cela écrase les anciennes valeurs et donne la priorité à l'interface web
        
        logger.info(f"Filtres reçus de l'interface: {filters}")
        
        # Traitement des filtres de date
        date_debut = filters.get('date_depot_debut', '').strip()
        date_fin = filters.get('date_depot_fin', '').strip()
        
        if date_debut:
            os.environ['DATE_DEPOT_DEBUT'] = date_debut
            logger.info(f"DATE_DEPOT_DEBUT définie à: {date_debut}")
        else:
            os.environ['DATE_DEPOT_DEBUT'] = ''
            logger.info("DATE_DEPOT_DEBUT vidée (tous les dossiers)")
            
        if date_fin:
            os.environ['DATE_DEPOT_FIN'] = date_fin
            logger.info(f"DATE_DEPOT_FIN définie à: {date_fin}")
        else:
            os.environ['DATE_DEPOT_FIN'] = ''
            logger.info("DATE_DEPOT_FIN vidée (tous les dossiers)")
        
        # Traitement des statuts - CRITIQUE
        statuts = filters.get('statuts_dossiers', '').strip()
        if statuts:
            os.environ['STATUTS_DOSSIERS'] = statuts
            logger.info(f"STATUTS_DOSSIERS définis à: {statuts}")
        else:
            os.environ['STATUTS_DOSSIERS'] = ''
            logger.info("STATUTS_DOSSIERS vidé (tous les statuts)")
            
        # Traitement des groupes instructeurs - CRITIQUE  
        groupes = filters.get('groupes_instructeurs', '').strip()
        if groupes:
            os.environ['GROUPES_INSTRUCTEURS'] = groupes
            logger.info(f"GROUPES_INSTRUCTEURS définis à: {groupes}")
        else:
            os.environ['GROUPES_INSTRUCTEURS'] = ''
            logger.info("GROUPES_INSTRUCTEURS vidé (tous les groupes)")
        
        # Log de vérification - afficher les variables d'environnement finales
        logger.info("Variables d'environnement après mise à jour:")
        logger.info(f"  DATE_DEPOT_DEBUT = '{os.getenv('DATE_DEPOT_DEBUT', '')}'")
        logger.info(f"  DATE_DEPOT_FIN = '{os.getenv('DATE_DEPOT_FIN', '')}'")
        logger.info(f"  STATUTS_DOSSIERS = '{os.getenv('STATUTS_DOSSIERS', '')}'")
        logger.info(f"  GROUPES_INSTRUCTEURS = '{os.getenv('GROUPES_INSTRUCTEURS', '')}'")
        
        # Démarrer la tâche avec la configuration serveur sécurisée
        task_id = task_manager.start_task(run_synchronization_task, server_config, filters)
        
        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "Synchronisation démarrée",
            "demarche_number": server_config['demarche_number'],
            "doc_id": server_config['grist_doc_id']
        })
        
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de la synchronisation: {str(e)}")
        return jsonify({"success": False, "message": "Erreur interne du serveur"}), 500

@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    """API pour récupérer le statut d'une tâche"""
    task = task_manager.get_task(task_id)
    if task:
        return jsonify(task)
    else:
        return jsonify({"error": "Tâche non trouvée"}), 404

@app.route('/execution')
def execution():
    """Page d'exécution et de suivi"""
    return render_template('execution.html')

@app.route('/debug')
def debug():
    """Page de débogage"""
    # Vérifier la présence des fichiers requis
    required_files = [
        "grist_processor_working_all.py",
        "queries.py",
        "queries_config.py",
        "queries_extract.py",
        "queries_graphql.py",
        "queries_util.py",
        "repetable_processor.py"
    ]
    
    file_status = {}
    for file in required_files:
        file_path = os.path.join(script_dir, file)
        file_status[file] = os.path.exists(file_path)
    
    # Lister tous les fichiers du répertoire
    try:
        all_files = sorted(os.listdir(script_dir))
    except Exception as e:
        all_files = [f"Erreur: {str(e)}"]
    
    # Variables d'environnement (masquées pour la sécurité)
    env_vars = {
        "DEMARCHES_API_TOKEN": "***" if os.getenv("DEMARCHES_API_TOKEN") else "Non défini",
        "DEMARCHES_API_URL": os.getenv("DEMARCHES_API_URL", "Non défini"),
        "DEMARCHE_NUMBER": os.getenv("DEMARCHE_NUMBER", "Non défini"),
        "GRIST_BASE_URL": os.getenv("GRIST_BASE_URL", "Non défini"),
        "GRIST_API_KEY": "***" if os.getenv("GRIST_API_KEY") else "Non défini",
        "GRIST_DOC_ID": os.getenv("GRIST_DOC_ID", "Non défini")
    }
    
    filter_vars = {
        "DATE_DEPOT_DEBUT": os.getenv("DATE_DEPOT_DEBUT", "Non défini"),
        "DATE_DEPOT_FIN": os.getenv("DATE_DEPOT_FIN", "Non défini"),
        "STATUTS_DOSSIERS": os.getenv("STATUTS_DOSSIERS", "Non défini"),
        "GROUPES_INSTRUCTEURS": os.getenv("GROUPES_INSTRUCTEURS", "Non défini"),
        "BATCH_SIZE": os.getenv("BATCH_SIZE", "25"),
        "MAX_WORKERS": os.getenv("MAX_WORKERS", "2"),
        "PARALLEL": os.getenv("PARALLEL", "True")
    }
    
    return render_template('debug.html', 
                          file_status=file_status,
                          all_files=all_files,
                          env_vars=env_vars,
                          filter_vars=filter_vars,
                          script_dir=script_dir)

# WebSocket events

@socketio.on('connect')
def handle_connect():
    """Gestion de la connexion WebSocket"""
    logger.info('Client connecté')

@socketio.on('disconnect')
def handle_disconnect():
    """Gestion de la déconnexion WebSocket"""
    logger.info('Client déconnecté')

# Custom request handler pour des logs moins verbeux
class QuietWSGIRequestHandler(WSGIRequestHandler):
    def log_request(self, code='-', size='-'):
        # Ne logguer que les erreurs
        if str(code).startswith('4') or str(code).startswith('5'):
            super().log_request(code, size)

if __name__ == '__main__':
    # Désactiver les logs de werkzeug pour les requêtes statiques
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.setLevel(logging.ERROR)
    
    print("🦄 One Trick Pony DS to Grist - Version Flask")
    print(f"📁 Répertoire de travail: {script_dir}")
    print("🌐 Application disponible sur: http://localhost:5000")
    print("🔌 WebSocket activé pour les mises à jour en temps réel")
    print("💾 Gestion améliorée de la sauvegarde des configurations")
    
    # Démarrer l'application
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=False,
    )
