# tests/python/db/conftest.py
import os
from collections.abc import Iterator

import psycopg2
import pytest
from psycopg2 import sql
from sqlalchemy import Engine, create_engine, make_url, text

from database.models import Base
from tests.python.db.runner import TEST_DATABASE_SUFFIX, TEST_DATABASE_URL_ENV

# Base présente sur tout serveur PostgreSQL, utilisée pour créer la base de test
MAINTENANCE_DATABASE = "postgres"


@pytest.fixture(scope="session")
def database_url() -> str:
    """
    URL de la base de test, créée si besoin ; les tests sont ignorés si elle
    n'est pas fournie.
    """
    url = os.getenv(TEST_DATABASE_URL_ENV)

    if not url:
        pytest.skip(f"{TEST_DATABASE_URL_ENV} non définie : tests sur base réelle ignorés")

    database_name = make_url(url).database or ""

    if not database_name.endswith(TEST_DATABASE_SUFFIX):
        pytest.fail(
            f"{TEST_DATABASE_URL_ENV} doit cibler une base dont le nom se termine "
            f"par '{TEST_DATABASE_SUFFIX}' (reçu : '{database_name}')"
        )

    _ensure_database_exists(url)

    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Iterator[Engine]:
    """Moteur SQLAlchemy sur la base de test, partagé par la session de tests."""
    test_engine = create_engine(database_url)

    yield test_engine

    test_engine.dispose()


@pytest.fixture
def empty_database(engine: Engine) -> Engine:
    """Base de test vidée des tables de l'application avant le test."""
    tables = ", ".join(Base.metadata.tables)

    with engine.begin() as connection:
        connection.execute(text(f"DROP TABLE IF EXISTS {tables} CASCADE"))

    return engine


# --- Fonctions privées ---


def _ensure_database_exists(database_url: str) -> None:
    """Crée la base de test sur son serveur si elle n'existe pas encore."""
    url = make_url(database_url)
    maintenance_url = url.set(database=MAINTENANCE_DATABASE)

    conn = psycopg2.connect(maintenance_url.render_as_string(hide_password=False))
    # CREATE DATABASE refuse de s'exécuter dans une transaction
    conn.autocommit = True

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (url.database,)
            )

            if not cursor.fetchone():
                cursor.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(url.database))
                )
    finally:
        conn.close()
