from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect

from database.database_manager import DatabaseManager
from database.models import Base
from tests.python.db.schema_helpers import (
    EXPECTED_LEGACY_ROWS,
    assert_database_matches_models,
    read_legacy_rows,
)


class TestUpgradeOnEmptyDatabase:
    """Création du schéma par les migrations sur une base neuve"""

    def test_reaches_schema_described_by_models(self, empty_database, alembic_config):
        command.upgrade(alembic_config, "head")

        assert_database_matches_models(empty_database)

    def test_records_head_revision(self, empty_database, alembic_config):
        command.upgrade(alembic_config, "head")

        assert _current_revision(empty_database) == _head_revision(alembic_config)

    def test_second_upgrade_changes_nothing(self, empty_database, alembic_config):
        command.upgrade(alembic_config, "head")

        command.upgrade(alembic_config, "head")

        assert_database_matches_models(empty_database)


class TestUpgradeOnDeployedDatabase:
    """
    Bascule vers Alembic : base déjà initialisée par DatabaseManager, sans
    version Alembic, comme les bases déployées
    """

    def test_reaches_schema_described_by_models(
        self, legacy_database, database_url, alembic_config
    ):
        DatabaseManager.init_db(database_url)

        command.upgrade(alembic_config, "head")

        assert_database_matches_models(legacy_database)
        assert _current_revision(legacy_database) == _head_revision(alembic_config)

    def test_keeps_existing_rows(self, legacy_database, database_url, alembic_config):
        DatabaseManager.init_db(database_url)

        command.upgrade(alembic_config, "head")

        assert read_legacy_rows(legacy_database) == EXPECTED_LEGACY_ROWS


class TestUpgradeOnLegacyDatabase:
    """Mise à niveau par les migrations d'une base au schéma historique"""

    def test_reaches_schema_described_by_models(self, legacy_database, alembic_config):
        command.upgrade(alembic_config, "head")

        assert_database_matches_models(legacy_database)

    def test_keeps_existing_rows(self, legacy_database, alembic_config):
        command.upgrade(alembic_config, "head")

        assert read_legacy_rows(legacy_database) == EXPECTED_LEGACY_ROWS


class TestDowngrade:
    def test_downgrade_to_base_removes_application_tables(
        self, empty_database, alembic_config
    ):
        command.upgrade(alembic_config, "head")

        command.downgrade(alembic_config, "base")

        tables = set(inspect(empty_database).get_table_names())
        assert tables.isdisjoint(Base.metadata.tables)


# --- Fonctions privées ---


def _current_revision(engine: Engine) -> str | None:
    """Version du schéma enregistrée par Alembic dans la base."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _head_revision(alembic_config: Config) -> str | None:
    """Dernière migration connue du projet."""
    return ScriptDirectory.from_config(alembic_config).get_current_head()
