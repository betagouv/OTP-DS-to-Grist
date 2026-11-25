"""
Application Flask pour la synchronisation Démarches Simplifiées vers Grist
"""

import json
import logging
import os
import re
import threading
import time
from collections.abc import Iterable
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask,
    Response,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException, InternalServerError

from api.responses import config_not_found_response, error_response
from configuration.config_manager import (
    ConfigIncompleteError,
    ConfigManager,
    ConfigNotFoundError,
)
from configuration.config_usage import ConfigUsage
from database.models import OtpConfiguration, SyncLog, UserSchedule
from database.session import SessionLocal
from dn.client import (
    DemarcheAccessError,
    DnUnavailableError,
    get_groups,
    require_demarche_access,
)
from grist.base_url import (
    GristBaseUrlImmutableError,
    GristBaseUrlNotAllowedError
)
from grist.utils import key_access_level
from security.ip_blocklist import (
    is_whitelisted,
    parse_whitelist,
    purge_stale_hits,
    register_hit,
    resolve_client_ip,
    should_ignore_path,
)
from security.ip_blocklist_store import IpBlocklistStore
from security.widget_auth import authorize_request
from sync.scheduled_sync import (
    DAILY_SYNC_JOB_ID,
    register_daily_sync_job,
    scheduler,
)
from sync.live_tracking import init_live_tracking, socketio
from sync.sequencer import sequencer
from sync.sync_manager import (
    SyncManager,
    SyncSeriesAlreadyRunningError,
    missing_sync_fields,
)
from utils.formatter import to_local_iso
from utils.api_validator import test_grist_api
from utils.constants import (
    CHANGELOG_PATH,
    GITHUB_CHANGELOG_BASE_URL,
    DATABASE_URL,
    GRIST_KEY_ACCESS_CACHE_TTL_SECONDS,
    HELP_LINK_FAQ,
    HELP_LINK_GRIST_API_KEY,
    HELP_LINK_DN_TOKEN_API,
    IP_BLOCKLIST_CACHE_TTL_SECONDS,
    IP_BLOCKLIST_THRESHOLD,
    IP_BLOCKLIST_WINDOW_SECONDS,
    IP_BLOCKLIST_WHITELIST,
    VITE_DEV_ORIGIN,
)

# Chargement des variables d'environnement
load_dotenv()

# Schéma de la base : appliqué par les migrations (database/migrations/README.md)

# Instance de ConfigManager
config_manager = ConfigManager(DATABASE_URL)

# Configuration de l'application Flask
app = Flask(__name__)

sync_manager = SyncManager(notify_callback=socketio.emit)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-key-change-in-production-2024")

init_live_tracking(app, sync_manager)

# Configuration du logging pour Flask
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Protection anti-scanner : bannie les IP qui produisent trop de réponses 4xx.
# Les compteurs vivent en mémoire, les bannissements en base :
# voir le dossier `security/`.
ip_blocklist_store = IpBlocklistStore(cache_ttl=IP_BLOCKLIST_CACHE_TTL_SECONDS)
ip_blocklist_whitelist = parse_whitelist(IP_BLOCKLIST_WHITELIST.split(","))
ip_blocklist_hits: dict[str, list[float]] = {}

# Trace des IP qui utilisent chaque configuration, pour l'exploitation
config_usage = ConfigUsage()

# Cache du niveau d'accès de la clé Grist sur le document, alimenté par
# GET /api/config : (base_url, api_key, doc_id) -> (horodatage, niveau).
_grist_key_access_cache: dict[tuple[str, str, str], tuple[float, str]] = {}

# Taille au-delà de laquelle le cache d'accès est vidé d'un coup :
# le nombre de clés/configs est faible, l'invalidation fine est inutile.
_GRIST_KEY_ACCESS_CACHE_MAX_ENTRIES = 256


