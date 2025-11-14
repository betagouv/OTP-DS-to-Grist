"""
Application Flask pour la synchronisation Démarches Simplifiées vers Grist
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import os
import sys
import time
import threading
import subprocess
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests
from werkzeug.serving import WSGIRequestHandler
import psycopg2
from cryptography.fernet import Fernet
import logging
import atexit
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from collections import defaultdict

Base = declarative_base()

# Instance globale du scheduler APScheduler
scheduler = BackgroundScheduler()


def scheduled_sync_job(otp_config_id):
    """
    Job exécuté automatiquement par le scheduler pour une configuration donnée.
    Exécute la synchronisation et log les résultats.
    """
    logger.info(f"Démarrage de la synchronisation planifiée pour config ID: {otp_config_id}")
    logger.info(f"Scheduler running: {scheduler.running}, jobs count: {len(scheduler.get_jobs())}")

    db = SessionLocal()

    try:
        # Récupérer la configuration OTP
        otp_config = db.query(OtpConfiguration).filter_by(
            id=otp_config_id
        ).first()

        if not otp_config:
            logger.error(f"Configuration OTP non trouvée: {otp_config_id}")
            return

        # Charger la configuration complète
        config = ConfigManager.load_config(
            grist_user_id=otp_config.grist_user_id,
            grist_doc_id=otp_config.grist_doc_id
        )

        if not config:
            logger.error(f"Impossible de charger la configuration pour {otp_config_id}")
            return

        # Mettre à jour last_run
        user_schedule = db.query(UserSchedule).filter_by(otp_config_id=otp_config_id).first()
        if user_schedule:
            user_schedule.last_run = datetime.now(timezone.utc)
            db.commit()

        # Exécuter la synchronisation (sans callbacks WebSocket)
        result = run_synchronization_task(config, {})

        # Calculer next_run (prochaine exécution à minuit)
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if now.hour >= 0:  # Si on est déjà passé minuit, programmer pour demain
            next_run = next_run + timedelta(days=1)

        # Mettre à jour next_run
        if user_schedule:
            user_schedule.next_run = next_run
            db.commit()

        # Logger le résultat
        status = "success" if result.get("success") else "error"
        message = result.get("message", "Synchronisation terminée")

        # Mettre à jour le statut de la dernière exécution
        if user_schedule:
            user_schedule.last_status = status
            db.commit()

        sync_log = SyncLog(
            grist_user_id=otp_config.grist_user_id,
            grist_doc_id=otp_config.grist_doc_id,
            status=status,
            message=message
        )
        db.add(sync_log)
        db.commit()

        logger.info(f"Synchronisation planifiée terminée pour config {otp_config_id}: {status}")
        logger.info(f"next_run DB mis à jour: {next_run}")

        # En cas d'erreur, émettre une notification WebSocket
        if not result.get("success"):
            socketio.emit('sync_error', {
                'grist_user_id': otp_config.grist_user_id,
                'grist_doc_id': otp_config.grist_doc_id,
                'message': message,
                'timestamp': datetime.now(timezone.utc).isoformat()
            })

    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation planifiée pour config {otp_config_id}: {str(e)}")

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
    """
    logger.info("Rechargement des jobs du scheduler...")

    try:
        # Supprimer tous les jobs existants
        scheduler.remove_all_jobs()

        # Récupérer tous les plannings activés
        db = SessionLocal()
        try:
            active_schedules = db.query(UserSchedule).filter_by(enabled=True).all()

            # Grouper par document Grist
            schedules_by_doc = defaultdict(list)
            for schedule in active_schedules:
                # Vérifier que la configuration existe encore
                otp_config = db.query(OtpConfiguration).filter_by(id=schedule.otp_config_id).first()
                if not otp_config:
                    logger.warning(f"Configuration manquante pour schedule {schedule.id}, skipping")
                    continue
                schedules_by_doc[otp_config.grist_doc_id].append((schedule, otp_config))

            # Pour chaque document, ajouter les jobs avec décalage si nécessaire
            for doc_id, schedule_list in schedules_by_doc.items():
                if len(schedule_list) > 1:
                    # Plusieurs tâches sur le même document : espacer de 15 min
                    for i, (schedule, otp_config) in enumerate(sorted(schedule_list, key=lambda x: x[0].otp_config_id)):
                        minute = i * 15
                        job_id = f"scheduled_sync_{schedule.otp_config_id}"
                        scheduler.add_job(
                            func=scheduled_sync_job,
                            trigger=CronTrigger(hour=0, minute=minute),
                            args=[schedule.otp_config_id],
                            id=job_id,
                            name=f"Sync planifiée pour config {schedule.otp_config_id}",
                            replace_existing=True,
                            max_instances=1
                        )
                        logger.info(f"Job ajouté pour config {schedule.otp_config_id} à 00:{minute:02d} (document {doc_id})")
                else:
                    # Une seule tâche : à minuit
                    schedule, otp_config = schedule_list[0]
                    job_id = f"scheduled_sync_{schedule.otp_config_id}"
                    scheduler.add_job(
                        func=scheduled_sync_job,
                        trigger=CronTrigger(hour=0, minute=0),
                        args=[schedule.otp_config_id],
                        id=job_id,
                        name=f"Sync planifiée pour config {schedule.otp_config_id}",
                        replace_existing=True,
                        max_instances=1
                    )
                    logger.info(f"Job ajouté pour config {schedule.otp_config_id} à 00:00 (document {doc_id})")

        finally:
            db.close()

        logger.info(f"Scheduler rechargé avec {len(scheduler.get_jobs())} jobs actifs")

    except Exception as e:
        logger.error(f"Erreur lors du rechargement des jobs scheduler: {str(e)}")


