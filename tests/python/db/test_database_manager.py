from sqlalchemy import Engine, inspect, make_url, text

from database.database_manager import DatabaseManager
from database.models import Base

# Schéma tel que le créait la première version de DatabaseManager (commit
# a4229ea) : état de départ des bases déployées avant les migrations suivantes
LEGACY_SCHEMA = """
    CREATE TABLE otp_configurations (
        id SERIAL PRIMARY KEY,
        ds_api_token TEXT,
        demarche_number TEXT,
        grist_base_url TEXT,
        grist_api_key TEXT,
        grist_doc_id TEXT,
        grist_user_id TEXT DEFAULT ''
    );
    CREATE TABLE user_schedules (
        id SERIAL PRIMARY KEY,
        otp_config_id INTEGER,
        frequency TEXT DEFAULT 'daily',
        enabled BOOLEAN DEFAULT FALSE,
        last_run TIMESTAMP,
        next_run TIMESTAMP,
        last_status TEXT,
        FOREIGN KEY (otp_config_id) REFERENCES otp_configurations(id) ON DELETE SET NULL
    );
    CREATE TABLE sync_logs (
        id SERIAL PRIMARY KEY,
        grist_user_id TEXT,
        grist_doc_id TEXT,
        status TEXT,
        message TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
"""

LEGACY_DATA = """
    INSERT INTO otp_configurations
        (id, demarche_number, grist_doc_id, grist_user_id)
        VALUES (1, '123', 'docA', 'userA');
    INSERT INTO user_schedules (otp_config_id, enabled, last_status)
        VALUES (1, TRUE, 'success');
    INSERT INTO sync_logs (grist_user_id, grist_doc_id, status)
        VALUES ('userA', 'docA', 'success');
"""


def _columns_by_table(engine: Engine) -> dict[str, set[str]]:
    inspector = inspect(engine)

    return {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in inspector.get_table_names()
    }


def _schema(engine: Engine) -> dict[str, dict]:
    """Description du schéma : colonnes (type, nullabilité, défaut) et clés étrangères."""
    inspector = inspect(engine)

    return {
        table: {
            "columns": {
                column["name"]: (
                    str(column["type"]),
                    column["nullable"],
                    column["default"],
                )
                for column in inspector.get_columns(table)
            },
            "foreign_keys": sorted(
                (
                    tuple(fk["constrained_columns"]),
                    fk["referred_table"],
                    fk["options"].get("ondelete"),
                )
                for fk in inspector.get_foreign_keys(table)
            ),
            "unique_constraints": sorted(
                tuple(unique["column_names"])
                for unique in inspector.get_unique_constraints(table)
            ),
        }
        for table in inspector.get_table_names()
    }


class TestInitDb:
    """Création et migration du schéma sur une vraie base PostgreSQL"""

    def test_creates_all_application_tables(self, empty_database, database_url):
        DatabaseManager.init_db(database_url)

        tables = set(inspect(empty_database).get_table_names())
        assert tables == set(Base.metadata.tables)

    def test_is_idempotent(self, empty_database, database_url):
        DatabaseManager.init_db(database_url)
        columns_after_first_run = _columns_by_table(empty_database)

        DatabaseManager.init_db(database_url)

        assert _columns_by_table(empty_database) == columns_after_first_run


class TestInitDbOnLegacyDatabase:
    """Mise à niveau d'une base créée par la première version du schéma"""

    def test_reaches_same_schema_as_new_database(self, empty_database, database_url):
        DatabaseManager.init_db(database_url)
        new_database_schema = _schema(empty_database)
        self._create_legacy_database(empty_database)

        DatabaseManager.init_db(database_url)

        assert _schema(empty_database) == new_database_schema

    def test_keeps_existing_rows(self, empty_database, database_url):
        self._create_legacy_database(empty_database)

        DatabaseManager.init_db(database_url)

        with empty_database.connect() as connection:
            otp_configuration = connection.execute(
                text(
                    "SELECT demarche_number, grist_doc_id, grist_user_id "
                    "FROM otp_configurations WHERE id = 1"
                )
            ).one()
            schedule = connection.execute(
                text("SELECT otp_config_id, enabled FROM user_schedules")
            ).one()
            sync_log = connection.execute(
                text("SELECT grist_doc_id, status, auto FROM sync_logs")
            ).one()

        assert tuple(otp_configuration) == ("123", "docA", "userA")
        assert tuple(schedule) == (1, True)
        # Colonne NOT NULL ajoutée après coup : remplie par sa valeur par défaut
        assert tuple(sync_log) == ("docA", "success", True)

    @staticmethod
    def _create_legacy_database(engine: Engine) -> None:
        """Remplace les tables de l'application par le schéma historique et ses données."""
        tables = ", ".join(Base.metadata.tables)

        with engine.begin() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {tables} CASCADE"))
            connection.execute(text(LEGACY_SCHEMA))
            connection.execute(text(LEGACY_DATA))


class TestGetConnection:
    """Connexion réelle via psycopg2"""

    def test_returns_open_connection(self, database_url):
        conn = DatabaseManager.get_connection(database_url)

        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                assert cursor.fetchone() == (1,)
        finally:
            conn.close()

    def test_returns_none_when_database_does_not_exist(self, database_url):
        url = make_url(database_url).set(database="inexistante_test")

        conn = DatabaseManager.get_connection(
            url.render_as_string(hide_password=False)
        )

        assert conn is None
