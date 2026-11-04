from sqlalchemy import make_url

from database.database_manager import DatabaseManager


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
