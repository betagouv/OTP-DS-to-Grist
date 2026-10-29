# tests/python/db/conftest.py
import os
from collections.abc import Iterator

import psycopg2
import pytest
from cryptography.fernet import Fernet
from psycopg2 import sql
from sqlalchemy import Engine, make_url, text
from sqlalchemy.orm import Session

from database.database_manager import DatabaseManager
from database.models import Base
from database.session import SessionLocal
from database.session import engine as app_engine
from tests.python.db.runner import TEST_DATABASE_URL_ENV
from utils.constants import DATABASE_URL

# Base présente sur tout serveur PostgreSQL, utilisée pour créer la base de test
MAINTENANCE_DATABASE = "postgres"


@pytest.fixture(scope="session")
def database_url() -> str:
    """
    URL de la base de test, telle que l'application la reçoit (DATABASE_URL),
    créée si besoin ; les tests sont ignorés si elle n'est pas fournie.

    Le garde-fou sur son nom est appliqué par tests/python/conftest.py.
    """
    if not os.getenv(TEST_DATABASE_URL_ENV):
        pytest.skip(f"{TEST_DATABASE_URL_ENV} non définie : tests sur base réelle ignorés")

    _ensure_database_exists(DATABASE_URL)

    return DATABASE_URL


@pytest.fixture(scope="session")
def engine(database_url: str) -> Engine:
    """Moteur de l'application (database/session.py), pointé sur la base de test."""
    return app_engine


@pytest.fixture
def empty_database(engine: Engine) -> Engine:
    """Base de test vidée des tables de l'application avant le test."""
    tables = ", ".join(Base.metadata.tables)

    with engine.begin() as connection:
        connection.execute(text(f"DROP TABLE IF EXISTS {tables} CASCADE"))

    return engine


@pytest.fixture
def initialized_database(empty_database: Engine, database_url: str) -> Engine:
    """Base de test au schéma créé par le SQL de DatabaseManager, sans données."""
    DatabaseManager.init_db(database_url)

    return empty_database


@pytest.fixture
def db_session(initialized_database: Engine) -> Iterator[Session]:
    """Session ORM de l'application sur la base de test initialisée."""
    session = SessionLocal()

    yield session

    session.close()


@pytest.fixture
def encryption_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """
    Clé Fernet valide : celle de tests/python/conftest.py ne l'est pas, ce qui
    suffit aux tests mockés mais pas au chiffrement réel des jetons.
    """
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)

    return key


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
