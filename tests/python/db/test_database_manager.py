from sqlalchemy import Engine, inspect, make_url

from database.database_manager import DatabaseManager
from database.models import Base


def _columns_by_table(engine: Engine) -> dict[str, set[str]]:
    inspector = inspect(engine)

    return {
        table: {column["name"] for column in inspector.get_columns(table)}
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
