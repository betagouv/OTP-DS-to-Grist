"""
Croise les informations de la base pour dépanner une instance.

Usage :
    poe inspect --ip <adresse> [--app <instance>]
    poe inspect --config <otp_config_id> [--app <instance>]
    poe inspect --demarche <numéro> [--app <instance>]

Sans `--app`, la base locale (`DATABASE_URL`) est interrogée. Avec `--app`, un
tunnel est ouvert vers la base de l'instance Scalingo (voir tools/README.md).
La connexion est toujours en lecture seule.
"""

import argparse
import ipaddress
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import IpBlocklist, OtpConfiguration, SyncLog, UserSchedule
from tools import scalingo

SYNC_LOGS_PERIOD = timedelta(hours=24)

SYNC_MESSAGE_MAX_LENGTH = 200

# Toute écriture est refusée par PostgreSQL : l'outil ne peut rien abîmer
READ_ONLY_CONNECT_ARGS = {"options": "-c default_transaction_read_only=on"}


def inspect_ip(session: Session, ip: str, now: datetime) -> list[str]:
    """Lignes du rapport pour une adresse IP."""
    row = session.query(IpBlocklist).filter_by(ip=ip).one_or_none()

    return [_title(f"IP {ip}"), f"Blocage : {_ban_status(row, now)}"]


def inspect_configs(
    session: Session, configs: Sequence[OtpConfiguration], now: datetime
) -> list[str]:
    """Lignes du rapport pour des configurations, un bloc par configuration."""
    lines = []

    for config in configs:
        lines.extend(_config_block(session, config, now))
        lines.append("")

    return lines[:-1]


def find_configs(
    session: Session, config_id: int | None, demarche_number: str | None
) -> list[OtpConfiguration]:
    """Configurations visées par un identifiant ou par un numéro de démarche."""
    query = session.query(OtpConfiguration)

    if config_id is not None:
        query = query.filter(OtpConfiguration.id == config_id)
    else:
        query = query.filter(OtpConfiguration.demarche_number == demarche_number)

    return query.order_by(OtpConfiguration.id).all()


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    arguments = _parse_arguments(argv)

    try:
        if arguments.app:
            instance = scalingo.resolve_instance(arguments.app, os.environ)
            print(f"Instance {instance.name} : ouverture du tunnel…", file=sys.stderr)
            with scalingo.database_tunnel(instance) as database_url:
                lines = _report(database_url, arguments)
        else:
            lines = _report(_local_database_url(), arguments)
    except Exception as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        return 1

    print("\n".join(lines))

    return 0


# --- Helpers privés ---


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="poe inspect",
        description="Croise les informations de la base pour dépanner une instance.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--ip", type=_ip_address, help="adresse IP")
    target.add_argument("--config", type=int, help="otp_config_id")
    target.add_argument("--demarche", type=int, help="numéro de démarche")
    parser.add_argument(
        "--app",
        help="instance Scalingo (prod, test…) ; base locale si absent",
    )

    return parser.parse_args(argv)


def _ip_address(value: str) -> str:
    """Adresse IP normalisée, comme l'enregistre la blocklist."""
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"adresse IP invalide : {value!r}") from e


