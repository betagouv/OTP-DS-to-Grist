import psycopg2
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Connexions psycopg2 à la base de données. Le schéma est géré par les
    migrations Alembic (database/migrations/).
    """

    @staticmethod
    def get_connection(database_url):
        """Établit une connexion à la base de données PostgreSQL"""
        try:
            return psycopg2.connect(database_url)
        except Exception as e:
            logger.error(f"Erreur de connexion à la base de données: {str(e)}")
            return None
