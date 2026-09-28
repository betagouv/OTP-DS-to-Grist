import json
import os
import traceback
from collections.abc import Callable
from typing import Any

import requests

from utils.log import log, log_verbose, log_error, log_progress
from utils.rate_limited_session import RateLimitedSession, build_rate_limited_session


# Configuration du rate limiting réactif des appels à l'API Grist,
# surchargeable via variables d'environnement.
# Grist ne renvoie pas d'en-têtes Retry-After / RateLimit-Reset sur les 429 :
# RateLimitedSession retombe alors sur GRIST_FALLBACK_429_DELAY.
GRIST_MAX_429_RETRIES = max(1, int(os.getenv("GRIST_MAX_429_RETRIES", "3")))
GRIST_FALLBACK_429_DELAY = int(os.getenv("GRIST_FALLBACK_429_DELAY", "60"))
GRIST_MAX_RANDOM_DELAY_SECONDS = int(
    os.getenv("GRIST_MAX_RANDOM_DELAY_SECONDS", "5")
)

# L'API Grist refuse les corps de requête trop volumineux.
# Au-delà, une écriture échoue en bloc :
# les enregistrements sont donc découpés en paquets
# pour que chaque requête reste acceptée.
GRIST_MAX_BODY_BYTES = 1024 * 1024

# Poids de l'enveloppe `{"records": [ … ]}` : le reste du corps vient des
# enregistrements sérialisés et de leur virgule séparatrice (2 octets chacun).
_RECORDS_PAYLOAD_BASE_BYTES = 13


