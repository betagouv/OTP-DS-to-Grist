"""
Croise les informations de la base pour dépanner une instance.

Usage :
    poe inspect --ip <adresse> [--app <instance>] [--since 24h] [--errors]
    poe inspect --config <otp_config_id> [--app <instance>] [--since 24h] [--errors]
    poe inspect --demarche <numéro> [--app <instance>] [--since 24h] [--errors]

Sans `--app`, la base locale (`DATABASE_URL`) est interrogée, sans logs. Avec
`--app`, un tunnel est ouvert vers la base de l'instance Scalingo (voir
tools/README.md) et ses logs d'accès sont lus. La connexion est toujours en
lecture seule.
"""

import argparse
import ipaddress
import os
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database.models import IpBlocklist, OtpConfiguration, SyncLog, UserSchedule
from tools import scalingo
from tools.access_log import AccessLogEntry, parse_access_log

SYNC_LOGS_PERIOD = timedelta(hours=24)

DEFAULT_LOGS_PERIOD = "24h"

PERIOD_PATTERN = re.compile(r"^(?P<amount>\d+)(?P<unit>[mhd])$")

PERIOD_UNITS = {"m": "minutes", "h": "hours", "d": "days"}

# Maximum de lignes restituées par `scalingo logs` : tout le tampon disponible,
# la période est filtrée ensuite côté client (pas d'option `--since`)
LOGS_MAX_LINES = 100_000

LOGS_DISPLAYED_MAX = 50

SYNC_MESSAGE_MAX_LENGTH = 60

# Le lien IP ↔ configuration ne vient que des URL qui portent un otp_config_id
PARTIAL_NOTE = "  (d'après les URL des logs, liste partielle)"

# Toute écriture est refusée par PostgreSQL : l'outil ne peut rien abîmer
READ_ONLY_CONNECT_ARGS = {"options": "-c default_transaction_read_only=on"}


def inspect_ip(
    session: Session,
    ip: str,
    now: datetime,
    entries: Sequence[AccessLogEntry] | None,
    logs_title: str,
) -> list[str]:
    """Lignes du rapport pour une adresse IP."""
    row = session.query(IpBlocklist).filter_by(ip=ip).one_or_none()
    lines = [_title(f"IP {ip}"), f"Blocage : {_ban_status(row, now)}", ""]

    if entries is None:
        return [
            *lines,
            *_unavailable("Configurations"),
            "",
            *_unavailable(logs_title),
        ]

    ip_entries = [entry for entry in entries if entry.ip == ip]
    config_ids = sorted(
        {entry.otp_config_id for entry in ip_entries if entry.otp_config_id}
    )
    configs = {
        config.id: config
        for config in session.query(OtpConfiguration).filter(
            OtpConfiguration.id.in_(config_ids)
        )
    }

    return [
        *lines,
        *_configs_table(session, config_ids, configs, ip_entries),
        PARTIAL_NOTE,
        "",
        *_logs_section(logs_title, ip_entries, with_config=False, with_ip=False),
    ]


def inspect_configs(
    session: Session,
    configs: Sequence[OtpConfiguration],
    now: datetime,
    entries: Sequence[AccessLogEntry] | None,
    logs_title: str,
) -> list[str]:
    """Lignes du rapport pour des configurations, une ligne par configuration."""
    config_ids = [config.id for config in configs]
    lines = [
        *_configs_table(
            session,
            config_ids,
            {config.id: config for config in configs},
            entries,
        ),
        "",
        *_sync_logs_table(session, config_ids, now),
        "",
    ]

    if entries is None:
        return [
            *lines,
            *_unavailable("Adresses IP"),
            "",
            *_unavailable(logs_title),
        ]

    config_entries = [
        entry for entry in entries if entry.otp_config_id in set(config_ids)
    ]

    return [
        *lines,
        *_ips_table(session, config_entries, now),
        PARTIAL_NOTE,
        "",
        *_logs_section(logs_title, config_entries, with_config=True, with_ip=True),
    ]


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
            print(f"Instance {instance.name} : lecture des logs…", file=sys.stderr)
            entries, notes = _access_log(instance, arguments)
            print(f"Instance {instance.name} : ouverture du tunnel…", file=sys.stderr)
            with scalingo.database_tunnel(instance) as database_url:
                lines = _report(database_url, arguments, entries)
            lines = [*notes, *lines]
        else:
            lines = _report(_local_database_url(), arguments, None)
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
        help="instance Scalingo (prod, test…) ; base locale, sans logs, si absent",
    )
    parser.add_argument(
        "--since",
        type=_period_argument,
        default=DEFAULT_LOGS_PERIOD,
        help=f"période des logs : 30m, 4h, 2d… (défaut {DEFAULT_LOGS_PERIOD})",
    )
    parser.add_argument(
        "--errors",
        action="store_true",
        help="logs : seulement les réponses 4xx et 5xx",
    )

    return parser.parse_args(argv)