class OtpConfiguration(Base):
    __tablename__ = 'otp_configurations'
    id = Column(Integer, primary_key=True)
    ds_api_token = Column(String)
    demarche_number = Column(String)
    grist_base_url = Column(String)
    grist_api_key = Column(String)
    grist_doc_id = Column(String)
    grist_user_id = Column(String)


class UserSchedule(Base):
    __tablename__ = 'user_schedules'
    id = Column(Integer, primary_key=True)
    otp_config_id = Column(
        Integer,
        ForeignKey('otp_configurations.id', ondelete='SET NULL')
    )
    frequency = Column(String, default='daily')
    enabled = Column(Boolean, default=False)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    last_status = Column(String)


class SyncLog(Base):
    __tablename__ = 'sync_logs'
    id = Column(Integer, primary_key=True)
    grist_user_id = Column(String)
    grist_doc_id = Column(String)
    status = Column(String)
    message = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


DEMARCHES_API_URL = "https://www.demarches-simplifiees.fr/api/v2/graphql"

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

# Déterminer le répertoire du script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Chargement des variables d'environnement
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required for database operations"
    )

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class TaskManager:
    """
    Gestionnaire de tâches asynchrones avec WebSocket
    pour les mises à jour en temps réel
    """

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

    SENSITIVE_KEYS = ['ds_api_token', 'grist_api_key']

    @staticmethod
    def get_env_path():
        """Retourne le chemin vers le fichier .env"""
        return os.path.join(script_dir, '.env')

    @staticmethod
    def get_encryption_key():
        """Récupère ou génère la clé de chiffrement"""
        logger.info("---get_encryption_key---")
        key = os.getenv('ENCRYPTION_KEY')

        if not key:
            raise ValueError('"ENCRYPTION_KEY" non définie')

        return key

    @staticmethod
    def get_db_connection():
        """Établit une connexion à la base de données PostgreSQL"""
        logger.info(f"DATABASE_URL: {DATABASE_URL}")
        try:
            return psycopg2.connect(DATABASE_URL)
        except Exception as e:
            logger.error(f"Erreur de connexion à la base de données: {str(e)}")
            return None

    @staticmethod
    def create_table_if_not_exists(conn):
        """Crée la table otp_configurations
        si elle n'existe pas et ajoute les colonnes manquantes"""
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp_configurations (
                    id SERIAL PRIMARY KEY,
                    ds_api_token TEXT,
                    demarche_number TEXT,
                    grist_base_url TEXT,
                    grist_api_key TEXT,
                    grist_doc_id TEXT
                )
            """)

            cursor.execute("""
                ALTER TABLE otp_configurations
                ADD COLUMN IF NOT EXISTS grist_user_id TEXT DEFAULT ''
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_logs (
                    id SERIAL PRIMARY KEY,
                    grist_user_id TEXT,
                    grist_doc_id TEXT,
                    status TEXT,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ajouter les colonnes manquantes aux tables existantes
            cursor.execute("""
                ALTER TABLE user_schedules
                ADD COLUMN IF NOT EXISTS last_status TEXT
            """)

            # Insérer une ligne vide si la table est vide
            cursor.execute("SELECT COUNT(*) FROM otp_configurations")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO otp_configurations (ds_api_token, demarche_number, grist_base_url, grist_api_key, grist_doc_id, grist_user_id)
                    VALUES ('', '', 'https://grist.numerique.gouv.fr/api', '', '', '')
                """)
            conn.commit()

    @staticmethod
    def init_db():
        """Initialise la base de données en créant les tables si nécessaire"""
        conn = ConfigManager.get_db_connection()
        if conn:
            try:
                ConfigManager.create_table_if_not_exists(conn)
                logger.info("Tables de base de données initialisées")
            finally:
                conn.close()
        else:
            logger.error("Impossible de se connecter à la base de données pour l'initialisation")

    @staticmethod
    def encrypt_value(value):
        """Chiffre une valeur"""
        logger.info("---encrypt_value---")
        try:
            if not value:
                return value

            key = ConfigManager.get_encryption_key()
            f = Fernet(key.encode())

            return f.encrypt(value.encode()).decode()
        except Exception as e:
            raise ValueError(
                f"Échec du chiffrement : {str(e)}. \
                Vérifiez la clé de chiffrement ou la valeur fournie."
            )

    @staticmethod
    def decrypt_value(value):
        """Déchiffre une valeur"""
        logger.info("---decrypt_value---")
        try:
            if not value:
                return value

            key = ConfigManager.get_encryption_key()
            f = Fernet(key.encode())

            return f.decrypt(value.encode()).decode()
        except Exception as e:
            raise ValueError(
                f"Échec du déchiffrement : {str(e)}. \
                Vérifiez la clé de chiffrement ou la valeur fournie."
            )

    @staticmethod
    def load_config(grist_user_id, grist_doc_id):
        """Charge la configuration depuis la base de données"""
        conn = ConfigManager.get_db_connection()

        try:
            with conn.cursor() as cursor:
                if not grist_user_id or not grist_doc_id:
                    raise Exception("No grist user id or doc id")

                cursor.execute("""
                    SELECT ds_api_token,
                        demarche_number,
                        grist_base_url,
                        grist_api_key,
                        grist_doc_id,
                        grist_user_id
                    FROM otp_configurations
                    WHERE grist_user_id = %s AND grist_doc_id = %s
                    LIMIT 1
                """, (grist_user_id, grist_doc_id))
                row = cursor.fetchone()

                if row:
                    config = {
                        'ds_api_token': ConfigManager.decrypt_value(row[0]) if row[0] else '',
                        'demarche_number': row[1] or '',
                        'grist_base_url': row[2] or 'https://grist.numerique.gouv.fr/api',
                        'grist_api_key': ConfigManager.decrypt_value(row[3]) if row[3] else '',
                        'grist_doc_id': row[4] or '',
                        'grist_user_id': row[5] or '',
                    }
                else:
                    config = {
                        'ds_api_token': '',
                        'demarche_number': '',
                        'grist_base_url': 'https://grist.numerique.gouv.fr/api',
                        'grist_api_key': '',
                        'grist_doc_id': '',
                        'grist_user_id': '',
                    }

                # Charger les autres valeurs depuis les variables d'environnement
                config.update({
                    'ds_api_url': DEMARCHES_API_URL,
                    'batch_size': int(os.getenv('BATCH_SIZE', '25')),
                    'max_workers': int(os.getenv('MAX_WORKERS', '2')),
                    'parallel': os.getenv('PARALLEL', 'True').lower() == 'true'
                })

                return config

        except Exception as e:
            logger.error(f"Erreur lors du chargement depuis la base: {str(e)}")
            conn.close()
            raise Exception(str(e))
        finally:
            conn.close()


    @staticmethod
    def save_config(config):
        """Sauvegarde la configuration dans la base de données"""
        conn = ConfigManager.get_db_connection()

        try:
            with conn.cursor() as cursor:
                # Préparer les valeurs, chiffrer les sensibles
                values = {
                    'ds_api_token': ConfigManager.encrypt_value(config.get('ds_api_token', '')),
                    'demarche_number': config.get('demarche_number', ''),
                    'grist_base_url': config.get('grist_base_url', 'https://grist.numerique.gouv.fr/api'),
                    'grist_api_key': ConfigManager.encrypt_value(config.get('grist_api_key', '')),
                    'grist_doc_id': config.get('grist_doc_id', ''),
                    'grist_user_id': config.get('grist_user_id', ''),
                    'grist_document_id': config.get('grist_document_id', ''),
                }

                # Vérifier si une configuration existe déjà pour ce grist_user_id et grist_doc_id
                grist_user_id = config.get('grist_user_id', '')
                grist_doc_id = config.get('grist_doc_id', '')

                if not grist_user_id or not grist_doc_id:
                    raise Exception("No grist user id or doc id")

                # Vérifier si la configuration existe
                cursor.execute("""
                    SELECT COUNT(*) FROM otp_configurations
                    WHERE grist_user_id = %s AND grist_doc_id = %s
                """, (grist_user_id, grist_doc_id))

                result = cursor.fetchone()
                exists = result[0] > 0 if result else False

                if exists:
                    # UPDATE : mettre à jour la configuration existante
                    cursor.execute("""
                        UPDATE otp_configurations SET
                        ds_api_token = %s,
                        demarche_number = %s,
                        grist_base_url = %s,
                        grist_api_key = %s,
                        grist_doc_id = %s,
                        grist_user_id = %s
                        WHERE grist_user_id = %s AND grist_doc_id = %s
                    """, (
                        values['ds_api_token'],
                        values['demarche_number'],
                        values['grist_base_url'],
                        values['grist_api_key'],
                        values['grist_doc_id'],
                        values['grist_user_id'],
                        grist_user_id,
                        grist_doc_id
                    ))
                    logger.info(f"Configuration mise à jour pour user_id={grist_user_id}, doc_id={grist_doc_id}")
                else:
                    # INSERT : créer une nouvelle configuration
                    cursor.execute("""
                        INSERT INTO otp_configurations
                        (ds_api_token, demarche_number, grist_base_url, grist_api_key, grist_doc_id, grist_user_id)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        values['ds_api_token'],
                        values['demarche_number'],
                        values['grist_base_url'],
                        values['grist_api_key'],
                        values['grist_doc_id'],
                        values['grist_user_id']
                    ))
                    logger.info(f"Nouvelle configuration créée pour user_id={grist_user_id}, doc_id={grist_doc_id}")

                conn.commit()
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde en base: {str(e)}")
            conn.close()

            return False
        finally:
            conn.close()

        return True


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
            response = requests.post(
                DEMARCHES_API_URL,
                json={
                    "query": query,
                    "variables": variables
                },
                headers=headers,
                timeout=10,
                verify=True
            )
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
            response = requests.post(
                DEMARCHES_API_URL,
                json={"query": query},
                headers=headers,
                timeout=10,
                verify=True
            )

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