class GristClient:
    def __init__(
        self, base_url: str, api_key: str, doc_id: str | None = None
    ) -> None:
        self.base_url: str = base_url.rstrip("/")  # Enlever le / final s'il y en a un
        self.api_key: str = api_key
        self.doc_id: str | None = doc_id
        self.headers: dict[str, str] = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        log(f"Initialisation du client Grist avec l'URL de base: {self.base_url}")
        self._session: RateLimitedSession | None = None

    def _get_session(self) -> RateLimitedSession:
        """Session HTTP du client, créée paresseusement (retry 429 + 5xx)."""
        if self._session is None:
            self._session = build_rate_limited_session(
                max_retries=GRIST_MAX_429_RETRIES,
                fallback_delay=GRIST_FALLBACK_429_DELAY,
                max_random_delay=GRIST_MAX_RANDOM_DELAY_SECONDS,
            )

        return self._session

    def set_doc_id(self, doc_id: str | None) -> None:
        self.doc_id = doc_id

    def get_grist_user_email(self) -> str | None:
        """Email Grist de l'utilisateur courant via SCIM /Me. None si indisponible."""
        try:
            resp = self._get_session().get(
                f"{self.base_url}/scim/v2/Me", headers=self.headers, timeout=10
            )
            if resp.status_code != 200:
                log_error(f"SCIM /Me HTTP {resp.status_code}")
                return None

            return self._extract_email_from_scim(resp.json())
        except Exception as e:
            log_error(f"SCIM /Me indisponible: {e}")

            return None

    def get_plan_info(self) -> dict[str, Any]:
        """Infos plan/site Grist de la session courante (GET /api/session/access/active).

        Retourne le payload complet (billingAccount.product.name, features,
        apiUsage...). Peut échouer si le token n'est pas owner / manager du site.
        self.base_url porte déjà le suffixe /api (ex. /o/<site>/api), le préfixe
        /o/<site> étant retiré côté serveur avant dispatch.
        """
        resp = self._get_session().get(
            f"{self.base_url}/session/access/active",
            headers=self.headers,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    def table_exists(self, table_id: str) -> dict[str, Any] | None:
        """
        Vérifie si une table existe dans le document Grist.
        """
        try:
            tables_data = self.list_tables()

            # Vérification de la structure de tables_data
            if isinstance(tables_data, dict) and "tables" in tables_data:
                tables = tables_data["tables"]
            elif isinstance(tables_data, list):
                tables = tables_data
            else:
                log_verbose(
                    f"Structure inattendue de données de tables: {type(tables_data)}"
                )
                return None

            # Recherche case-insensitive
            for table in tables:
                if (
                    isinstance(table, dict)
                    and table.get("id", "").lower() == table_id.lower()
                ):
                    log_verbose(f"Table {table_id} trouvée avec l'ID {table.get('id')}")
                    return table

            log_verbose(f"Table {table_id} non trouvée")
            return None

        except Exception as e:
            log_error(f"Erreur lors de la recherche de la table {table_id}: {e}")
            return None

    def get_existing_dossier_numbers(self, table_id: str) -> dict[str, int]:
        if not self.doc_id:
            raise ValueError("Document ID is required")

        log_progress.log("Récupération des enregistrements existants")

        response = self.get_records(table_id)
        if response.status_code != 200:
            log_error(
                f"Erreur lors de la récupération des enregistrements existants: {response.status_code} - {response.text}"
            )
            return {}
        data = response.json()

        log_verbose(
            f"Nombre total d'enregistrements récupérés: {len(data.get('records', []))}"
        )

        # Chercher les enregistrements avec dossier_number ou number
        dossier_dict = {}
        if "records" in data and isinstance(data["records"], list):
            for record in data["records"]:
                if (
                    isinstance(record, dict)
                    and "fields" in record
                    and isinstance(record["fields"], dict)
                ):
                    record_id = record.get("id")
                    fields = record.get("fields", {})

                    # Vérifier si dossier_number ou number est présent
                    dossier_num = None
                    if "dossier_number" in fields and fields["dossier_number"]:
                        dossier_num = fields["dossier_number"]
                        dossier_dict[str(dossier_num)] = record_id
                    elif "number" in fields and fields["number"]:
                        dossier_num = fields["number"]
                        dossier_dict[str(dossier_num)] = record_id

        log(f"  Table '{table_id}': {len(dossier_dict)} enregistrements existants")

        return dossier_dict

    # Fonction upsert par date
    def get_existing_dossier_dates(self, table_id: str) -> dict[str, dict[str, Any]]:
        """
        Récupère les dates de modification stockées dans Grist pour la table dossiers.
        Retourne un dict {str(dossier_number): {
            "grist_id": int,
            "date_derniere_modification": str|None,
            "date_derniere_modification_champs": str|None,
            "date_derniere_modification_annotations": str|None
        }}
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        response = self.get_records(table_id)

        if response.status_code != 200:
            log_error(f"Erreur get_existing_dossier_dates: {response.status_code}")
            return {}

        dates_dict = {}
        for record in response.json().get("records", []):
            fields = record.get("fields", {})
            num = fields.get("dossier_number") or fields.get("number")
            if num:
                dates_dict[str(num)] = {
                    "grist_id": record.get("id"),
                    "date_derniere_modification": fields.get(
                        "date_derniere_modification"
                    ),
                    "date_derniere_modification_champs": fields.get(
                        "date_derniere_modification_champs"
                    ),
                    "date_derniere_modification_annotations": fields.get(
                        "date_derniere_modification_annotations"
                    ),
                }

        log(f"  Cache dates: {len(dates_dict)} dossiers chargés depuis {table_id}")
        return dates_dict

    def get_sync_metadata(
        self, demarche_number: int | str
    ) -> dict[str, Any] | None:
        """
        Récupère les métadonnées de sync pour une démarche depuis Sync_metadata.
        Retourne un dict ou None si pas encore de sync enregistrée.
        """
        url = f"{self.base_url}/docs/{self.doc_id}/tables/Sync_metadata/records"
        response = self._get_session().get(url, headers=self.headers)

        if response.status_code != 200:
            log_error(f"Erreur get_sync_metadata: {response.status_code}")
            return None

        for record in response.json().get("records", []):
            fields = record.get("fields", {})
            if str(fields.get("demarche_number") or "") == str(demarche_number):
                return {
                    "grist_id": record.get("id"),
                    "last_sync_at": fields.get("last_sync_at"),
                    "updated_since_cursor": fields.get("updated_since_cursor"),
                    "deleted_since_cursor": fields.get("deleted_since_cursor"),
                    "deleted_after_cursor": fields.get("deleted_after_cursor"),
                    "last_sync_status": fields.get("last_sync_status"),
                    "last_sync_duration": fields.get("last_sync_duration"),
                    "force_full_sync": fields.get("force_full_sync", False),
                    "filters_hash": fields.get("filters_hash"),
                }

        return None  # première sync

    def save_sync_metadata(
        self,
        demarche_number: int | str,
        metadata: dict[str, Any],
        existing_grist_id: int | None = None,
    ) -> int | None:
        """
        Crée ou met à jour la ligne de métadonnées de sync pour une démarche.

        Args:
            demarche_number: Numéro de la démarche
            metadata: dict avec les champs à sauvegarder
            existing_grist_id: ID Grist de la ligne existante (None = créer)
        """
        url = f"{self.base_url}/docs/{self.doc_id}/tables/Sync_metadata/records"
        fields = {"demarche_number": int(demarche_number), **metadata}

        # Chercher si une ligne existe déjà pour cette démarche
        get_response = self._get_session().get(url, headers=self.headers)
        existing_id = None
        if get_response.status_code == 200:
            for record in get_response.json().get("records", []):
                if int(record.get("fields", {}).get("demarche_number") or 0) == int(
                    demarche_number
                ):
                    existing_id = record.get("id")
                    break

        if existing_id:
            payload = {"records": [{"id": existing_id, "fields": fields}]}
            response = self._get_session().patch(url, headers=self.headers, json=payload)
        else:
            payload = {"records": [{"fields": fields}]}
            response = self._get_session().post(url, headers=self.headers, json=payload)

        if response.status_code in [200, 201]:
            log(f"  Sync_metadata sauvegardée pour démarche {demarche_number}")
        else:
            log_error(
                f"  Erreur save_sync_metadata: {response.status_code} — {response.text[:200]}"
            )

        return existing_grist_id

    def upsert_dossier_in_grist(self, table_id: str, row_dict: dict[str, Any]) -> bool:
        """
        Insère ou met à jour un dossier dans une table Grist, en filtrant les champs problématiques.
        """
        # Log des champs avant filtrage
        log_verbose(f"Champs dans row_dict avant filtrage: {list(row_dict.keys())}")
        log_verbose(f"Présence de 'label_names': {'label_names' in row_dict}")
        log_verbose(f"Présence de 'labels_json': {'labels_json' in row_dict}")

        if "label_names" in row_dict:
            log_verbose(f"Valeur de 'label_names': {row_dict['label_names']}")
        if "labels_json" in row_dict:
            log_verbose(f"Valeur de 'labels_json': {row_dict['labels_json']}")
            if not self.doc_id:
                raise ValueError("Document ID is required")

        # Vérifier si nous avons le numéro de dossier
        dossier_number = row_dict.get("dossier_number") or row_dict.get("number")

        if not dossier_number:
            log_error(
                f"dossier_number ou number manquant dans les données "
                f"(table {table_id}, champs {sorted(row_dict)}): l'enregistrement est ignoré"
            )
            return False

        # Convertir le numéro de dossier en chaîne pour les comparaisons
        dossier_number_str = str(dossier_number)

        # Récupération des dossiers existants pour vérifier si on doit faire un update ou un insert
        log_verbose(f"Récupération des dossiers existants pour la table {table_id}...")
        existing_records = self.get_existing_dossier_numbers(table_id)
        log_verbose(f"Dossiers existants trouvés: {len(existing_records)}")

        # S'assurer que le dictionnaire est formaté correctement pour l'API Grist
        # Grist attend des champs sous la forme {"fields": {...}}
        formatted_row = {"fields": row_dict} if "fields" not in row_dict else row_dict

        log_verbose(
            f"Recherche du dossier {dossier_number_str} dans les enregistrements existants..."
        )
        if dossier_number_str in existing_records:
            # Mise à jour de l'enregistrement existant
            record_id = existing_records[dossier_number_str]
            log_verbose(
                f"Dossier {dossier_number_str} trouvé avec ID {record_id}, mise à jour..."
            )
            response = self.patch_records(
                table_id, [{"id": record_id, "fields": formatted_row["fields"]}]
            )
        else:
            # Création d'un nouvel enregistrement
            log_verbose(
                f"Dossier {dossier_number_str} non trouvé, création d'un nouvel enregistrement..."
            )
            response = self.post_records(table_id, [formatted_row])

        if response.status_code in [200, 201]:
            return True
        else:
            log_error(
                f"Erreur UPSERT pour {dossier_number_str}: {response.status_code} - {response.text}"
            )
            return False

    def list_documents(self) -> dict[str, Any]:
        url = f"{self.base_url}/docs"
        log_verbose(f"GET {url}")
        response = self._get_session().get(url, headers=self.headers)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data

    def get_document_info(self) -> dict[str, Any]:
        if not self.doc_id:
            raise ValueError("Document ID is required")
        url = f"{self.base_url}/docs/{self.doc_id}"
        log_verbose(f"GET {url}")
        response = self._get_session().get(url, headers=self.headers)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data

    def run_sql(self, sql: str) -> list[dict[str, Any]]:
        """
        Exécute une requête SQL en lecture seule sur le document.

        Grist n'accepte que des SELECT : le tri, le filtrage et l'agrégation
        restent à la charge de l'appelant. Le format de la réponse Grist est
        traduit ici en une simple liste de champs, un dict par ligne.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/sql"
        log_verbose(f"GET {url} : {sql}")
        response = requests.get(url, headers=self.headers, params={"q": sql})

        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        records = response.json().get("records", [])
        log_verbose(f"  {len(records)} ligne(s) renvoyée(s)")

        return [record.get("fields", {}) for record in records]

    def list_tables(self) -> dict[str, Any]:
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables"
        log_verbose(f"GET {url}")
        response = self._get_session().get(url, headers=self.headers)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data

    def create_table(
        self, table_id: str, columns: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables"
        data = {"tables": [{"id": table_id, "columns": columns}]}
        log(f"Création de la table {table_id}")

        for col in columns:
            if "id" not in col or not col["id"]:
                raise ValueError(f"Column missing id: {col}")
            if "type" not in col or not col["type"]:
                raise ValueError(
                    f"Invalid column id '{col['id']}'. Must start with a letter and contain only letters, numbers, and underscores."
                )

        response = self._get_session().post(url, headers=self.headers, json=data)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        result = response.json()
        return result

    def get_columns(self, table_id: str) -> dict[str, str]:
        """
        Récupère les colonnes d'une table sous forme de dict {col_id: type}.
        Retourne un dict vide en cas d'erreur.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/columns"
        log_verbose(f"GET {url}")
        response = self._get_session().get(url, headers=self.headers)

        if response.status_code != 200:
            log_error(
                f"Erreur lors de la récupération des colonnes: {response.status_code} - {response.text}"
            )

            return {}

        columns = {}
        for col in response.json().get("columns", []):
            col_id = col.get("id")
            if col_id:
                columns[col_id] = col.get("type", "Text")

        return columns

    def get_records(self, table_id: str) -> requests.Response:
        """
        Récupère les enregistrements d'une table Grist.
        Retourne la réponse HTTP brute : l'appelant gère lui-même le statut.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
        log_verbose(f"GET {url}")
        response = self._get_session().get(url, headers=self.headers)

        return response

    def add_columns(
        self, table_id: str, columns: list[dict[str, Any]]
    ) -> requests.Response:
        """
        Ajoute des colonnes à une table Grist existante.
        Retourne la réponse HTTP brute : l'appelant gère lui-même le statut.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/columns"
        log_verbose(f"POST {url}")
        payload = {"columns": columns}
        response = self._get_session().post(url, headers=self.headers, json=payload)

        return response

    def post_records(
        self, table_id: str, records: list[dict[str, Any]]
    ) -> requests.Response:
        """
        Crée des enregistrements dans une table Grist.
        Retourne la réponse HTTP brute : l'appelant gère lui-même le statut.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
        log_verbose(f"POST {url}")

        return self._send_records(
            records,
            lambda packet: self._get_session().post(
                url, headers=self.headers, json={"records": packet}
            ),
        )

    def patch_records(
        self, table_id: str, records: list[dict[str, Any]]
    ) -> requests.Response:
        """
        Met à jour des enregistrements dans une table Grist.
        Retourne la réponse HTTP brute : l'appelant gère lui-même le statut.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
        log_verbose(f"PATCH {url}")

        return self._send_records(
            records,
            lambda packet: self._get_session().patch(
                url, headers=self.headers, json={"records": packet}
            ),
        )

    def delete_records(
        self, table_id: str, record_ids: list[int]
    ) -> requests.Response:
        """
        Supprime des enregistrements d'une table Grist.
        Le payload envoyé est la liste brute des ids (sans enveloppe).
        Retourne la réponse HTTP brute : l'appelant gère lui-même le statut.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = (
            f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records/delete"
        )
        log_verbose(f"POST {url}")
        response = self._get_session().post(url, headers=self.headers, json=record_ids)

        return response

    def apply_user_actions(self, actions: list[Any]) -> requests.Response:
        """
        Applique des actions utilisateur Grist (AddRecord, BulkRemoveRecord...).

        Passe par `/apply` et non par la route `records/delete` des enregistrements :
        celle-ci n'est pas exposée sur toutes les surfaces d'API d'un document, alors
        que `/apply` l'est toujours, et c'est le seul point d'entrée des actions.

        Le payload envoyé est la liste brute des actions (sans enveloppe).
        Retourne la réponse HTTP brute : l'appelant gère lui-même le statut.
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/apply"
        log_verbose(f"POST {url} : {len(actions)} action(s)")
        response = requests.post(url, headers=self.headers, json=actions)

        return response

    def create_or_clear_grist_tables(
        self, demarche_number: int | str, column_types: dict[str, Any]
    ) -> dict[str, str]:
        """
        Crée ou met à jour les tables Grist pour une démarche.
        """
        try:
            # FILTRAGE EXPLICITE DES COLONNES PROBLÉMATIQUES
            # Retirer toutes les colonnes qui pourraient correspondre à HeaderSectionChamp et ExplicationChamp
            filtered_champ_columns = column_types.get("champs", [])
            # Remplacer les colonnes originales par les colonnes filtrées
            column_types["champs"] = filtered_champ_columns

            # Filtrage similaire pour les colonnes d'annotations
            filtered_annotation_columns = column_types.get("annotations", [])
            # Remplacer les colonnes originales par les colonnes filtrées
            column_types["annotations"] = filtered_annotation_columns

            # Définir les IDs de tables
            dossier_table_id = f"Demarche_{demarche_number}_dossiers"
            champ_table_id = f"Demarche_{demarche_number}_champs"
            annotation_table_id = f"Demarche_{demarche_number}_annotations"

            # Récupérer les tables existantes
            existing_tables_response = self.list_tables()
            existing_tables = existing_tables_response.get("tables", [])

            # Rechercher les tables existantes (dossiers, champs, annotations, répétables)
            dossier_table = None
            champ_table = None
            annotation_table = None

            for table in existing_tables:
                if isinstance(table, dict):
                    table_id = table.get("id", "").lower()
                    if table_id == dossier_table_id.lower():
                        dossier_table = table
                        dossier_table_id = table.get("id")
                        log(
                            f"Table dossiers existante trouvée avec l'ID {dossier_table_id}"
                        )
                    elif table_id == champ_table_id.lower():
                        champ_table = table
                        champ_table_id = table.get("id")
                        log(
                            f"Table champs existante trouvée avec l'ID {champ_table_id}"
                        )
                    elif table_id == annotation_table_id.lower():
                        annotation_table = table
                        annotation_table_id = table.get("id")
                        log(
                            f"Table annotations existante trouvée avec l'ID {annotation_table_id}"
                        )

            # Créer la table des dossiers si elle n'existe pas
            if not dossier_table:
                dossier_table_result = self.create_table(
                    dossier_table_id, column_types["dossier"]
                )
                dossier_table = dossier_table_result["tables"][0]
                dossier_table_id = dossier_table.get("id")

            # Créer la table des champs si elle n'existe pas
            if not champ_table:
                champ_table_result = self.create_table(
                    champ_table_id, column_types["champs"]
                )
                champ_table = champ_table_result["tables"][0]
                champ_table_id = champ_table.get("id")

            # Créer la table des annotations si elle n'existe pas
            if not annotation_table:
                annotation_table_result = self.create_table(
                    annotation_table_id, column_types["annotations"]
                )
                annotation_table = annotation_table_result["tables"][0]
                annotation_table_id = annotation_table.get("id")

            # Retourner les IDs des tables
            return {
                "dossier_table_id": dossier_table_id,
                "champ_table_id": champ_table_id,
                "annotation_table_id": annotation_table_id,
            }

        except Exception as e:
            log_error(f"Erreur lors de la gestion des tables Grist: {e}")
            traceback.print_exc()
            raise

    def upsert_multiple_dossiers_in_grist(
        self,
        table_id: str,
        dossiers_list: list[dict[str, Any]],
        existing_records: dict[str, int] | None = None,
        column_cache=None,
    ) -> bool:
        """
        Insère ou met à jour plusieurs dossiers en une seule requête.
        Version corrigée avec gestion appropriée des succès/échecs et cache optionnel.

        Args:
            table_id: ID de la table Grist
            dossiers_list: Liste des enregistrements à traiter
            existing_records: Cache optionnel des enregistrements existants (dict)
        """
        if not self.doc_id:
            raise ValueError("Document ID is required")

        # Utiliser le cache si fourni, sinon récupérer
        if not existing_records:
            existing_records = self.get_existing_dossier_numbers(table_id)
            log_verbose(
                f"Récupération de {len(existing_records)} enregistrements existants pour traitement par lot"
            )
        else:
            log_verbose(
                f"Utilisation du cache: {len(existing_records)} enregistrements existants"
            )

        # Récupérer les colonnes existantes via le cache si disponible
        existing_columns = set()
        try:
            if column_cache:
                existing_columns = column_cache.get_columns(table_id)
            else:
                existing_columns = set(self.get_columns(table_id))
        except Exception as e:
            log_error(f"Erreur lors de la récupération des colonnes: {str(e)}")

        # Préparer les listes pour les opérations de création et de mise à jour
        to_create = []
        to_update = []

        for row_dict in dossiers_list:
            # Filtrer les colonnes qui existent dans la table
            filtered_row_dict = {}
            for key, value in row_dict.items():
                if (
                    not existing_columns
                    or key in existing_columns
                    or key == "dossier_number"
                ):
                    filtered_row_dict[key] = value

            # Obtenir le numéro de dossier
            dossier_number = _dossier_number(filtered_row_dict)
            if not dossier_number:
                log_error(
                    f"dossier_number ou number manquant dans les données "
                    f"(table {table_id}, champs {sorted(filtered_row_dict)}): "
                    "l'enregistrement est ignoré"
                )
                continue

            dossier_number_str = str(dossier_number)

            if dossier_number_str in existing_records:
                # Mise à jour d'un enregistrement existant
                record_id = existing_records[dossier_number_str]
                to_update.append({"id": record_id, "fields": filtered_row_dict})
            else:
                # Création d'un nouvel enregistrement
                to_create.append({"fields": filtered_row_dict})

        # Variables pour suivre les succès
        total_success = 0
        total_errors = 0

        # Traitement des mises à jour
        if to_update:
            # Normaliser tous les enregistrements pour qu'ils aient les mêmes champs
            all_update_keys = set()
            for record in to_update:
                all_update_keys.update(record["fields"].keys())

            normalized_updates = []
            for record in to_update:
                normalized_fields = {}
                for key in all_update_keys:
                    normalized_fields[key] = record["fields"].get(key, None)
                normalized_updates.append(
                    {"id": record["id"], "fields": normalized_fields}
                )

            # Mise à jour par lot pour toutes les tables
            update_response = self.patch_records(table_id, normalized_updates)

            if update_response.status_code in [200, 201]:
                log(
                    f"Mise à jour par lot: {len(normalized_updates)} enregistrements mis à jour avec succès"
                )
                total_success += len(normalized_updates)
            else:
                log_error(
                    f"Erreur lors de la mise à jour par lot de la table {table_id} "
                    f"({len(normalized_updates)} dossiers): "
                    f"{update_response.status_code} - {update_response.text}"
                )

                # Fallback: essayer individuellement
                log("Tentative de mise à jour individuelle...")
                update_success = 0
                for individual_record in normalized_updates:
                    individual_response = self.patch_records(
                        table_id, [individual_record]
                    )

                    if individual_response.status_code in [200, 201]:
                        update_success += 1
                    else:
                        total_errors += 1
                        dossier_number = _dossier_number(
                            individual_record["fields"]
                        )
                        log_error(
                            f"Échec individuel pour le dossier {dossier_number} "
                            f"(ligne Grist {individual_record['id']})"
                        )

                total_success += update_success
                log(
                    f"Mise à jour individuelle: {update_success}/{len(normalized_updates)} succès"
                )

        # Traitement des créations
        if to_create:
            # Normaliser tous les enregistrements de création
            all_create_keys = set()
            for record in to_create:
                all_create_keys.update(record["fields"].keys())

            normalized_creations = []
            for record in to_create:
                normalized_fields = {}
                for key in all_create_keys:
                    normalized_fields[key] = record["fields"].get(key, None)
                normalized_creations.append({"fields": normalized_fields})

            create_response = self.post_records(table_id, normalized_creations)
            log_progress.log("Écriture dans Grist")

            if create_response.status_code in [200, 201]:
                log(
                    f"Création par lot: {len(normalized_creations)} enregistrements créés avec succès"
                )
                total_success += len(normalized_creations)
                # Mettre à jour le cache in-place avec les IDs Grist créés
                created_ids = create_response.json().get("records", [])
                for i, created in enumerate(created_ids):
                    if i < len(normalized_creations):
                        dossier_num = _dossier_number(
                            normalized_creations[i]["fields"]
                        )
                        if dossier_num and existing_records is not None:
                            existing_records[str(dossier_num)] = created.get("id")
            else:
                log_error(
                    f"Erreur lors de la création par lot de la table {table_id} "
                    f"({len(normalized_creations)} dossiers): "
                    f"{create_response.status_code} - {create_response.text}"
                )
                total_errors += len(normalized_creations)

        # Retourner le succès global
        success = total_success > 0 and total_errors == 0

        # Log du résumé
        if total_success > 0 or total_errors > 0:
            log(
                f"Résumé upsert table {table_id}: {total_success} succès, {total_errors} échecs"
            )

        return success

    # --- Helpers privés ---

    def _extract_email_from_scim(self, data: dict[str, Any]) -> str | None:
        """
        Extrait l'email primaire d'une réponse SCIM /Me.

        primary > premier email > None. userName est ignoré (peut être un pseudo).
        """
        emails = data.get("emails")

        if not emails:
            return None

        primary = next((email for email in emails if email.get("primary")), None)

        return (primary or emails[0]).get("value")

    def _warn_record_too_large(self, records: list[dict[str, Any]]) -> None:
        """Journalise un envoi qui dépasse à lui seul la limite de taille de Grist."""
        poids = _records_payload_bytes(records)
        if len(records) == 1 and poids > GRIST_MAX_BODY_BYTES:
            dossier_number = (
                _dossier_number(records[0].get("fields") or records[0]) or "inconnu"
            )
            log_error(
                f"Dossier {dossier_number} trop volumineux pour Grist "
                f"({poids} octets pour une limite de {GRIST_MAX_BODY_BYTES}) : "
                "envoi tenté, il sera refusé"
            )

    def _send_records(
        self,
        records: list[dict[str, Any]],
        send: Callable[[list[dict[str, Any]]], requests.Response],
    ) -> requests.Response:
        """
        Envoie `records` par paquets tenant sous la limite de taille de Grist.

        Un paquet refusé arrête l'envoi et sa réponse est renvoyée telle quelle,
        pour que les replis individuels des appelants restent possibles. Si tous
        les paquets passent, la réponse renvoyée agrège leurs enregistrements.
        """
        packets = _split_records_by_size(records)
        if len(packets) <= 1:
            self._warn_record_too_large(records)
            return send(records)

        sent_records: list[dict[str, Any]] = []
        for index, packet in enumerate(packets, start=1):
            log(
                f"  Payload découpé en {len(packets)} paquets : envoi du paquet "
                f"{index}/{len(packets)} ({len(packet)} enregistrements)"
            )
            self._warn_record_too_large(packet)
            response = send(packet)
            if response.status_code not in (200, 201):
                log_error(
                    f"Erreur lors de l'envoi du paquet {index}/{len(packets)} : "
                    f"{response.status_code} - {response.text}"
                )
                return response
            sent_records.extend(response.json().get("records", []))

        return _aggregated_response(sent_records)


# --- Helpers privés (module) ---


def _record_weight(record: dict[str, Any]) -> int:
    """Poids d'un enregistrement dans un payload `{"records": [...]}`."""
    return len(json.dumps(record).encode("utf-8")) + 2


def _records_payload_bytes(records: list[dict[str, Any]]) -> int:
    """Taille du corps HTTP que `requests` produira pour `records`."""
    return len(json.dumps({"records": records}).encode("utf-8"))


def _split_records_by_size(
    records: list[dict[str, Any]], max_bytes: int = GRIST_MAX_BODY_BYTES
) -> list[list[dict[str, Any]]]:
    """
    Découpe les enregistrements en paquets dont le corps tient sous `max_bytes`.

    Un enregistrement plus volumineux que la limite forme son propre paquet : il
    ne peut pas être fractionné davantage, son envoi est tenté et c'est Grist
    qui décide de l'accepter ou de le refuser.
    """
    if _records_payload_bytes(records) <= max_bytes:
        return [records]

    packets: list[list[dict[str, Any]]] = []
    packet: list[dict[str, Any]] = []
    poids = _RECORDS_PAYLOAD_BASE_BYTES
    for record in records:
        poids_record = _record_weight(record)
        if packet and poids + poids_record > max_bytes:
            packets.append(packet)
            packet = []
            poids = _RECORDS_PAYLOAD_BASE_BYTES
        packet.append(record)
        poids += poids_record
    if packet:
        packets.append(packet)

    return packets


def _dossier_number(fields: dict[str, Any]) -> Any:
    """Numéro de dossier porté par les champs d'un enregistrement, s'il existe."""
    return fields.get("dossier_number") or fields.get("number")


def _aggregated_response(records: list[dict[str, Any]]) -> requests.Response:
    """
    Réponse 200 agrgeant les enregistrements renvoyés par plusieurs paquets.

    Les enregistrements sont concaténés dans l'ordre d'envoi : l'appelant peut
    ainsi continuer à associer les ids Grist aux dossiers qu'il a soumis.
    """
    reponse = requests.Response()
    reponse.status_code = 200
    reponse._content = json.dumps({"records": records}).encode("utf-8")
    reponse.headers["Content-Type"] = "application/json"

    return reponse
