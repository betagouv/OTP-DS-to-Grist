from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from datetime import datetime, timezone

from sqlalchemy import Engine, inspect, text

from database.models import Base
from tests.python.db.schema_helpers import assert_database_matches_models

# Dernière révision où les colonnes de date sont en UTC sans fuseau
UTC_NAIVE_DATES_REVISION = "a2c8e8833cd0"

# Synchro finie à 00:00:10 (Paris) le 18/11/2026, enregistrée en UTC sans fuseau
STORED_UTC_NAIVE = datetime(2026, 11, 17, 23, 0, 10)


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


class TestUpgradeKeepsStoredInstants:
    """
    Les dates enregistrées en UTC sans fuseau désignent le même instant après
    passage des migrations suivantes.
    """

    def test_dates_keep_their_instant(self, empty_database, alembic_config):
        command.upgrade(alembic_config, UTC_NAIVE_DATES_REVISION)
        with empty_database.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO otp_configurations (id) VALUES (1);"
                    "INSERT INTO sync_logs (timestamp) VALUES (:moment);"
                    "INSERT INTO ip_blocklist (ip, banned_until)"
                    " VALUES ('203.0.113.7', :moment);"
                    "INSERT INTO otp_config_ips (ip, otp_config_id, seen_at)"
                    " VALUES ('203.0.113.7', 1, :moment)"
                ),
                {"moment": STORED_UTC_NAIVE},
            )

        command.upgrade(alembic_config, "head")

        # L'epoch calculé par PostgreSQL désigne l'instant, quel que soit le
        # type de la colonne (avec ou sans fuseau)
        with empty_database.connect() as connection:
            epochs = connection.execute(
                text(
                    "SELECT"
                    " (SELECT EXTRACT(epoch FROM timestamp) FROM sync_logs),"
                    " (SELECT EXTRACT(epoch FROM banned_until) FROM ip_blocklist),"
                    " (SELECT EXTRACT(epoch FROM seen_at) FROM otp_config_ips)"
                )
            ).one()

        expected = STORED_UTC_NAIVE.replace(tzinfo=timezone.utc).timestamp()
        assert [float(epoch) for epoch in epochs] == [expected] * 3


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