def get_available_groups(api_token, demarche_number):
    """Récupère les groupes instructeurs disponibles"""
    if not all([api_token, demarche_number]):
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
        
        response = requests.post(
            DEMARCHES_API_URL,
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=10
        )
        
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
            'grist_user_id': 'GRIST_USER_ID',
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


@app.context_processor
def inject_build_time():
    return dict(build_time=datetime.now())


@app.route('/')
def index():
    """Page d'accueil avec configuration"""
    return render_template('index.html')


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """API pour la gestion de la configuration"""
    if request.method == 'GET':
        try:
            # Récupérer les paramètres de contexte Grist depuis la requête
            grist_user_id = request.args.get('grist_user_id')
            grist_doc_id = request.args.get('grist_doc_id')

            config = ConfigManager.load_config(
                grist_user_id=grist_user_id,
                grist_doc_id=grist_doc_id
            )

            # Ajouter l'id de la configuration
            db = SessionLocal()
            try:
                otp_config = db.query(OtpConfiguration).filter_by(
                    grist_user_id=grist_user_id,
                    grist_doc_id=grist_doc_id
                ).first()
                if otp_config:
                    config['otp_config_id'] = otp_config.id
            finally:
                db.close()

            # Garder les vraies valeurs pour la logique côté client,
            # masquer seulement pour affichage
            config['ds_api_token_masked'] = '***' if config['ds_api_token'] else ''
            config['ds_api_token_exists'] = bool(config['ds_api_token'])
            config['grist_api_key_masked'] = '***' if config['grist_api_key'] else ''
            config['grist_api_key_exists'] = bool(config['grist_api_key'])

            return jsonify(config)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    elif request.method == 'POST':
        try:
            new_config = request.get_json()
            
            # Validation basique
            required_fields = [
                'ds_api_token',
                'ds_api_url',
                'demarche_number',
                'grist_base_url',
                'grist_api_key',
                'grist_doc_id',
                'grist_user_id'
            ]
            
            for field in required_fields:
                if not new_config.get(field):
                    return jsonify({"success": False, "message": f"Le champ {field} est requis"}), 400
            
            # Sauvegarder la configuration
            success = ConfigManager.save_config(new_config)

            if success:
                # Récupérer l'ID de la configuration sauvegardée
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
            return jsonify(
                {"success": False, "message": f"Erreur: {str(e)}"}
            ), 500


