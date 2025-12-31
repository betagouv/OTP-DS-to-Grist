"""
Application Flask pour la synchronisation Démarches Simplifiées vers Grist
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests
from werkzeug.serving import WSGIRequestHandler
import logging
import atexit
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

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required for database operations"
    )

# Initialiser la base de données au chargement du module
DatabaseManager.init_db(DATABASE_URL)

# Instance de ConfigManager
config_manager = ConfigManager(DATABASE_URL)

# Configuration de la synchronisation planifiée
SYNC_HOUR = int(os.getenv('SYNC_HOUR', '0'))
SYNC_MINUTE = int(os.getenv('SYNC_MINUTE', '0'))
SYNC_TZ = os.getenv('SYNC_TZ', 'Europe/Paris')

# SQLAlchemy setup (doit être avant les fonctions qui l'utilisent)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def scheduled_sync_job(otp_config_id):
    """
    Job exécuté automatiquement par APScheduler pour une configuration donnée.
    Exécute la synchronisation complète,
    met à jour les statuts en base de données,
    et gère les erreurs avec notifications et désactivation automatique.
    - Fréquence :
      - Quotidienne, à l'heure configurée (SYNC_HOUR:SYNC_MINUTE)
        dans la timezone SYNC_TZ (défaut Europe/Paris),
        ou décalée de 15 mn pour chaque config supplémentaire
      - Au démarrage de l'app
      - Lors de l'activation/désactivation d'un planning via les endpoints API
    - Condition : Uniquement pour les synchronisations activées
    - Actions :
      - Charge la configuration depuis la base
      - Met à jour last_run et calcule next_run dans UserSchedule
      - Exécute run_synchronization_task
      - Met à jour last_status et crée une entrée SyncLog
      - En cas d'erreur :
        - Notification WebSocket : uniquement pour success: false.
        - Désactivation du planning : uniquement pour les exceptions.
    """

    logger.info(f"Démarrage de la synchronisation planifiée pour config ID: {otp_config_id}")
    logger.info(f"Scheduler running: {scheduler.running}, jobs count: {len(scheduler.get_jobs())}")

    db = SessionLocal()

    try:
        # Récupérer le modèle OtpConfiguration par id
        otp_config = db.query(OtpConfiguration).filter_by(
            id=otp_config_id
        ).first()

        if not otp_config:
            logger.error(f"Configuration OTP non trouvée: {otp_config_id}")
            return

        # Charger la configuration complète
        config = config_manager.load_config_by_id(otp_config_id)

        if not config:
            logger.error(f"Configuration {otp_config_id} non trouvée")
            return

        # Mettre à jour last_run
        user_schedule = db.query(UserSchedule).filter_by(
            otp_config_id=otp_config_id
        ).first()
        if user_schedule:
            user_schedule.last_run = datetime.now(timezone.utc)
            db.commit()

        # Exécuter la synchronisation
        result = sync_task_manager.run_synchronization_task(config)

        # Calculer next_run (prochaine exécution à l'heure configurée)
        now = datetime.now(timezone.utc)
        next_run = now.replace(
            hour=SYNC_HOUR,
            minute=SYNC_MINUTE,
            second=0,
            microsecond=0
        )

        # Si on est déjà passé l'heure programmée, programmer pour demain
        if now >= next_run:
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

        # Désactiver le planning en cas d'erreur
        try:
            user_schedule = db.query(UserSchedule).filter_by(
                otp_config_id=otp_config_id
            ).first()

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
                return False, f"Erreur API: {'; '.join(
                    [
                        e.get(
                            'message',
                            'Erreur inconnue'
                        ) for e in result['errors']
                    ]
                )}"

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
            except Exception:
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

        groupes = result.get(
            "data", {}
        ).get(
            "demarche", {}
        ).get(
            "groupeInstructeurs", []
        )
        return [
            (groupe.get("number"), groupe.get("label")) for groupe in groupes
        ]

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des groupes instructeurs: {str(e)}")
        return []


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

            config = config_manager.load_config(
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

            # Supprimer les tokens sensibles, ajouter flags d'existence
            config['has_ds_token'] = bool(config.get('ds_api_token'))
            config['has_grist_key'] = bool(config.get('grist_api_key'))
            config.pop('ds_api_token', None)
            config.pop('grist_api_key', None)

            return jsonify(config)
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

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
                return jsonify({
                    "success": True,
                    "message": "Configuration mise à jour avec succès",
                    "otp_config_id": otp_config_id
                }) if success else jsonify(
                    {
                        "success": False,
                        "message": "Erreur lors de la mise à jour"
                    }
                   ), 500
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
            return jsonify(
                {
                    "success": False,
                    "message": "Erreur interne lors de la sauvegarde."
                }
            ), 500


@app.route('/api/config/<int:otp_config_id>', methods=['DELETE'])
def api_delete_config(otp_config_id):
    """API pour supprimer une configuration"""
    db = SessionLocal()

    try:
        # Trouver la configuration
        otp_config = db.query(
            OtpConfiguration
        ).filter_by(
            id=otp_config_id
        ).first()

        if not otp_config:
            return jsonify(
                {
                    "success": False,
                    "message": "Configuration non trouvée"
                }
            ), 404

        # Supprimer la configuration (les FK sont gérées automatiquement)
        db.delete(otp_config)
        db.commit()

        # Recharger les jobs du scheduler
        reload_scheduler_jobs()

        logger.info(f"Configuration supprimée: {otp_config_id}")
        return jsonify(
            {
                "success": True,
                "message": "Configuration supprimée avec succès"
            }
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur lors de la suppression de la configuration {otp_config_id}: {str(e)}")
        return jsonify(
            {
                "success": False,
                "message": "Erreur interne lors de la suppression"
            }
        ), 500
    finally:
        db.close()


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
        return jsonify(
            {
                "success": False,
                "message": "Une erreur interne est survenue."
            }
        ), 500
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
        return jsonify(
            {"success": False, "message": "Type de connexion invalide"}
        ), 400

    return jsonify({"success": success, "message": message})


@app.route('/api/groups')
def api_groups():
    """API pour récupérer les groupes instructeurs - Mode hybride"""
    try:
        # Mode 1: Priorité à otp_config_id si fourni
        otp_config_id = request.args.get('otp_config_id')
        if otp_config_id:
            config = config_manager.load_config_by_id(otp_config_id)
        else:
            # Mode 2: Utiliser les paramètres Grist (compatibilité)
            grist_user_id = request.args.get('grist_user_id')
            grist_doc_id = request.args.get('grist_doc_id')
            config = config_manager.load_config(
                grist_user_id=grist_user_id,
                grist_doc_id=grist_doc_id
            )

        groups = get_available_groups(
            config['ds_api_token'],
            config['demarche_number']
        )

        return jsonify(groups)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des groupes : {str(e)}")
        return jsonify(
            {'error': 'Erreur lors de la récupération des groupes'}
        ), 400


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

        # Utiliser l'ID de config fourni
        otp_config_id = data.get('otp_config_id')
        if not otp_config_id:
            return jsonify(
                {
                    "success": False,
                    "message": "ID de configuration requis"
                }
            ), 400
        server_config = config_manager.load_config_by_id(otp_config_id)

        # Validation simple de la configuration serveur
        required_fields = [
            'ds_api_token',
            'demarche_number',
            'grist_api_key',
            'grist_doc_id',
            'grist_user_id'
        ]
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

        # Démarrer la tâche avec la configuration serveur sécurisée
        task_id = sync_task_manager.start_sync(server_config)

        return jsonify({
            "success": True,
            "task_id": task_id,
            "message": "Synchronisation démarrée",
            "demarche_number": server_config['demarche_number'],
            "doc_id": server_config['grist_doc_id']
        })

    except Exception as e:
        logger.error(f"Erreur lors du démarrage de la synchronisation: {str(e)}")
        return jsonify(
            {
                "success": False,
                "message": "Erreur interne du serveur"
            }
        ), 500


@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    """API pour récupérer le statut d'une tâche"""
    task = sync_task_manager.get_task(task_id)
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
        "DEMARCHES_API_URL": f"Constante: {DEMARCHES_API_URL}",
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