def _cached_grist_key_access(base_url: str, api_key: str, doc_id: str) -> str:
    """Niveau d'accès de la clé sur le document, avec cache TTL en mémoire.

    Renvoie un niveau explicite `unavailable` quand Grist n'a pas répondu,
    pour distinguer une indisponibilité transitoire d'un refus d'accès.
    """
    cache_key = (base_url, api_key, doc_id)
    cached = _grist_key_access_cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < GRIST_KEY_ACCESS_CACHE_TTL_SECONDS:
        return cached[1]

    level = key_access_level(base_url, api_key, doc_id)

    if len(_grist_key_access_cache) >= _GRIST_KEY_ACCESS_CACHE_MAX_ENTRIES:
        _grist_key_access_cache.clear()
    _grist_key_access_cache[cache_key] = (time.monotonic(), level)

    return level


def _blocklist_target_ip() -> str | None:
    """
    Adresse IP à prendre en compte pour la blocklist.

    Retourne None si elle n'est pas exploitable ou si elle est en liste
    blanche, pour que les deux hooks partagent exactement le même filtre.
    """
    client_ip = resolve_client_ip(request.headers)

    if client_ip is None or is_whitelisted(client_ip, ip_blocklist_whitelist):
        return None

    return client_ip


def _server_error_response() -> Response:
    """
    Réponse 500, au même format que celle d'une erreur non rattrapée
    (JSON sous /api, page HTML ailleurs).
    """
    return app.make_response(handle_http_exception(InternalServerError()))


def _mark_configs_used(otp_config_ids: Iterable[int]) -> None:
    """
    Note que le client de la requête en cours utilise ces configurations.

    Sans IP exploitable, rien n'est noté. Un échec est journalisé sans faire
    échouer la route : la trace sert l'exploitation, pas l'utilisateur.
    """
    client_ip = resolve_client_ip(request.headers)

    if client_ip is None:
        return

    try:
        config_usage.mark_used(client_ip, otp_config_ids)
    except Exception:
        logger.exception(
            "Utilisation des configurations non enregistrée pour l'IP %s", client_ip
        )


@app.before_request
def check_banned_ip() -> tuple[Response, int] | None:
    """
    Refuse la requête si l'IP est bannie.

    La décision est retenue dans `g.ip_banned`, pour que le comptage après la
    route la reprenne sans relire le store.
    """
    client_ip = _blocklist_target_ip()

    if client_ip is None:
        return None

    try:
        g.ip_banned = ip_blocklist_store.is_banned(client_ip)
    except SQLAlchemyError:
        # Sans la base, l'IP ne peut être ni refusée ni autorisée
        logger.exception(
            "Vérification du bannissement impossible pour l'IP %s : "
            "base de données en défaut",
            client_ip,
        )
        abort(500)

    if g.ip_banned:
        logger.warning("Requête refusée : IP bannie %s", client_ip)
        return jsonify({"error": "Forbidden"}), 403

    return None


@app.before_request
def check_widget_token() -> tuple[Response, int] | None:
    """Vérifie le jeton widget porté par la requête."""
    return authorize_request(request, config_manager)