def _period_argument(value: str) -> timedelta:
    match = PERIOD_PATTERN.match(value.strip())

    if match is None:
        raise argparse.ArgumentTypeError(
            f"période invalide : {value!r} (ex. 30m, 4h, 2d)"
        )

    unit = PERIOD_UNITS[match.group("unit")]

    return timedelta(**{unit: int(match.group("amount"))})


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


def _access_log(
    instance: scalingo.ScalingoInstance, arguments: argparse.Namespace
) -> tuple[list[AccessLogEntry], list[str]]:
    """Entrées d'accès de la période, et les avertissements sur leur complétude."""
    output = scalingo.run(instance, ["logs", "-n", str(LOGS_MAX_LINES), "-F", "web"])
    entries = parse_access_log(output.splitlines())
    start = datetime.now(timezone.utc) - arguments.since
    notes = []

    oldest = min((entry.moment for entry in entries), default=None)

    if oldest is not None and oldest > start:
        notes.append(
            f"Attention : logs disponibles seulement depuis le "
            f"{_local_time_aware(oldest)}"
        )

    if entries and all(entry.ip is None for entry in entries):
        notes.append(
            "Attention : aucune IP client dans les logs "
            "(GUNICORN_CMD_ARGS non défini sur l'instance ?)"
        )

    period_entries = [
        entry
        for entry in entries
        if entry.moment >= start and (not arguments.errors or entry.status >= 400)
    ]

    return period_entries, [*notes, ""] if notes else []


def _report(
    database_url: str,
    arguments: argparse.Namespace,
    entries: Sequence[AccessLogEntry] | None,
) -> list[str]:
    """Rapport complet, calculé dans une session en lecture seule."""
    engine = create_engine(database_url, connect_args=READ_ONLY_CONNECT_ARGS)
    # Les colonnes DateTime sont en UTC naïf
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    logs_title = _logs_title(arguments)

    try:
        with Session(engine) as session:
            if arguments.ip:
                return inspect_ip(session, arguments.ip, now, entries, logs_title)

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

            return inspect_configs(session, configs, now, entries, logs_title)
    finally:
        engine.dispose()


def _configs_table(
    session: Session,
    config_ids: Sequence[int],
    configs: Mapping[int, OtpConfiguration],
    entries: Sequence[AccessLogEntry] | None,
) -> list[str]:
    """Tableau des configurations ; les absentes de la base restent signalées."""
    lines = [_title("Configurations")]

    if not config_ids:
        return [*lines, "  aucune"]

    # La dernière ligne de planning d'une configuration fait foi
    schedules = {
        schedule.otp_config_id: schedule
        for schedule in session.query(UserSchedule)
        .filter(UserSchedule.otp_config_id.in_(config_ids))
        .order_by(UserSchedule.id)
    }
    rows = []

    for config_id in config_ids:
        config = configs.get(config_id)
        details = (
            [
                config.demarche_number or "-",
                config.grist_base_url or "-",
                config.grist_doc_id or "-",
                config.grist_user_id or "-",
                config.grist_user_email or "-",
                _schedule(schedules.get(config_id)),
                _filters(config),
            ]
            if config is not None
            else ["inexistante en base", *[""] * 6]
        )
        rows.append([str(config_id), *details, *_activity(entries, config_id)])

    headers = [
        "Config",
        "Démarche",
        "URL Grist",
        "Document Grist",
        "Utilisateur Grist",
        "Email",
        "Planning",
        "Filtres",
        "Requêtes",
        "Dernière requête",
    ]

    return [*lines, *_table(headers, rows)]


def _sync_logs_table(
    session: Session, config_ids: Sequence[int], now: datetime
) -> list[str]:
    """Tableau des synchros récentes des configurations, la plus récente en tête."""
    sync_logs = (
        session.query(SyncLog)
        .filter(SyncLog.otp_config_id.in_(config_ids))
        .filter(SyncLog.timestamp >= now - SYNC_LOGS_PERIOD)
        .order_by(SyncLog.timestamp.desc())
        .all()
    )
    lines = [_title(f"Synchros ({_period(SYNC_LOGS_PERIOD)})")]

    if not sync_logs:
        return [*lines, "  aucune"]

    headers = [
        "Config",
        "Date",
        "Mode",
        "Statut",
        "Ok",
        "Erreurs",
        "Durée",
        "Message",
    ]
    rows = [_sync_log_row(sync_log) for sync_log in sync_logs]

    return [*lines, *_table(headers, rows)]


def _ips_table(
    session: Session, entries: Sequence[AccessLogEntry], now: datetime
) -> list[str]:
    """Tableau des IP des requêtes, la plus récemment vue en tête."""
    ips = {entry.ip for entry in entries if entry.ip is not None}
    lines = [_title("Adresses IP")]

    if not ips:
        return [*lines, "  aucune"]

    bans = {
        row.ip: row
        for row in session.query(IpBlocklist).filter(IpBlocklist.ip.in_(ips))
    }
    last_seen = {
        ip: max(entry.moment for entry in entries if entry.ip == ip) for ip in ips
    }
    rows = [
        [
            ip,
            str(sum(entry.ip == ip for entry in entries)),
            _local_time_aware(last_seen[ip]),
            _ban_status(bans.get(ip), now),
        ]
        for ip in sorted(ips, key=last_seen.get, reverse=True)
    ]

    return [*lines, *_table(["IP", "Requêtes", "Dernière requête", "Blocage"], rows)]


