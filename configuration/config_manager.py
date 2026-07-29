import os
import logging
from cryptography.fernet import Fernet
from database.database_manager import DatabaseManager
from utils.constants import DEMARCHES_API_URL

logger = logging.getLogger(__name__)


class ConfigManager:
    """Gestionnaire de configuration optimisé avec sauvegarde robuste"""

    SENSITIVE_KEYS = ["ds_api_token", "grist_api_key"]

    def __init__(self, database_url):
        self.database_url = database_url

    def get_env_path(self):
        """Retourne le chemin vers le fichier .env"""
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(script_dir, ".env")

    @staticmethod
    def get_encryption_key():
        """Récupère ou génère la clé de chiffrement"""
        key = os.getenv("ENCRYPTION_KEY")

        if not key:
            raise ValueError('"ENCRYPTION_KEY" non définie')

        return key

    @staticmethod
    def encrypt_value(value):
        """Chiffre une valeur"""
        try:
            if not value:
                return value

            key = ConfigManager.get_encryption_key()
            f = Fernet(key.encode())

            return f.encrypt(value.encode()).decode()
        except Exception as e:
            raise ValueError(
                f"Échec du chiffrement : {str(e)}. \
                Vérifiez la clé de chiffrement ou la valeur fournie."
            )

    @staticmethod
    def decrypt_value(value):
        """Déchiffre une valeur"""
        try:
            if not value:
                return value

            key = ConfigManager.get_encryption_key()
            f = Fernet(key.encode())

            return f.decrypt(value.encode()).decode()
        except Exception as e:
            raise ValueError(
                f"Échec du déchiffrement : {str(e)}. \
                Vérifiez la clé de chiffrement ou la valeur fournie."
            )

    @staticmethod
    def normalize_config(raw: dict) -> dict:
        """Normalise les types et applique les valeurs par défaut"""
        normalized = {}

        normalized["otp_config_id"] = (
            int(raw["otp_config_id"]) if raw.get("otp_config_id") is not None else None
        )
        normalized["ds_api_token"] = str(raw.get("ds_api_token") or "")
        normalized["demarche_number"] = str(raw.get("demarche_number") or "")
        normalized["grist_base_url"] = str(
            raw.get("grist_base_url") or "https://grist.numerique.gouv.fr/api"
        )
        normalized["grist_api_key"] = str(raw.get("grist_api_key") or "")
        normalized["grist_doc_id"] = str(raw.get("grist_doc_id") or "")
        normalized["grist_user_id"] = str(raw.get("grist_user_id") or "")
        normalized["filter_date_start"] = str(raw.get("filter_date_start") or "")
        normalized["filter_date_end"] = str(raw.get("filter_date_end") or "")
        normalized["filter_statuses"] = str(raw.get("filter_statuses") or "")
        normalized["filter_groups"] = str(raw.get("filter_groups") or "")

        normalized["ds_api_url"] = str(raw.get("ds_api_url") or DEMARCHES_API_URL)
        try:
            normalized["batch_size"] = int(raw.get("batch_size", 25))
        except (ValueError, TypeError):
            normalized["batch_size"] = 25
        try:
            normalized["max_workers"] = int(raw.get("max_workers", 2))
        except (ValueError, TypeError):
            normalized["max_workers"] = 2

        raw_parallel = raw.get("parallel", "True")
        if isinstance(raw_parallel, bool):
            normalized["parallel"] = raw_parallel
        else:
            normalized["parallel"] = str(raw_parallel).lower() == "true"

        return normalized

    @staticmethod
    def _build_config_from_row(row: tuple | None) -> dict:
        """Construit une config normalisée à partir d'une ligne DB (None → vide avec defaults)"""

        config_columns = [
            "id",
            "ds_api_token",
            "demarche_number",
            "grist_base_url",
            "grist_api_key",
            "grist_doc_id",
            "grist_user_id",
            "filter_date_start",
            "filter_date_end",
            "filter_statuses",
            "filter_groups",
        ]

        if row is None:
            raw: dict = {}
        else:
            raw = dict(zip(config_columns, row))
            raw["otp_config_id"] = raw.pop("id")
            raw["ds_api_token"] = (
                ConfigManager.decrypt_value(raw["ds_api_token"])
                if raw["ds_api_token"]
                else ""
            )
            raw["grist_api_key"] = (
                ConfigManager.decrypt_value(raw["grist_api_key"])
                if raw["grist_api_key"]
                else ""
            )

        raw.setdefault("ds_api_url", DEMARCHES_API_URL)
        raw.setdefault("batch_size", os.getenv("BATCH_SIZE", "25"))
        raw.setdefault("max_workers", os.getenv("MAX_WORKERS", "2"))
        raw.setdefault("parallel", os.getenv("PARALLEL", "True"))

        return ConfigManager.normalize_config(raw)

    def load_config(self, grist_user_id, grist_doc_id):
        """Charge la configuration depuis la base de données - retourne une liste"""
        conn = DatabaseManager.get_connection(self.database_url)

        try:
            with conn.cursor() as cursor:
                if not grist_user_id or not grist_doc_id:
                    raise Exception("No grist user id or doc id")

                cursor.execute(
                    """
                    SELECT id,
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
                    FROM otp_configurations
                    WHERE grist_user_id = %s AND grist_doc_id = %s
                """,
                    (grist_user_id, grist_doc_id),
                )
                rows = cursor.fetchall()

                configs = [ConfigManager._build_config_from_row(row) for row in rows]

                if not configs:
                    configs.append(ConfigManager._build_config_from_row(None))

                return configs

        except Exception as e:
            logger.error(f"Erreur lors du chargement depuis la base: {str(e)}")
            conn.close()
            raise Exception(str(e))
        finally:
            conn.close()

    def load_config_by_id(self, otp_config_id):
        """Charge la configuration depuis la base de données par ID"""
        conn = DatabaseManager.get_connection(self.database_url)

        try:
            with conn.cursor() as cursor:
                if not otp_config_id:
                    raise Exception("No otp config id")

                cursor.execute(
                    """
                    SELECT id,
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
                    FROM otp_configurations
                    WHERE id = %s
                    LIMIT 1
                """,
                    (otp_config_id,),
                )
                row = cursor.fetchone()

                if not row:
                    raise Exception("Configuration not found")

                return ConfigManager._build_config_from_row(row)

        except Exception as e:
            logger.error(f"Erreur lors du chargement depuis la base: {str(e)}")
            conn.close()
            raise Exception(str(e))
        finally:
            conn.close()

    def save_config(self, config):
        """Sauvegarde la configuration dans la base de données"""
        conn = DatabaseManager.get_connection(self.database_url)
        config = ConfigManager.normalize_config(config)

        try:
            with conn.cursor() as cursor:
                otp_config_id = config.get("otp_config_id")

                if otp_config_id:
                    # UPDATE par ID
                    # Charger l'existant pour gérer les tokens vides
                    cursor.execute(
                        """
                        SELECT ds_api_token, grist_api_key
                        FROM otp_configurations
                        WHERE id = %s
                    """,
                        (otp_config_id,),
                    )
                    row = cursor.fetchone()

                    if not row:
                        logger.error(
                            f"Configuration non trouvée pour id={otp_config_id}"
                        )
                        return False

                    # Gérer ds_api_token
                    ds_api_token = config.get("ds_api_token", "")
                    if not ds_api_token:
                        ds_api_token = row[0]  # Garder l'existant (déjà encrypté)
                    else:
                        ds_api_token = ConfigManager.encrypt_value(ds_api_token)

                    # Gérer grist_api_key
                    grist_api_key = config.get("grist_api_key", "")
                    if not grist_api_key:
                        grist_api_key = row[1]  # Garder l'existant (déjà encrypté)
                    else:
                        grist_api_key = ConfigManager.encrypt_value(grist_api_key)

                    # UPDATE par ID
                    cursor.execute(
                        """
                        UPDATE otp_configurations SET
                        ds_api_token = %s,
                        demarche_number = %s,
                        grist_base_url = %s,
                        grist_api_key = %s,
                        grist_doc_id = %s,
                        grist_user_id = %s,
                        filter_date_start = %s,
                        filter_date_end = %s,
                        filter_statuses = %s,
                        filter_groups = %s
                        WHERE id = %s
                    """,
                        (
                            ds_api_token,
                            config["demarche_number"],
                            config["grist_base_url"],
                            grist_api_key,
                            config["grist_doc_id"],
                            config["grist_user_id"],
                            config["filter_date_start"],
                            config["filter_date_end"],
                            config["filter_statuses"],
                            config["filter_groups"],
                            otp_config_id,
                        ),
                    )
                    logger.info(f"Configuration mise à jour pour id={otp_config_id}")
                else:
                    # INSERT nouvelle configuration
                    # Validation des champs requis
                    required_fields = [
                        "ds_api_token",
                        "demarche_number",
                        "grist_base_url",
                        "grist_doc_id",
                        "grist_user_id",
                    ]
                    for field in required_fields:
                        if not config.get(field):
                            logger.error(f"Champ requis manquant: {field}")
                            return False

                    grist_api_key_encrypted = (
                        ConfigManager.encrypt_value(config["grist_api_key"])
                        if config.get("grist_api_key")
                        else ""
                    )

                    if not grist_api_key_encrypted:
                        cursor.execute(
                            "SELECT grist_api_key FROM otp_configurations "
                            "WHERE grist_user_id = %s AND grist_doc_id = %s "
                            "AND grist_api_key IS NOT NULL AND grist_api_key != '' "
                            "LIMIT 1",
                            (config["grist_user_id"], config["grist_doc_id"]),
                        )
                        existing = cursor.fetchone()
                        if existing:
                            grist_api_key_encrypted = existing[0]

                    cursor.execute(
                        """
                        INSERT INTO otp_configurations
                        (ds_api_token,
                         demarche_number,
                         grist_base_url,
                         grist_api_key,
                         grist_doc_id,
                         grist_user_id,
                         filter_date_start,
                         filter_date_end,
                         filter_statuses,
                         filter_groups)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                        (
                            ConfigManager.encrypt_value(config["ds_api_token"]),
                            config["demarche_number"],
                            config["grist_base_url"],
                            grist_api_key_encrypted,
                            config["grist_doc_id"],
                            config["grist_user_id"],
                            config["filter_date_start"],
                            config["filter_date_end"],
                            config["filter_statuses"],
                            config["filter_groups"],
                        ),
                    )
                    logger.info(
                        "Nouvelle configuration créée pour "
                        f"user_id={config['grist_user_id']}, "
                        f"doc_id={config['grist_doc_id']}"
                    )

                conn.commit()
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde en base: {str(e)}")
            if conn:
                conn.close()
            return False
        finally:
            if conn:
                conn.close()

        return True