@app.after_request
def check_and_count_ip(response: Response) -> Response:
    """
    Compte les réponses 4xx de l'IP, et la bannie si le seuil est atteint.

    Le comptage se fait sur la réponse, donc il englobe tous les 4xx : ceux du
    routage comme ceux produits par les vues. Il ne dépend pas des codes, donc
    un 4xx qu'on ne peut pas encore prévoir compte aussi.

    Une IP déjà bannie n'est pas comptée.
    Son bannissement ne peut donc pas s'allonger pendant qu'il est actif.
    L'état de bannissement est celui décidé avant la route (`g.ip_banned`).

    À chaque comptage, les IP dont plus aucune erreur n'est récente sont oubliées.
    """
    global ip_blocklist_hits

    if not 400 <= response.status_code < 500:
        return response

    client_ip = _blocklist_target_ip()

    if client_ip is None or should_ignore_path(request.path):
        return response

    if g.get("ip_banned", False):
        return response

    now = time.time()
    ip_blocklist_hits, hits = register_hit(
        purge_stale_hits(
            ip_blocklist_hits,
            now,
            IP_BLOCKLIST_WINDOW_SECONDS
        ),
        client_ip,
        now,
        IP_BLOCKLIST_WINDOW_SECONDS
    )

    if hits >= IP_BLOCKLIST_THRESHOLD:
        try:
            banned_until = ip_blocklist_store.apply_ban(client_ip)
        except SQLAlchemyError:
            # Une erreur levée après la route serait journalisée une seconde
            # fois par Flask : la réponse 500 est donc renvoyée directement
            logger.exception(
                "Bannissement de l'IP %s non enregistré : base de données en défaut",
                client_ip,
            )
            return _server_error_response()

        banned_until_local = banned_until.astimezone()

        logger.warning(
            "IP bannie jusqu'au %s après %d hits dans la fenêtre : %s",
            banned_until_local,
            hits,
            client_ip,
        )

    return response


def _shutdown_background_tasks() -> None:
    """
    Arrêt à la sortie du process : le scheduler d'abord, pour qu'aucun job
    n'enfile pendant l'arrêt, puis le séquenceur, qui n'attend que la synchro
    en cours (redéploiement pendant une longue file).
    """
    if scheduler.running:
        scheduler.shutdown(wait=True)
    sequencer.shutdown(cancel_pending=True)
    sync_manager.shutdown_series()


# Démarrage du scheduler au niveau module : c'est le seul endroit commun aux
# deux points d'entrée, gunicorn (`app:app`) et `dev.py` (`poe dev`). Seul le
# processus qui sert l'appli importe ce module : le processus parent du
# reloader de `dev.py` ne l'importe jamais, aucun cron ne part donc deux fois.
if not scheduler.running:
    scheduler.start()
    register_daily_sync_job(sync_manager)
    logger.info("Scheduler APScheduler démarré au chargement du module")
    # Pas atexit.register : à la sortie, Python attend la fin des threads du
    # pool (qui exécutent alors toute la file) avant les handlers atexit.
    # threading._register_atexit (API privée) passe avant cette attente, et
    # avant le handler du pool, enregistré plus tôt (ordre inverse).
    threading._register_atexit(_shutdown_background_tasks)


# Routes Flask

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
        release_url=f"{GITHUB_CHANGELOG_BASE_URL}#{anchor}",
    )


@app.context_processor
def inject_env_name():
    return dict(env_name=os.getenv("ENV", ""))


@app.context_processor
def inject_sync_schedule_hour():
    hour = os.getenv("SYNC_HOUR", "0")
    minute = os.getenv("SYNC_MINUTE", "0")
    return dict(sync_schedule_time=f"{int(hour):02d}h{int(minute):02d}")


@app.route("/")
def index():
    """Page d'accueil avec configuration"""
    return render_template("index.html")


@app.route("/wip")
def wip() -> Response:
    """Ancienne adresse du front Vue, redirigée temporairement vers l'accueil."""
    logger.warning("[REDIRECTION /wip] Accès à /wip, redirigé vers /")
    return redirect(url_for("index"))


@app.errorhandler(ConfigNotFoundError)
def handle_config_not_found(e: ConfigNotFoundError):
    """Réponse 404 unique pour une configuration absente en base."""
    return error_response(str(e), 404)