@app.route('/api/schedule', methods=['GET', 'POST', 'DELETE'])
def api_schedule():
    """API pour gérer les plannings de synchronisation"""
    db = SessionLocal()

    try:
        if request.method == 'GET':
            otp_config_id = request.args.get('otp_config_id')
            if not otp_config_id:
                return jsonify(
                    {"success": False, "message": "otp_config_id is required"}
                ), 400

            # Trouver la configuration
            otp_config = db.query(OtpConfiguration).filter_by(
                id=otp_config_id
            ).first()

            if not otp_config:
                return jsonify(
                    {"success": False, "message": "Configuration not found"}
                ), 404

            # Vérifier si le planning existe et est activé
            schedule = db.query(UserSchedule).filter_by(
                otp_config_id=otp_config.id
            ).first()

            return jsonify({
                "success": True,
                "enabled": schedule.enabled if schedule else False,
                "last_run": schedule.last_run.isoformat() if schedule and schedule.last_run else None,
                "last_status": schedule.last_status if schedule else None
            })

        data = request.get_json()
        otp_config_id = data.get('otp_config_id')

        if not otp_config_id:
            return jsonify(
                {"success": False, "message": "otp_config_id is required"}
            ), 400

        # Trouver la configuration
        otp_config = db.query(OtpConfiguration).filter_by(
            id=otp_config_id
        ).first()

        if not otp_config:
            return jsonify(
                {"success": False, "message": "Configuration not found"}
            ), 404

        if request.method == 'POST':
            # Activer le planning
            schedule = db.query(UserSchedule).filter_by(
                otp_config_id=otp_config.id
            ).first()

            if schedule:
                schedule.enabled = True
            else:
                schedule = UserSchedule(
                    otp_config_id=otp_config.id,
                    enabled=True
                )
                db.add(schedule)
            db.commit()

            # Recharger les jobs du scheduler
            reload_scheduler_jobs()

            return jsonify({"success": True, "message": "Schedule enabled"})

        elif request.method == 'DELETE':
            # Désactiver le planning
            schedule = db.query(UserSchedule).filter_by(
                otp_config_id=otp_config.id
            ).first()

            if schedule:
                schedule.enabled = False
                db.commit()

            # Recharger les jobs du scheduler
            reload_scheduler_jobs()

            return jsonify({"success": True, "message": "Schedule disabled"})

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur dans api_schedule: {str(e)}")
        return jsonify({"success": False, "message": f"Erreur: {str(e)}"}), 500
    finally:
        db.close()


