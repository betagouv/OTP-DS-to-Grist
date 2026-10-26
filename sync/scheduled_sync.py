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


from database.models import UserSchedule
from database.session import SessionLocal
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

DAILY_SYNC_JOB_ID = "daily_scheduled_sync"
# Retard toléré au déclenchement du job quotidien (process occupé, mise en
# veille) : au-delà, l'exécution du jour est abandonnée
DAILY_SYNC_MISFIRE_GRACE_SECONDS = 3600

# Un seul job quotidien : un seul thread suffit, les synchros elles-mêmes
# s'exécutent dans le séquenceur
scheduler = BackgroundScheduler(
    executors={"default": ThreadPoolExecutor(max_workers=1)}
)

config_manager = ConfigManager(DATABASE_URL)


def scheduled_sync_job(otp_config_id: int, sync_manager: SyncManager) -> None:
    """
    Mise en file de la synchronisation planifiée d'une configuration donnée,
    appelée par daily_sync_job pour chaque planning activé.
    Valide la configuration puis l'enfile dans le séquenceur, qui exécute
    les synchros les unes après les autres.
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
        fn=lambda: _run_scheduled_sync_step(otp_config_id, sync_manager),
    )
    logger.info(
        f"Synchronisation planifiée {otp_config_id} enfile "
        f"(étape {step_id}, document {config['grist_doc_id']})"
    )


def daily_sync_job(sync_manager: SyncManager) -> None:
    """
    Job quotidien unique, déclenché à SYNC_HOUR:SYNC_MINUTE (timezone SYNC_TZ) :
    enfile dans le séquenceur chaque configuration dont le planning est activé.
    Les plannings sont lus à chaque exécution : une activation ou une
    désactivation est prise en compte sans recharger le scheduler. Une
    configuration en échec n'empêche pas d'enfiler les suivantes.
    """
    otp_config_ids = _enabled_schedule_config_ids()
    logger.info(
        f"Synchronisation quotidienne : {len(otp_config_ids)} planning(s) activé(s)"
    )

    for otp_config_id in otp_config_ids:
        try:
            scheduled_sync_job(otp_config_id, sync_manager)
        except Exception as e:
            logger.error(
                f"Mise en file impossible pour config {otp_config_id}: {str(e)}"
            )


def register_daily_sync_job(sync_manager: SyncManager) -> None:
    """Programme le job quotidien unique ; un job déjà programmé est remplacé."""
    scheduler.add_job(
        func=daily_sync_job,
        trigger=CronTrigger(
            hour=SYNC_HOUR, minute=SYNC_MINUTE, timezone=ZoneInfo(SYNC_TZ)
        ),
        args=[sync_manager],
        id=DAILY_SYNC_JOB_ID,
        name="Synchronisation quotidienne des plannings activés",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=DAILY_SYNC_MISFIRE_GRACE_SECONDS,
    )
    logger.info(
        f"Synchronisation quotidienne programmée à "
        f"{SYNC_HOUR:02d}:{SYNC_MINUTE:02d} ({SYNC_TZ})"
    )


# --- Helpers privés (module) ---


def _enabled_schedule_config_ids() -> list[int]:
    """Identifiants des configurations dont le planning est activé, par ordre croissant."""
    db = SessionLocal()

    try:
        rows = (
            db.query(UserSchedule.otp_config_id)
            .filter_by(enabled=True)
            .filter(UserSchedule.otp_config_id.isnot(None))
            .order_by(UserSchedule.otp_config_id)
            .all()
        )
        return [row.otp_config_id for row in rows]
    finally:
        db.close()


def _is_schedule_enabled(otp_config_id: int) -> bool:
    """Indique si le planning de la configuration est activé en base."""
    db = SessionLocal()

    try:
        schedule = (
            db.query(UserSchedule).filter_by(otp_config_id=otp_config_id).first()
        )
        return bool(schedule and schedule.enabled)
    finally:
        db.close()


def _run_scheduled_sync_step(otp_config_id: int, sync_manager: SyncManager) -> None:
    """
    Corps d'une étape de synchronisation planifiée, exécuté par le séquenceur.
    L'exécution a lieu dans un thread du séquenceur, potentiellement
    longtemps après la mise en file : le planning et la configuration sont
    donc relus au démarrage de l'étape.
    - Ignore l'étape si le planning a été désactivé ou la configuration
      supprimée depuis la mise en file
    - Exécute run_synchronization_task avec la configuration à jour
    - Désactive le planning sur EXIT_CODE_EXTERNAL_API_ERROR ; les autres
      codes laissent le planning actif, qui retentera au prochain créneau
    """
    if not _is_schedule_enabled(otp_config_id):
        logger.info(
            f"Planning désactivé depuis la mise en file pour config {otp_config_id}, "
            "synchronisation ignorée"
        )
        return

    try:
        config = config_manager.load_config_by_id(otp_config_id)
    except ConfigNotFoundError:
        logger.info(
            f"Configuration {otp_config_id} supprimée depuis la mise en file, "
            "synchronisation ignorée"
        )
        return

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