@app.errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    """Erreurs HTTP en JSON sous /api, rendu HTML conservé ailleurs."""
    if not request.path.startswith("/api/"):
        return e
    return error_response(str(e.description), int(e.code or 500))


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    """API pour la gestion de la configuration"""
    if request.method == "GET":
        try:
            # L'identité vient du jeton widget, vérifié par l'authentification.
            identity = g.get("widget_identity") or {}
            grist_user_id = str(identity.get("userId") or "")
            grist_doc_id = str(identity.get("docId") or "")

            configs = config_manager.load_config(
                grist_user_id=grist_user_id, grist_doc_id=grist_doc_id
            )
            _mark_configs_used(config["otp_config_id"] for config in configs)

            # Masquer les tokens et ajouter les flags pour chaque config
            for config in configs:
                config["has_ds_token"] = bool(config.get("ds_api_token"))
                config["has_grist_key"] = bool(config.get("grist_api_key"))
                api_key = config.get("grist_api_key")
                if api_key:
                    # Niveau d'accès de la clé sur le document (lecture seule,
                    # éditeur…), pour que le front puisse prévenir l'utilisateur
                    # d'une clé qui ne peut pas écrire.
                    config["grist_key_access"] = _cached_grist_key_access(
                        config.get("grist_base_url") or "",
                        api_key,
                        str(config.get("grist_doc_id") or ""),
                    )
                config.pop("ds_api_token", None)
                config.pop("grist_api_key", None)

            return jsonify({"configs": configs})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 500

    elif request.method == "POST":
        try:
            new_config = request.get_json()

            new_config = ConfigManager.normalize_config(new_config)

            identity = g.get("widget_identity")
            if identity:
                new_config["grist_user_id"] = str(identity.get("userId", ""))
                new_config["grist_doc_id"] = str(identity.get("docId", ""))

            otp_config_id = new_config.get("otp_config_id")
            if otp_config_id:
                # Update existant - Charger la config pour vérification
                existing_config = config_manager.load_config_by_id(otp_config_id)

                # Vérification de sécurité : IDs doivent correspondre
                if existing_config.get("grist_user_id") != new_config.get(
                    "grist_user_id"
                ) or existing_config.get("grist_doc_id") != new_config.get(
                    "grist_doc_id"
                ):
                    return jsonify({"success": False, "message": "Forbidden"}), 403

                # Passer le dict à save_config() qui gère l'update par ID et les tokens
                config_manager.save_config(new_config)

                return jsonify(
                    {
                        "success": True,
                        "message": "Configuration mise à jour avec succès",
                        "otp_config_id": otp_config_id,
                    }
                ), 200
            else:
                otp_config_id = config_manager.save_config(new_config)
                _mark_configs_used([otp_config_id])

                return jsonify(
                    {
                        "success": True,
                        "message": "Configuration sauvegardée avec succès",
                        "otp_config_id": otp_config_id,
                    }
                )

        except GristBaseUrlImmutableError:
            return jsonify(
                {
                    "success": False,
                    "message": "L'URL de base Grist ne peut pas être modifiée",
                }
            ), 403
        except GristBaseUrlNotAllowedError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        except ConfigIncompleteError as e:
            return jsonify({"success": False, "message": str(e)}), 400
        except ConfigNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {str(e)}")
            return jsonify(
                {"success": False, "message": "Erreur interne lors de la sauvegarde."}
            ), 500


@app.route("/api/config/<int:otp_config_id>", methods=["DELETE"])
def api_delete_config(otp_config_id):
    """API pour supprimer une configuration"""
    db = SessionLocal()

    try:
        # Trouver la configuration
        otp_config = db.query(OtpConfiguration).filter_by(id=otp_config_id).first()

        if not otp_config:
            return config_not_found_response(otp_config_id)

        # Supprimer la configuration (les FK sont gérées automatiquement)
        db.delete(otp_config)
        db.commit()

        logger.info(f"Configuration supprimée: {otp_config_id}")
        return jsonify(
            {"success": True, "message": "Configuration supprimée avec succès"}
        )

    except Exception as e:
        db.rollback()
        logger.error(
            f"Erreur lors de la suppression de la configuration {otp_config_id}: {str(e)}"
        )
        return jsonify(
            {"success": False, "message": "Erreur interne lors de la suppression"}
        ), 500
    finally:
        db.close()