@app.route('/api/test-connection', methods=['POST'])
def api_test_connection():
    """API pour tester les connexions"""
    data = request.get_json()
    connection_type = data.get('type')

    if connection_type == 'demarches':
        success, message = test_demarches_api(
            data.get('api_token'),
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
    grist_user_id = request.args.get('grist_user_id')
    grist_doc_id = request.args.get('grist_doc_id')
    config = ConfigManager.load_config(
        grist_user_id=grist_user_id,
        grist_doc_id=grist_doc_id
    )
    groups = get_available_groups(
        config['ds_api_token'],
        config['demarche_number']
    )

    return jsonify(groups)


@app.route('/api/start-sync', methods=['POST'])
def api_start_sync():
    """API pour démarrer la synchronisation - Version sécurisée"""
    try:
        data = request.get_json()
        
        # Utiliser la config du contexte Grist fourni
        grist_user_id = str(data.get('grist_user_id', '')) if data.get('grist_user_id') is not None else None
        grist_doc_id = str(data.get('grist_doc_id', '')) if data.get('grist_doc_id') is not None else None
        server_config = ConfigManager.load_config(grist_user_id=grist_user_id, grist_doc_id=grist_doc_id)
        filters = data.get('filters', {})
        
        # Validation simple de la configuration serveur
        required_fields = ['ds_api_token', 'demarche_number', 'grist_api_key', 'grist_doc_id', 'grist_user_id']
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
        "GRIST_DOC_ID": os.getenv("GRIST_DOC_ID", "Non défini"),
        "GRIST_USER_ID": os.getenv("GRIST_USER_ID", "Non défini")
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

    return render_template(
        'debug.html',
        file_status=file_status,
        all_files=all_files,
        env_vars=env_vars,
        filter_vars=filter_vars,
        script_dir=script_dir
    )


@app.route('/utiliser-le-connecteur')
def use_otp():
    return render_template(
        'use-otp.html'
    )

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
    # Initialiser la base de données
    ConfigManager.init_db()

    # Démarrer le scheduler APScheduler
    if not scheduler.running:
        scheduler.start()
        reload_scheduler_jobs()
        logger.info("Scheduler APScheduler démarré avec rechargement des jobs")

        # Enregistrer l'arrêt propre du scheduler
        atexit.register(lambda: scheduler.shutdown(wait=True))

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
        debug=os.getenv(
            'FLASK_DEBUG',
            'False'
        ).lower() == 'true'
    )
