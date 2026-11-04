"""
Lecture des logs d'accès gunicorn tels que les restitue `scalingo logs`.

Format attendu (variable GUNICORN_CMD_ARGS de l'instance) :

    <date> <heure> <décalage> <zone> [web-1] <x-forwarded-for>|<x-real-ip>|<h> - - [<t>] "<requête>" <statut> …

Sans cette variable, gunicorn n'écrit que `<h>`, l'adresse interne du routeur
Scalingo : l'IP du client est alors inconnue.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from security.ip_blocklist import resolve_client_ip

ACCESS_LINE_PATTERN = re.compile(
    r"^(?P<date>\S+) (?P<time>\d{2}:\d{2}:\d{2})(?:\.(?P<fraction>\d+))? "
    r"(?P<offset>[+-]\d{4}) \S+ \[web-\d+\] "
    r'(?P<client>.*?) \S+ \S+ \[[^\]]+\] "(?P<method>\S+) (?P<target>\S+) [^"]*" '
    r"(?P<status>\d{3}) "
)

CONFIG_PATH_PATTERN = re.compile(r"^/api/config/(?P<id>\d+)$")

# Bruit sans intérêt pour un dépannage : ressources statiques et
# scrutation socket.io, qui représentent l'essentiel des lignes
NOISE_PATH_PREFIXES = ("/static/", "/socket.io/")


@dataclass(frozen=True)
class AccessLogEntry:
    moment: datetime
    ip: str | None
    method: str
    target: str
    status: int

    @property
    def path(self) -> str:
        return urlsplit(self.target).path

    @property
    def is_noise(self) -> bool:
        return self.path.startswith(NOISE_PATH_PREFIXES)

    @property
    def otp_config_id(self) -> int | None:
        """Configuration visée par la requête, quand son URL la porte."""
        match = CONFIG_PATH_PATTERN.match(self.path)

        if match:
            return int(match.group("id"))

        values = parse_qs(urlsplit(self.target).query).get("otp_config_id", [])

        return int(values[0]) if values and values[0].isdigit() else None


def parse_access_log(lines: Iterable[str]) -> list[AccessLogEntry]:
    """Entrées d'accès des lignes de log ; les autres lignes sont ignorées."""
    entries = (_parse_line(line) for line in lines)

    return [entry for entry in entries if entry is not None]


# --- Helpers privés ---


def _parse_line(line: str) -> AccessLogEntry | None:
    match = ACCESS_LINE_PATTERN.match(line)

    if match is None:
        return None

    # Scalingo horodate à la nanoseconde, datetime s'arrête à la microseconde
    fraction = (match.group("fraction") or "0")[:6].ljust(6, "0")
    moment = datetime.strptime(
        f"{match.group('date')} {match.group('time')}.{fraction} "
        f"{match.group('offset')}",
        "%Y-%m-%d %H:%M:%S.%f %z",
    )

    return AccessLogEntry(
        moment=moment,
        ip=_client_ip(match.group("client")),
        method=match.group("method"),
        target=match.group("target"),
        status=int(match.group("status")),
    )


def _client_ip(client: str) -> str | None:
    """IP du client, résolue comme le fait l'application pour la blocklist."""
    parts = client.split("|")

    if len(parts) != 3:
        return None

    forwarded_for, real_ip, _ = parts
    # gunicorn écrit `-` pour un en-tête absent
    headers = {
        name: value
        for name, value in (
            ("X-Forwarded-For", forwarded_for),
            ("X-Real-IP", real_ip),
        )
        if value != "-"
    }

    return resolve_client_ip(headers)