@app.route("/api/schedule", methods=["GET", "POST", "DELETE"])
def api_schedule():
    """API pour gérer les plannings de synchronisation"""
    db = SessionLocal()

    try:
        if request.method == "GET":
            otp_config_id = request.args.get("otp_config_id")
            if not otp_config_id:
                return jsonify(
                    {"success": False, "message": "otp_config_id is required"}
                ), 400

            # Trouver la configuration
            otp_config = db.query(OtpConfiguration).filter_by(id=otp_config_id).first()

            if not otp_config:
                return config_not_found_response(otp_config_id)

            # Vérifier si le planning existe et est activé
            schedule = (
                db.query(UserSchedule).filter_by(otp_config_id=otp_config.id).first()
            )

            enabled = schedule.enabled if schedule else False

            # Un seul job quotidien pour tous les plannings activés
            job = scheduler.get_job(DAILY_SYNC_JOB_ID) if enabled else None
            next_run = job.next_run_time.isoformat() if job and job.next_run_time else None

            return jsonify(
                {
                    "success": True,
                    "enabled": enabled,
                    "next_run": next_run,
                }
            )

        data = request.get_json()
        otp_config_id = data.get("otp_config_id")

        if not otp_config_id:
            return jsonify(
                {"success": False, "message": "otp_config_id is required"}
            ), 400

        # Trouver la configuration
        otp_config = db.query(OtpConfiguration).filter_by(id=otp_config_id).first()

        if not otp_config:
            return config_not_found_response(otp_config_id)

        if request.method == "POST":
            if not otp_config.grist_api_key:
                return jsonify(
                    {"success": False, "message": "Clé grist manquante"}
                ), 403

            # Activer le planning
            schedule = (
                db.query(UserSchedule).filter_by(otp_config_id=otp_config.id).first()
            )

            if schedule:
                schedule.enabled = True
            else:
                schedule = UserSchedule(otp_config_id=otp_config.id, enabled=True)
                db.add(schedule)
            db.commit()

            return jsonify({"success": True, "message": "Schedule enabled"})

        elif request.method == "DELETE":
            # Désactiver le planning
            schedule = (
                db.query(UserSchedule).filter_by(otp_config_id=otp_config.id).first()
            )

            if schedule:
                schedule.enabled = False
                db.commit()

            return jsonify({"success": True, "message": "Schedule disabled"})

    except Exception as e:
        db.rollback()
        logger.error(f"Erreur dans api_schedule: {str(e)}")
        return jsonify(
            {"success": False, "message": "Une erreur interne est survenue."}
        ), 500
    finally:
        db.close()


@app.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    """
    Route pour tester les connexions vers les autres API

    Avec type='demarches' ou 'grist' : teste uniquement l'API spécifiée
    """
    data = request.get_json() or {}
    connection_type = data.get("type")

    if connection_type == "demarches":
        api_token = data.get("api_token")
        demarche_number = data.get("demarche_number")
        otp_config_id = data.get("otp_config_id")

        if not api_token:
            if otp_config_id:
                try:
                    config = config_manager.load_config_by_id(otp_config_id)
                except ConfigNotFoundError:
                    raise
                except Exception:
                    logger.error(
                        f"Configuration introuvable pour otp_config_id={otp_config_id}"
                    )
                    return jsonify(
                        {"success": False, "message": "Configuration introuvable"}
                    ), 500
                api_token = config.get("ds_api_token", "")
            if not api_token:
                return jsonify(
                    {"success": False, "message": "Token API non fourni"}
                ), 400

        try:
            demarche = require_demarche_access(api_token, demarche_number)
        except DemarcheAccessError as error:
            if isinstance(error, DnUnavailableError):
                logger.error(
                    f"Test de l'API Démarche Numérique impossible : {error.__cause__ or error}"
                )
            success, message, title = False, str(error), None
        else:
            title = demarche.get("title") or "Sans titre"
            success, message = True, f"Connexion réussie! Démarche trouvée: {title}"
    elif connection_type == "grist":
        api_key = data.get("api_key")
        base_url = data.get("base_url")
        doc_id = data.get("doc_id")
        otp_config_id = data.get("otp_config_id")

        if not api_key:
            if otp_config_id:
                try:
                    config = config_manager.load_config_by_id(otp_config_id)
                except ConfigNotFoundError:
                    raise
                except Exception:
                    logger.error(
                        f"Configuration introuvable pour otp_config_id={otp_config_id}"
                    )
                    return jsonify(
                        {"success": False, "message": "Configuration introuvable"}
                    ), 500
                api_key = config.get("grist_api_key", "")
                base_url = base_url or config.get("grist_base_url", "")
                doc_id = doc_id or config.get("grist_doc_id", "")
            if not api_key:
                return jsonify(
                    {"success": False, "message": "Clé API Grist non fourni"}
                ), 400

        success, message = test_grist_api(base_url, api_key, doc_id)
        title = None
    else:
        return jsonify(
            {"success": False, "message": "Type de connexion inconnu"}
        ), 400

    return jsonify({"success": success, "message": message, "title": title})


