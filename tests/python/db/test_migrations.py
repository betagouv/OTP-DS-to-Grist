from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, inspect, text

from database.models import Base
from tests.python.db.schema_helpers import (
    EXPECTED_LEGACY_ROWS,
    assert_database_matches_models,
    read_legacy_rows,
)

# Table historique, antérieure à la clé primaire `id`, avec une configuration
PRE_PRIMARY_KEY_SCHEMA = """
    CREATE TABLE otp_configurations (
        ds_api_token TEXT,
        demarche_number TEXT,
        grist_base_url TEXT,
        grist_api_key TEXT,
        grist_doc_id TEXT
    );
    INSERT INTO otp_configurations (demarche_number, grist_doc_id)
        VALUES ('123', 'docA');
"""


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
    Bascule vers Alembic : base au schéma à jour mais sans version Alembic,
    comme les bases initialisées par l'ancien code maison de DatabaseManager
    """

    def test_reaches_schema_described_by_models(self, legacy_database, alembic_config):
        _deploy_without_alembic_version(legacy_database, alembic_config)

        command.upgrade(alembic_config, "head")

        assert_database_matches_models(legacy_database)
        assert _current_revision(legacy_database) == _head_revision(alembic_config)

    def test_keeps_existing_rows(self, legacy_database, alembic_config):
        _deploy_without_alembic_version(legacy_database, alembic_config)

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


class TestUpgradeOnPrePrimaryKeyDatabase:
    """Mise à niveau d'une base antérieure à la clé primaire de otp_configurations"""

    def test_reaches_schema_described_by_models(self, empty_database, alembic_config):
        _create_pre_primary_key_database(empty_database)

        command.upgrade(alembic_config, "head")

        assert_database_matches_models(empty_database)

    def test_numbers_existing_configuration(self, empty_database, alembic_config):
        _create_pre_primary_key_database(empty_database)

        command.upgrade(alembic_config, "head")

        with empty_database.connect() as connection:
            row = connection.execute(
                text("SELECT id, demarche_number, grist_doc_id FROM otp_configurations")
            ).one()
        assert tuple(row) == (1, "123", "docA")


class TestDowngrade:
    def test_downgrade_to_base_removes_application_tables(
        self, empty_database, alembic_config
    ):
        command.upgrade(alembic_config, "head")

        command.downgrade(alembic_config, "base")

        tables = set(inspect(empty_database).get_table_names())
        assert tables.isdisjoint(Base.metadata.tables)


# --- Fonctions privées ---


def _deploy_without_alembic_version(engine: Engine, alembic_config: Config) -> None:
    """Met la base à jour puis retire la version Alembic, comme avant la bascule."""
    command.upgrade(alembic_config, "head")

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))


def _create_pre_primary_key_database(engine: Engine) -> None:
    """Crée la table historique sans clé primaire, avec une configuration."""
    with engine.begin() as connection:
        connection.execute(text(PRE_PRIMARY_KEY_SCHEMA))


def _current_revision(engine: Engine) -> str | None:
    """Version du schéma enregistrée par Alembic dans la base."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def _head_revision(alembic_config: Config) -> str | None:
    """Dernière migration connue du projet."""
    return ScriptDirectory.from_config(alembic_config).get_current_head()
