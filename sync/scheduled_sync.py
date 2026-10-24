"""
Module de synchronisation planifiée.
Contient le scheduler APScheduler et les jobs de synchronisation automatique.
"""

import os
from dotenv import load_dotenv
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.executors.pool import ThreadPoolExecutor
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


from database.models import OtpConfiguration, UserSchedule
from configuration.config_manager import ConfigManager, ConfigNotFoundError
from sync.sequencer import sequencer
from sync.sync_manager import SyncManager
from utils.constants import EXIT_CODE_EXTERNAL_API_ERROR

logger = logging.getLogger(__name__)

load_dotenv()

from utils.constants import DATABASE_URL

SYNC_HOUR = int(os.getenv("SYNC_HOUR", "0"))
SYNC_MINUTE = int(os.getenv("SYNC_MINUTE", "0"))
SYNC_TZ = os.getenv("SYNC_TZ", "Europe/Paris")

scheduler = BackgroundScheduler(
    executors={"default": ThreadPoolExecutor(max_workers=2)}
)

config_manager = ConfigManager(DATABASE_URL)


def scheduled_sync_job(otp_config_id: int, sync_manager: SyncManager) -> None:
    """
    Job exécuté automatiquement par APScheduler pour une configuration donnée.
    Valide la configuration puis l'enfile dans le séquenceur, qui exécute
    les synchros les unes après les autres.
    - Fréquence :
      - Quotidienne, à l'heure configurée (SYNC_HOUR:SYNC_MINUTE)
        dans la timezone SYNC_TZ (défaut Europe/Paris)
      - Au démarrage de l'app
      - Lors de l'activation/désactivation d'un planning via les endpoints API
    - Condition : Uniquement pour les synchronisations activées
    - Actions :
      - Charge la configuration depuis la base
      - Enfile une étape dans le séquenceur
      - L'étape exécute run_synchronization_task et gère les erreurs :
        - Désactivation du planning : uniquement pour EXIT_CODE_EXTERNAL_API_ERROR
          (échec de la vérification des connexions : token, document ou démarche).
          Les autres erreurs, transitoires (EXIT_CODE_GRIST_READ_ERROR) ou
          inattendues, laissent le planning actif.
    """
    logger.info(
        f"Mise en file de la synchronisation planifiée pour config ID: {otp_config_id}"
    )
    logger.debug(
        f"Scheduler running: {scheduler.running}, jobs count: {len(scheduler.get_jobs())}"
    )

    try:
        config = config_manager.load_config_by_id(otp_config_id)
    except ConfigNotFoundError:
        logger.error(f"Configuration {otp_config_id} non trouvée")
        return

    step_id = sequencer.enqueue(
        otp_config_id=otp_config_id,
        grist_doc_id=config["grist_doc_id"],
        fn=lambda: _run_scheduled_sync_step(otp_config_id, config, sync_manager),
    )
    logger.info(
        f"Synchronisation planifiée {otp_config_id} enfile "
        f"(étape {step_id}, document {config['grist_doc_id']})"
    )


def reload_scheduler_jobs(sync_manager: SyncManager) -> None:
    """
    Recharge tous les jobs actifs du scheduler selon les plannings activés.
    Exécutée au démarrage et après activation/désactivation de plannings,
    pour éviter des jobs persistant pour des configs modifiées ou supprimées
    """
    logger.info("Rechargement des jobs du scheduler...")

    try:
        scheduler.remove_all_jobs()

        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        tz = ZoneInfo(SYNC_TZ)

        try:
            active_schedules = (
                db.query(UserSchedule)
                .filter_by(enabled=True)
                .filter(UserSchedule.otp_config_id.isnot(None))
                .all()
            )

            config_ids = {schedule.otp_config_id for schedule in active_schedules}
            configs_by_id: dict[int, OtpConfiguration] = {}
            if config_ids:
                configs = (
                    db.query(OtpConfiguration)
                    .filter(OtpConfiguration.id.in_(config_ids))
                    .all()
                )
                configs_by_id = {otp_config.id: otp_config for otp_config in configs}

            sorted_schedules = sorted(active_schedules, key=lambda s: s.otp_config_id)

            for schedule in sorted_schedules:
                otp_config = configs_by_id.get(schedule.otp_config_id)
                if not otp_config:
                    logger.warning(
                        f"Configuration manquante pour schedule {schedule.id}, skipping"
                    )
                    continue

                job_id = f"scheduled_sync_{schedule.otp_config_id}"

                scheduler.add_job(
                    func=scheduled_sync_job,
                    trigger=CronTrigger(
                        hour=SYNC_HOUR, minute=SYNC_MINUTE, timezone=tz
                    ),
                    args=[schedule.otp_config_id, sync_manager],
                    id=job_id,
                    name=f"Sync planifiée pour config {schedule.otp_config_id}",
                    replace_existing=True,
                    max_instances=1,
                )

                logger.info(
                    f"Job ajouté pour schedule {schedule.id} "
                    f"(config {schedule.otp_config_id}, démarche {otp_config.demarche_number}) "
                    f"à {SYNC_HOUR:02d}:{SYNC_MINUTE:02d} "
                    f"(document {otp_config.grist_doc_id})"
                )

        finally:
            db.close()

        logger.info(f"Scheduler rechargé avec {len(scheduler.get_jobs())} jobs actifs")

    except Exception as e:
        logger.error(f"Erreur lors du rechargement des jobs scheduler: {str(e)}")


# --- Helpers privés (module) ---


def _run_scheduled_sync_step(
    otp_config_id: int, config: dict, sync_manager: SyncManager
) -> None:
    """
    Corps d'une étape de synchronisation planifiée, exécuté par le séquenceur.
    Ouvre sa propre session de base uniquement pour désactiver un planning :
    l'exécution a lieu dans un thread du séquenceur, potentiellement
    longtemps après la mise en file.
    - Exécute run_synchronization_task
    - Désactive le planning sur EXIT_CODE_EXTERNAL_API_ERROR ; les autres
      codes laissent le planning actif, qui retentera au prochain créneau
    """
    logger.info(
        f"Démarrage de la synchronisation planifiée pour config {otp_config_id}"
    )

    result = sync_manager.run_synchronization_task(
        config,
        progress_callback=lambda progress, message: None,
        auto=True,
    )

    if result.get("error_code") == EXIT_CODE_EXTERNAL_API_ERROR:
        # Erreur définitive (token invalide, document ou démarche
        # introuvable) : relancer chaque jour ne servirait à rien.
        logger.error(
            f"Erreur API externe pour config {otp_config_id}: {result.get('message')}"
        )
        _disable_schedule(otp_config_id)
        return

    status = "success" if result.get("success") else "error"

    logger.info(
        f"Synchronisation planifiée terminée pour config {otp_config_id}: {status}"
    )


def _disable_schedule(otp_config_id: int) -> None:
    """Désactive le planning d'une configuration ; une erreur est loguée sans relance."""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        user_schedule = (
            db.query(UserSchedule).filter_by(otp_config_id=otp_config_id).first()
        )

        if not user_schedule:
            logger.warning(f"Aucun planning trouvé pour config {otp_config_id}")
            return

        user_schedule.enabled = False
        db.commit()
        logger.info(f"Planning désactivé pour config {otp_config_id} à cause d'erreur")

    except Exception as e:
        logger.error(
            f"Erreur lors de la désactivation du planning pour config {otp_config_id}: {str(e)}"
        )

    finally:
        db.close()