@app.route("/api/groups")
def api_groups():
    """API pour récupérer les groupes instructeurs"""
    try:
        otp_config_id = request.args.get("otp_config_id")
        if not otp_config_id:
            return error_response("otp_config_id requis", 400)

        config = config_manager.load_config_by_id(otp_config_id)
        groups = get_groups(config["ds_api_token"], config["demarche_number"])

        return jsonify(groups)

    except ConfigNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des groupes : {str(e)}")
        return error_response(
            "Erreur lors de la récupération des groupes", 400
        )


@app.route("/api/sync-log/latest-by-demarche", methods=["GET"])
def api_sync_log_latest_by_demarche():
    """
    Dernière synchronisation de chaque démarche sauvegardée de l'utilisateur et
    du document du jeton widget, dans l'ordre de l'écran ; les démarches jamais
    synchronisées sont absentes
    """
    identity = g.get("widget_identity") or {}
    grist_user_id = str(identity.get("userId") or "")
    grist_doc_id = str(identity.get("docId") or "")

    db = SessionLocal()

    try:
        configs = config_manager.load_config(
            grist_user_id=grist_user_id, grist_doc_id=grist_doc_id
        )

        # Les lignes sont insérées en fin de synchro : l'identifiant le plus
        # grand est la plus récente
        latest_ids = (
            select(func.max(SyncLog.id))
            .where(
                SyncLog.otp_config_id.in_(
                    [config["otp_config_id"] for config in configs]
                )
            )
            .group_by(SyncLog.otp_config_id)
        )
        latest_syncs = {
            sync.otp_config_id: sync
            for sync in db.scalars(select(SyncLog).where(SyncLog.id.in_(latest_ids)))
        }

        return jsonify(
            {
                "success": True,
                "syncs": [
                    {
                        "otp_config_id": config["otp_config_id"],
                        "demarche_number": config["demarche_number"],
                        "timestamp": to_local_iso(sync.timestamp),
                        "status": sync.status,
                        "success_count": sync.success_count,
                        "error_count": sync.error_count,
                        "message": sync.message,
                        "auto": sync.auto,
                    }
                    for config in configs
                    if (sync := latest_syncs.get(config["otp_config_id"]))
                ],
            }
        )

    except Exception as e:
        logger.error(
            f"Erreur lors de la lecture des dernières synchronisations par démarche: {str(e)}"
        )
        return jsonify({"success": False, "message": "Erreur interne du serveur"}), 500
    finally:
        db.close()


