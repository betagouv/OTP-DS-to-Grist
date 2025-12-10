import psycopg2
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestionnaire de base de données pour l'initialisation
    et la migration du schéma
    """

    @staticmethod
    def get_connection(database_url):
        """Établit une connexion à la base de données PostgreSQL"""
        logger.info(f"DATABASE_URL: {database_url}")
        try:
            return psycopg2.connect(database_url)
        except Exception as e:
            logger.error(f"Erreur de connexion à la base de données: {str(e)}")
            return None

    @staticmethod
    def create_table_if_not_exists(conn):
        """Crée la table otp_configurations
        si elle n'existe pas et ajoute les colonnes manquantes"""
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otp_configurations (
                    id SERIAL PRIMARY KEY,
                    ds_api_token TEXT,
                    demarche_number TEXT,
                    grist_base_url TEXT,
                    grist_api_key TEXT,
                    grist_doc_id TEXT
                )
            """)

            # Vérifier et ajoute la colonne id si elle n'existe pas
            cursor.execute("""
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'otp_configurations' AND column_name = 'id'
            """)
            if not cursor.fetchone():
                cursor.execute("""
                    ALTER TABLE otp_configurations ADD COLUMN id SERIAL PRIMARY KEY
                """)

            cursor.execute("""
                ALTER TABLE otp_configurations
                ADD COLUMN IF NOT EXISTS grist_user_id TEXT DEFAULT ''
            """)

            # Add filter columns
            cursor.execute("""
                ALTER TABLE otp_configurations
                ADD COLUMN IF NOT EXISTS filter_date_start TEXT
            """)

            cursor.execute("""
                ALTER TABLE otp_configurations
                ADD COLUMN IF NOT EXISTS filter_date_end TEXT
            """)

            cursor.execute("""
                ALTER TABLE otp_configurations
                ADD COLUMN IF NOT EXISTS filter_statuses TEXT
            """)

            cursor.execute("""
                ALTER TABLE otp_configurations
                ADD COLUMN IF NOT EXISTS filter_groups TEXT
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_schedules (
                    id SERIAL PRIMARY KEY,
                    otp_config_id INTEGER,
                    frequency TEXT DEFAULT 'daily',
                    enabled BOOLEAN DEFAULT FALSE,
                    last_run TIMESTAMP,
                    next_run TIMESTAMP,
                    last_status TEXT,
                    FOREIGN KEY (otp_config_id) REFERENCES otp_configurations(id) ON DELETE SET NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_logs (
                    id SERIAL PRIMARY KEY,
                    grist_user_id TEXT,
                    grist_doc_id TEXT,
                    status TEXT,
                    message TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Ajouter les colonnes manquantes aux tables existantes
            # (aucune pour le moment)

            # Insérer une ligne vide si la table est vide
            cursor.execute("SELECT COUNT(*) FROM otp_configurations")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO otp_configurations (
                        ds_api_token,
                        demarche_number,
                        grist_base_url,
                        grist_api_key,
                        grist_doc_id,
                        grist_user_id,
                        filter_date_start,
                        filter_date_end,
                        filter_statuses,
                        filter_groups
                    ) VALUES (
                        '',
                        '',
                        'https://grist.numerique.gouv.fr/api',
                        '',
                        '',
                        '',
                        '',
                        '',
                        '',
                        ''
                    )
                """)
            conn.commit()

    @staticmethod
    def init_db(database_url):
        """Initialise la base de données en créant les tables si nécessaire"""
        conn = DatabaseManager.get_connection(database_url)
        if conn:
            try:
                DatabaseManager.create_table_if_not_exists(conn)
                logger.info("Tables de base de données initialisées")
            finally:
                conn.close()
        else:
            logger.error("Impossible de se connecter à la base de données pour l'initialisation")