def _activity(entries: Sequence[AccessLogEntry] | None, config_id: int) -> list[str]:
    """Nombre de requêtes visant la configuration et date de la dernière."""
    if entries is None:
        return ["-", "-"]

    config_entries = [entry for entry in entries if entry.otp_config_id == config_id]

    if not config_entries:
        return ["0", "-"]

    last = max(entry.moment for entry in config_entries)

    return [str(len(config_entries)), _local_time_aware(last)]


def _logs_section(
    title: str,
    entries: Sequence[AccessLogEntry],
    with_config: bool,
    with_ip: bool,
) -> list[str]:
    """Résumé par famille de statut, puis les requêtes les plus récentes."""
    noise = sum(entry.is_noise for entry in entries)
    shown = [entry for entry in entries if not entry.is_noise]
    families = Counter(f"{entry.status // 100}xx" for entry in shown)
    summary = ", ".join(
        f"{count} en {family}" for family, count in sorted(families.items())
    )
    header = f"{_title(title)} {len(shown)} requête(s)"

    if summary:
        header += f" : {summary}"

    lines = [header]

    if noise:
        lines.append(f"  ({noise} requête(s) /static/ et /socket.io/ masquée(s))")

    if len(shown) > LOGS_DISPLAYED_MAX:
        lines.append(
            f"  … {len(shown) - LOGS_DISPLAYED_MAX} plus ancienne(s) non affichée(s)"
        )

    for entry in shown[-LOGS_DISPLAYED_MAX:]:
        fields = [
            _local_time_aware(entry.moment),
            f"{entry.otp_config_id or '-':<6}" if with_config else "",
            f"{entry.ip or '-':<15}" if with_ip else "",
            f"{entry.method:<6}",
            entry.target,
            str(entry.status),
        ]
        lines.append("  " + "  ".join(field for field in fields if field))

    return lines


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Tableau texte aligné : en-tête, séparateur, une ligne par entrée."""
    widths = [
        max(len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]

    def line(cells: Sequence[str]) -> str:
        return (
            "  "
            + "  ".join(
                cell.ljust(width) for cell, width in zip(cells, widths)
            ).rstrip()
        )

    return [
        line(headers),
        "  " + "  ".join("─" * width for width in widths),
        *(line(row) for row in rows),
    ]


def _unavailable(title: str) -> list[str]:
    return [_title(title), "  disponible seulement avec --app (logs de l'instance)"]


def _logs_title(arguments: argparse.Namespace) -> str:
    hours = arguments.since.total_seconds() / 3600

    if hours >= 48 and hours % 24 == 0:
        period = f"{hours / 24:g} j"
    elif hours >= 1:
        period = f"{hours:g} h"
    else:
        period = f"{hours * 60:g} min"
    errors = ", erreurs seulement" if arguments.errors else ""

    return f"Logs ({period}{errors})"


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

    return ", ".join(parts) if parts else "-"


def _schedule(schedule: UserSchedule | None) -> str:
    if schedule is None:
        return "-"

    state = "actif" if schedule.enabled else "inactif"

    return f"{schedule.frequency or '-'}, {state}"


def _sync_log_row(sync_log: SyncLog) -> list[str]:
    message = (sync_log.message or "").replace("\n", " ")

    if len(message) > SYNC_MESSAGE_MAX_LENGTH:
        message = message[:SYNC_MESSAGE_MAX_LENGTH] + "…"

    return [
        str(sync_log.otp_config_id),
        _local_time(sync_log.timestamp),
        "programmée" if sync_log.auto else "manuelle",
        sync_log.status or "-",
        _count(sync_log.success_count),
        _count(sync_log.error_count),
        f"{sync_log.duration_seconds:.0f} s"
        if sync_log.duration_seconds is not None
        else "-",
        message or "-",
    ]


def _count(value: int | None) -> str:
    return str(value) if value is not None else "-"


def _local_time(moment: datetime) -> str:
    """Date UTC naïve de la base, affichée à l'heure locale."""
    return moment.replace(tzinfo=timezone.utc).astimezone().strftime("%d/%m %H:%M")


def _local_time_aware(moment: datetime) -> str:
    """Horodatage des logs, affiché à l'heure locale."""
    return moment.astimezone().strftime("%d/%m %H:%M:%S")


def _period(period: timedelta) -> str:
    return f"dernières {period.total_seconds() / 3600:.0f} h"


def _title(text: str) -> str:
    return f"== {text} =="


if __name__ == "__main__":
    sys.exit(main())