@app.route("/api/start-sync", methods=["POST"])
def api_start_sync():
    """API pour démarrer la synchronisation - Version sécurisée"""
    try:
        data = request.get_json()

        # Utiliser l'ID de config fourni
        otp_config_id = data.get("otp_config_id")
        if not otp_config_id:
            return jsonify(
                {"success": False, "message": "ID de configuration requis"}
            ), 400
        server_config = config_manager.load_config_by_id(otp_config_id)

        # Validation simple de la configuration serveur
        missing_fields = missing_sync_fields(server_config)

        if missing_fields:
            return jsonify(
                {
                    "success": False,
                    "message": f"Configuration incomplète. Champs manquants: {', '.join(missing_fields)}",
                    "missing_fields": missing_fields,
                }
            ), 400

        # Démarrer la tâche avec la configuration serveur sécurisée
        task_id = sync_manager.start_sync(server_config, auto=False)
        _mark_configs_used([server_config["otp_config_id"]])

        return jsonify(
            {
                "success": True,
                "task_id": task_id,
                "message": "Synchronisation démarrée",
                "demarche_number": server_config["demarche_number"],
                "doc_id": server_config["grist_doc_id"],
            }
        )

    except ConfigNotFoundError:
        raise
    except Exception as e:
        logger.error(f"Erreur lors du démarrage de la synchronisation: {str(e)}")
        return jsonify({"success": False, "message": "Erreur interne du serveur"}), 500


@app.route("/api/start-sync-all", methods=["POST"])
def api_start_sync_all():
    """
    Démarre la synchronisation de toutes les démarches de l'utilisateur
    (« Tout synchroniser »), une par une. Les démarches incomplètes sont ignorées.
    """
    # L'identité vient du jeton widget, vérifié par l'authentification.
    identity = g.get("widget_identity") or {}
    grist_user_id = str(identity.get("userId") or "")
    grist_doc_id = str(identity.get("docId") or "")

    try:
        configs = [
            config
            for config in config_manager.load_config(
                grist_user_id=grist_user_id, grist_doc_id=grist_doc_id
            )
            if not missing_sync_fields(config)
        ]

        if not configs:
            return jsonify(
                {"success": False, "message": "Aucune démarche à synchroniser"}
            ), 400

        task_ids = sync_manager.start_sync_series(
            (grist_user_id, grist_doc_id), configs
        )
        _mark_configs_used(config["otp_config_id"] for config in configs)

        return jsonify(
            {
                "success": True,
                "message": "Synchronisation de toutes les démarches démarrée",
                "syncs": [
                    {
                        "otp_config_id": config["otp_config_id"],
                        "demarche_number": config["demarche_number"],
                        "task_id": task_id,
                    }
                    for config, task_id in zip(configs, task_ids)
                ],
            }
        )

    except SyncSeriesAlreadyRunningError:
        return jsonify(
            {
                "success": False,
                "message": "Une synchronisation de toutes les démarches est déjà en cours",
            }
        ), 409
    except Exception as e:
        logger.error(
            f"Erreur lors du démarrage de la synchronisation de toutes les démarches: {str(e)}"
        )
        return jsonify({"success": False, "message": "Erreur interne du serveur"}), 500


@app.context_processor
def inject_help_links():
    return {
        "help_links": {
            "faq": HELP_LINK_FAQ,
            "token_api": HELP_LINK_DN_TOKEN_API,
            "grist_api_key": HELP_LINK_GRIST_API_KEY,
        }
    }


def vite_asset(entry: str = "src/main.js") -> dict[str, str | None]:
    if app.debug:
        return {"js": f"{VITE_DEV_ORIGIN}/{entry}", "css": None}

    manifest_path = Path("static/dist/.vite/manifest.json")
    manifest = json.loads(manifest_path.read_text())
    entry_data = manifest[entry]
    css_list = entry_data.get("css", [])

    return {
        "js": url_for("static", filename=f"dist/{entry_data['file']}"),
        "css": url_for("static", filename=f"dist/{css_list[0]}") if css_list else None,
    }


app.jinja_env.globals["vite_asset"] = vite_asset


@app.context_processor
def inject_vite():
    return {"vite_asset": vite_asset}
