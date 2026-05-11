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

                configs = []
                for row in rows:
                    config = {
                        "otp_config_id": row[0],
                        "ds_api_token": ConfigManager.decrypt_value(row[1])
                        if row[1]
                        else "",
                        "demarche_number": row[2] or "",
                        "grist_base_url": row[3]
                        or "https://grist.numerique.gouv.fr/api",
                        "grist_api_key": ConfigManager.decrypt_value(row[4])
                        if row[4]
                        else "",
                        "grist_doc_id": row[5] or "",
                        "grist_user_id": row[6] or "",
                        "filter_date_start": row[7] or "",
                        "filter_date_end": row[8] or "",
                        "filter_statuses": row[9] or "",
                        "filter_groups": row[10] or "",
                    }

                    # Charger les autres valeurs depuis les variables d'environnement
                    config.update(
                        {
                            "ds_api_url": DEMARCHES_API_URL,
                            "batch_size": int(os.getenv("BATCH_SIZE", "25")),
                            "max_workers": int(os.getenv("MAX_WORKERS", "2")),
                            "parallel": os.getenv("PARALLEL", "True").lower() == "true",
                        }
                    )

                    configs.append(config)

                if not configs:
                    # Retourner une config vide si aucune trouvée
                    configs.append(
                        {
                            "otp_config_id": None,
                            "ds_api_token": "",
                            "demarche_number": "",
                            "grist_base_url": "https://grist.numerique.gouv.fr/api",
                            "grist_api_key": "",
                            "grist_doc_id": "",
                            "grist_user_id": "",
                            "filter_date_start": "",
                            "filter_date_end": "",
                            "filter_statuses": "",
                            "filter_groups": "",
                            "ds_api_url": DEMARCHES_API_URL,
                            "batch_size": int(os.getenv("BATCH_SIZE", "25")),
                            "max_workers": int(os.getenv("MAX_WORKERS", "2")),
                            "parallel": os.getenv("PARALLEL", "True").lower() == "true",
                        }
                    )

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

                if row:
                    config = {
                        "otp_config_id": row[0],
                        "ds_api_token": ConfigManager.decrypt_value(row[1])
                        if row[1]
                        else "",
                        "demarche_number": row[2] or "",
                        "grist_base_url": row[3]
                        or "https://grist.numerique.gouv.fr/api",
                        "grist_api_key": ConfigManager.decrypt_value(row[4])
                        if row[4]
                        else "",
                        "grist_doc_id": row[5] or "",
                        "grist_user_id": row[6] or "",
                        "filter_date_start": row[7] or "",
                        "filter_date_end": row[8] or "",
                        "filter_statuses": row[9] or "",
                        "filter_groups": row[10] or "",
                    }
                else:
                    raise Exception("Configuration not found")

                # Charger les autres valeurs depuis les variables d'environnement
                config.update(
                    {
                        "ds_api_url": DEMARCHES_API_URL,
                        "batch_size": int(os.getenv("BATCH_SIZE", "25")),
                        "max_workers": int(os.getenv("MAX_WORKERS", "2")),
                        "parallel": os.getenv("PARALLEL", "True").lower() == "true",
                    }
                )

                return config

        except Exception as e:
            logger.error(f"Erreur lors du chargement depuis la base: {str(e)}")
            conn.close()
            raise Exception(str(e))
        finally:
            conn.close()

    def save_config(self, config):
        """Sauvegarde la configuration dans la base de données"""
        conn = DatabaseManager.get_connection(self.database_url)

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
                            config.get("demarche_number", ""),
                            config.get(
                                "grist_base_url", "https://grist.numerique.gouv.fr/api"
                            ),
                            grist_api_key,
                            config.get("grist_doc_id", ""),
                            config.get("grist_user_id", ""),
                            config.get("filter_date_start", ""),
                            config.get("filter_date_end", ""),
                            config.get("filter_statuses", ""),
                            config.get("filter_groups", ""),
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
                            ConfigManager.encrypt_value(config.get("ds_api_token", "")),
                            config.get("demarche_number", ""),
                            config.get(
                                "grist_base_url", "https://grist.numerique.gouv.fr/api"
                            ),
                            ConfigManager.encrypt_value(
                                config.get("grist_api_key", "")
                            ),
                            config.get("grist_doc_id", ""),
                            config.get("grist_user_id", ""),
                            config.get("filter_date_start", ""),
                            config.get("filter_date_end", ""),
                            config.get("filter_statuses", ""),
                            config.get("filter_groups", ""),
                        ),
                    )
                    logger.info(
                        f"Nouvelle configuration créée pour user_id={config.get('grist_user_id')}, doc_id={config.get('grist_doc_id')}"
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
