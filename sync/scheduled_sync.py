"""
Module de synchronisation planifiée.
Contient le scheduler APScheduler et les jobs de synchronisation automatique.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from zoneinfo import ZoneInfo

from database.models import OtpConfiguration, UserSchedule, SyncLog
from configuration.config_manager import ConfigManager
from utils.socketio import socketio

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

SYNC_HOUR = int(os.getenv("SYNC_HOUR", "0"))
SYNC_MINUTE = int(os.getenv("SYNC_MINUTE", "0"))
SYNC_TZ = os.getenv("SYNC_TZ", "Europe/Paris")

scheduler = BackgroundScheduler(
    executors={"default": ThreadPoolExecutor(max_workers=2)}
)

config_manager = ConfigManager(DATABASE_URL)


def scheduled_sync_job(otp_config_id, sync_manager, notify_callback=None):
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
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    logger.info(
        f"Démarrage de la synchronisation planifiée pour config ID: {otp_config_id}"
    )
    logger.info(
        f"Scheduler running: {scheduler.running}, jobs count: {len(scheduler.get_jobs())}"
    )

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        otp_config = db.query(OtpConfiguration).filter_by(id=otp_config_id).first()

        if not otp_config:
            logger.error(f"Configuration OTP non trouvée: {otp_config_id}")
            return

        config = config_manager.load_config_by_id(otp_config_id)

        if not config:
            logger.error(f"Configuration {otp_config_id} non trouvée")
            return

        user_schedule = (
            db.query(UserSchedule).filter_by(otp_config_id=otp_config_id).first()
        )
        if user_schedule:
            user_schedule.last_run = datetime.now(timezone.utc)
            db.commit()

        result = sync_manager.run_synchronization_task(config)

        now = datetime.now(timezone.utc)
        next_run = now.replace(
            hour=SYNC_HOUR, minute=SYNC_MINUTE, second=0, microsecond=0
        )

        if now >= next_run:
            next_run = next_run + timedelta(days=1)

        if user_schedule:
            user_schedule.next_run = next_run
            db.commit()

        status = "success" if result.get("success") else "error"
        message = result.get("message", "Synchronisation terminée")

        if user_schedule:
            user_schedule.last_status = status
            db.commit()

        sync_log = SyncLog(
            grist_user_id=otp_config.grist_user_id,
            grist_doc_id=otp_config.grist_doc_id,
            status=status,
            message=message,
        )
        db.add(sync_log)
        db.commit()

        logger.info(
            f"Synchronisation planifiée terminée pour config {otp_config_id}: {status}"
        )
        logger.info(f"next_run DB mis à jour: {next_run}")

        if not result.get("success"):
            if notify_callback:
                notify_callback(
                    "sync_error",
                    {
                        "grist_user_id": otp_config.grist_user_id,
                        "grist_doc_id": otp_config.grist_doc_id,
                        "message": message,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            else:
                socketio.emit(
                    "sync_error",
                    {
                        "grist_user_id": otp_config.grist_user_id,
                        "grist_doc_id": otp_config.grist_doc_id,
                        "message": message,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

    except Exception as e:
        logger.error(
            f"Erreur lors de la synchronisation planifiée pour config {otp_config_id}: {str(e)}"
        )

        try:
            user_schedule = (
                db.query(UserSchedule).filter_by(otp_config_id=otp_config_id).first()
            )

            if user_schedule:
                user_schedule.enabled = False
                db.commit()
                logger.info(
                    f"Planning désactivé pour config {otp_config_id} à cause d'erreur"
                )
        except Exception:
            logger.error(f"Erreur lors de la désactivation du planning")

        try:
            otp_config = db.query(OtpConfiguration).filter_by(id=otp_config_id).first()

            if otp_config:
                sync_log = SyncLog(
                    grist_user_id=otp_config.grist_user_id,
                    grist_doc_id=otp_config.grist_doc_id,
                    status="error",
                    message=f"Erreur scheduler: {str(e)}",
                )
                db.add(sync_log)
                db.commit()

                if notify_callback:
                    notify_callback(
                        "sync_error",
                        {
                            "grist_user_id": otp_config.grist_user_id,
                            "grist_doc_id": otp_config.grist_doc_id,
                            "message": f"Erreur de synchronisation planifiée: {str(e)}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                else:
                    socketio.emit(
                        "sync_error",
                        {
                            "grist_user_id": otp_config.grist_user_id,
                            "grist_doc_id": otp_config.grist_doc_id,
                            "message": f"Erreur de synchronisation planifiée: {str(e)}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
        except Exception:
            logger.error(f"Erreur lors du logging de l'erreur scheduler")

    finally:
        db.close()


def reload_scheduler_jobs(sync_manager, notify_callback=None):
    """
    Recharge tous les jobs actifs du scheduler selon les plannings activés.
    Exécutée au démarrage et après activation/désactivation de plannings,
    pour éviter des jobs persistant pour des configs modifiées ou supprimées
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    logger.info("Rechargement des jobs du scheduler...")

    try:
        scheduler.remove_all_jobs()

        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        tz = ZoneInfo(SYNC_TZ) if SYNC_TZ != "UTC" else None

        try:
            active_schedules = (
                db.query(UserSchedule)
                .filter_by(enabled=True)
                .filter(UserSchedule.otp_config_id.isnot(None))
                .all()
            )

            sorted_schedules = sorted(active_schedules, key=lambda s: s.otp_config_id)

            for i, schedule in enumerate(sorted_schedules):
                otp_config = (
                    db.query(OtpConfiguration)
                    .filter_by(id=schedule.otp_config_id)
                    .first()
                )
                if not otp_config:
                    logger.warning(
                        f"Configuration manquante pour schedule {schedule.id}, skipping"
                    )
                    continue

                total_offset = SYNC_MINUTE + i * 5
                minute = total_offset % 60
                hour_offset = total_offset // 60
                hour = (SYNC_HOUR + hour_offset) % 24
                job_id = f"scheduled_sync_{schedule.otp_config_id}"
                scheduler.add_job(
                    func=scheduled_sync_job,
                    trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
                    args=[schedule.otp_config_id, sync_manager, notify_callback],
                    id=job_id,
                    name=f"Sync planifiée pour config {schedule.otp_config_id}",
                    replace_existing=True,
                    max_instances=1,
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
