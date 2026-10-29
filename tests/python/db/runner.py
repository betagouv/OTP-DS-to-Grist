"""
Point d'entrée de `poe test-db` : lance les tests sur base réelle contre une
base de test hébergée par le service `db` de docker compose.
"""

import os
import sys

import pytest
from dotenv import load_dotenv
from sqlalchemy import make_url

# Variable distincte de DATABASE_URL, que tests/python/conftest.py force
# volontairement vers une URL invalide pour les autres suites
TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"

# Garde-fou : ces tests suppriment les tables, ils refusent toute base
# dont le nom ne signale pas explicitement une base de test
TEST_DATABASE_SUFFIX = "_test"

# URL du service `db` (secret Codespace ou .env), dont on dérive la base de test
DOCKER_DATABASE_URL_ENV = "DOCKER_DATABASE_URL"

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))


def build_test_database_url(database_url: str) -> str:
    """URL de la base de test hébergée sur le même serveur que `database_url`."""
    url = make_url(database_url)

    if not url.database:
        raise ValueError(f"Aucun nom de base dans l'URL '{url}'")

    if url.database.endswith(TEST_DATABASE_SUFFIX):
        return url.render_as_string(hide_password=False)

    test_url = url.set(database=f"{url.database}{TEST_DATABASE_SUFFIX}")

    return test_url.render_as_string(hide_password=False)


def main() -> int:
    """Lance les tests de ce dossier sur la base de test dérivée du service `db`."""
    load_dotenv()
    database_url = os.getenv(DOCKER_DATABASE_URL_ENV)

    if not database_url:
        sys.exit(f"{DOCKER_DATABASE_URL_ENV} non définie : impossible de cibler `db`")

    os.environ[TEST_DATABASE_URL_ENV] = build_test_database_url(database_url)

    return pytest.main([TESTS_DIR])
