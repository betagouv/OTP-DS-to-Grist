"""
Accès en local aux instances Scalingo (prod, test…) via la CLI `scalingo`.

L'application et la région d'une instance viennent de l'environnement (voir
tools/README.md) : aucun nom d'infrastructure n'est versionné.
"""

import re
import socket
import subprocess
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import make_url

SCALINGO_EXECUTABLE = "scalingo"

INSTANCE_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Variable de l'application Scalingo qui porte l'URL de la base PostgreSQL
DATABASE_URL_VARIABLE = "SCALINGO_POSTGRESQL_URL"

TUNNEL_HOST = "127.0.0.1"
TUNNEL_READY_TIMEOUT_SECONDS = 30.0
TUNNEL_STOP_TIMEOUT_SECONDS = 5.0


class ScalingoError(Exception):
    """Instance mal configurée ou commande Scalingo en échec."""


@dataclass(frozen=True)
class ScalingoInstance:
    name: str
    app: str
    region: str | None


def resolve_instance(name: str, environ: Mapping[str, str]) -> ScalingoInstance:
    """Application et région Scalingo de l'instance, lues dans l'environnement."""
    if not INSTANCE_NAME_PATTERN.match(name):
        raise ScalingoError(
            f"Nom d'instance invalide : {name!r} (minuscules, chiffres et tirets)"
        )

    app_variable = _env_variable(name, "APP")
    app = (environ.get(app_variable) or "").strip()

    if not app:
        raise ScalingoError(
            f"Instance {name!r} inconnue : définir {app_variable} "
            f"(et {_env_variable(name, 'REGION')} si besoin) dans .env"
        )

    region = (environ.get(_env_variable(name, "REGION")) or "").strip()

    return ScalingoInstance(name=name, app=app, region=region or None)


def build_command(instance: ScalingoInstance, arguments: Sequence[str]) -> list[str]:
    """Commande `scalingo` ciblant l'instance, suivie des arguments transmis."""
    region_options = ["--region", instance.region] if instance.region else []

    return [SCALINGO_EXECUTABLE, *region_options, "-a", instance.app, *arguments]


def run(instance: ScalingoInstance, arguments: Sequence[str]) -> str:
    """Sortie standard d'une commande Scalingo sur l'instance."""
    command = build_command(instance, arguments)

    try:
        completed = subprocess.run(command, capture_output=True, text=True)
    except FileNotFoundError as e:
        raise ScalingoError(
            f"CLI `{SCALINGO_EXECUTABLE}` introuvable : l'installer d'abord"
        ) from e

    if completed.returncode != 0:
        raise ScalingoError(
            f"`scalingo {' '.join(arguments)}` en échec sur {instance.name} : "
            f"{completed.stderr.strip()}"
        )

    return completed.stdout


@contextmanager
def database_tunnel(instance: ScalingoInstance) -> Iterator[str]:
    """
    Ouvre un tunnel vers la base de l'instance et rend l'URL SQLAlchemy locale.

    L'URL de la base (avec son mot de passe) est lue par `env-get` et ne vit
    qu'en mémoire. Le tunnel est fermé à la sortie, même en cas d'erreur.
    """
    remote_url = run(instance, ["env-get", DATABASE_URL_VARIABLE]).strip()

    if not remote_url:
        raise ScalingoError(f"{DATABASE_URL_VARIABLE} vide sur {instance.name}")

    port = _free_port()
    command = build_command(
        instance, ["db-tunnel", "-p", str(port), DATABASE_URL_VARIABLE]
    )

    tunnel = subprocess.Popen(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True
    )

    try:
        _wait_for_port(tunnel, port)
        yield _local_database_url(remote_url, port)
    finally:
        _stop(tunnel)


# --- Helpers privés ---


def _env_variable(name: str, suffix: str) -> str:
    """Nom de la variable d'environnement d'une instance (`prod` → `SCALINGO_PROD_APP`)."""
    return f"SCALINGO_{name.upper().replace('-', '_')}_{suffix}"


def _free_port() -> int:
    """Port local libre, attribué par le système."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((TUNNEL_HOST, 0))

        return probe.getsockname()[1]


def _wait_for_port(tunnel: subprocess.Popen, port: int) -> None:
    """Attend que le tunnel accepte les connexions, ou lève s'il échoue."""
    deadline = time.monotonic() + TUNNEL_READY_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        if tunnel.poll() is not None:
            stderr = tunnel.stderr.read().strip() if tunnel.stderr else ""
            raise ScalingoError(f"Le tunnel vers la base s'est arrêté : {stderr}")

        try:
            with socket.create_connection((TUNNEL_HOST, port), timeout=1):
                return
        except OSError:
            time.sleep(0.5)

    raise ScalingoError(
        f"Tunnel vers la base non disponible après {TUNNEL_READY_TIMEOUT_SECONDS:.0f} s"
    )


def _local_database_url(remote_url: str, port: int) -> str:
    """URL de la base distante, réécrite pour passer par le tunnel local."""
    url = make_url(remote_url).set(
        drivername="postgresql+psycopg2", host=TUNNEL_HOST, port=port
    )

    return url.render_as_string(hide_password=False)


def _stop(tunnel: subprocess.Popen) -> None:
    """Arrête le tunnel, de force s'il ne répond pas."""
    if tunnel.poll() is not None:
        return

    tunnel.terminate()

    try:
        tunnel.wait(timeout=TUNNEL_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        tunnel.kill()
        tunnel.wait()