def _local_database_url() -> str:
    """URL SQLAlchemy de la base locale."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL non définie : impossible de cibler la base")

    # Même conversion que utils/constants.py : le projet utilise psycopg2
    return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)


def _report(database_url: str, arguments: argparse.Namespace) -> list[str]:
    """Rapport complet, calculé dans une session en lecture seule."""
    engine = create_engine(database_url, connect_args=READ_ONLY_CONNECT_ARGS)
    # Les colonnes DateTime sont en UTC naïf
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        with Session(engine) as session:
            if arguments.ip:
                return inspect_ip(session, arguments.ip, now)

            demarche_number = (
                str(arguments.demarche) if arguments.demarche is not None else None
            )
            configs = find_configs(session, arguments.config, demarche_number)

            if not configs:
                target = (
                    f"configuration {arguments.config}"
                    if arguments.config is not None
                    else f"démarche {demarche_number}"
                )
                return [f"Aucune configuration pour la {target}"]

            return inspect_configs(session, configs, now)
    finally:
        engine.dispose()


def _config_block(
    session: Session, config: OtpConfiguration, now: datetime
) -> list[str]:
    """Bloc du rapport pour une configuration : réglages, planning, synchros."""
    schedule = (
        session.query(UserSchedule)
        .filter_by(otp_config_id=config.id)
        .order_by(UserSchedule.id.desc())
        .first()
    )
    sync_logs = (
        session.query(SyncLog)
        .filter(SyncLog.otp_config_id == config.id)
        .filter(SyncLog.timestamp >= now - SYNC_LOGS_PERIOD)
        .order_by(SyncLog.timestamp.desc())
        .all()
    )

    lines = [
        _title(f"Configuration #{config.id}"),
        f"Démarche : {config.demarche_number or '-'}",
        f"Grist : {config.grist_base_url or '-'}",
        f"  document {config.grist_doc_id or '-'}, "
        f"utilisateur {config.grist_user_id or '-'}",
        f"Jetons : DS {_presence(config.ds_api_token)}, "
        f"Grist {_presence(config.grist_api_key)}",
        f"Filtres : {_filters(config)}",
        f"Planning : {_schedule(schedule)}",
        "",
        _title(f"Synchros ({_period(SYNC_LOGS_PERIOD)})"),
    ]

    if not sync_logs:
        return [*lines, "  aucune"]

    return [*lines, *(_sync_log_line(sync_log) for sync_log in sync_logs)]


def _ban_status(row: IpBlocklist | None, now: datetime) -> str:
    if row is None:
        return "jamais bannie"

    count = f"{row.ban_count} bannissement(s)"

    if row.banned_until is not None and row.banned_until > now:
        return f"bannie jusqu'au {_local_time(row.banned_until)} ({count})"

    last_end = (
        f", dernier terminé le {_local_time(row.banned_until)}"
        if row.banned_until is not None
        else ""
    )

    return f"non bannie ({count}{last_end})"


def _filters(config: OtpConfiguration) -> str:
    parts = [
        f"{label} {value}"
        for label, value in (
            ("dépôt depuis", config.filter_date_start),
            ("dépôt jusqu'au", config.filter_date_end),
            ("statuts", config.filter_statuses),
            ("groupes", config.filter_groups),
        )
        if value
    ]

    return ", ".join(parts) if parts else "aucun"


def _schedule(schedule: UserSchedule | None) -> str:
    if schedule is None:
        return "aucun"

    state = "actif" if schedule.enabled else "inactif"

    return f"{schedule.frequency or '-'}, {state}"


def _sync_log_line(sync_log: SyncLog) -> str:
    mode = "programmée" if sync_log.auto else "manuelle"
    counts = (
        f"{sync_log.success_count or 0} ok / {sync_log.error_count or 0} erreur(s)"
        if sync_log.success_count is not None or sync_log.error_count is not None
        else ""
    )
    duration = (
        f"{sync_log.duration_seconds:.0f} s"
        if sync_log.duration_seconds is not None
        else ""
    )
    message = (sync_log.message or "").replace("\n", " ")

    if len(message) > SYNC_MESSAGE_MAX_LENGTH:
        message = message[:SYNC_MESSAGE_MAX_LENGTH] + "…"

    fields = [
        _local_time(sync_log.timestamp),
        f"{mode:<10}",
        f"{sync_log.status or '-':<8}",
        counts,
        duration,
        f"« {message} »" if message else "",
    ]

    return "  " + "  ".join(field for field in fields if field)


def _local_time(moment: datetime) -> str:
    """Date UTC naïve de la base, affichée à l'heure locale."""
    return moment.replace(tzinfo=timezone.utc).astimezone().strftime("%d/%m %H:%M")


def _presence(value: str | None) -> str:
    return "présent" if value else "absent"


def _period(period: timedelta) -> str:
    return f"dernières {period.total_seconds() / 3600:.0f} h"


def _title(text: str) -> str:
    return f"== {text} =="


if __name__ == "__main__":
    sys.exit(main())
