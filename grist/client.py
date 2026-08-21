import traceback

import requests
from utils.log import log, log_verbose, log_error, log_progress


class GristClient:
    def __init__(self, base_url, api_key, doc_id=None):
        self.base_url = base_url.rstrip("/")  # Enlever le / final s'il y en a un
        self.api_key = api_key
        self.doc_id = doc_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        log(f"Initialisation du client Grist avec l'URL de base: {self.base_url}")

    def set_doc_id(self, doc_id):
        self.doc_id = doc_id

    def _extract_email_from_scim(self, data: dict) -> str | None:
        """
        Extrait l'email primaire d'une réponse SCIM /Me.
        primary > premier email > None. userName est ignoré (peut être un pseudo).
        """
        emails = data.get("emails")

        if not emails:
            return None

        primary = next((email for email in emails if email.get("primary")), None)

        return (primary or emails[0]).get("value")

    def get_grist_user_email(self):
        """Email Grist de l'utilisateur courant via SCIM /Me. None si indisponible."""
        try:
            resp = requests.get(
                f"{self.base_url}/scim/v2/Me", headers=self.headers, timeout=10
            )
            if resp.status_code != 200:
                log_error(f"SCIM /Me HTTP {resp.status_code}")
                return None

            return self._extract_email_from_scim(resp.json())
        except Exception as e:
            log_error(f"SCIM /Me indisponible: {e}")

            return None

    def table_exists(self, table_id):
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

    def get_existing_dossier_numbers(self, table_id):
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
        log_verbose(f"Récupération des enregistrements existants depuis {url}")
        log_progress.log("Récupération des enregistrements existants")

        response = requests.get(url, headers=self.headers)
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
    def get_existing_dossier_dates(self, table_id):
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

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
        response = requests.get(url, headers=self.headers)

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

    def get_sync_metadata(self, demarche_number):
        """
        Récupère les métadonnées de sync pour une démarche depuis Sync_metadata.
        Retourne un dict ou None si pas encore de sync enregistrée.
        """
        url = f"{self.base_url}/docs/{self.doc_id}/tables/Sync_metadata/records"
        response = requests.get(url, headers=self.headers)

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
                }

        return None  # première sync

    def save_sync_metadata(self, demarche_number, metadata, existing_grist_id=None):
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
        get_response = requests.get(url, headers=self.headers)
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
            response = requests.patch(url, headers=self.headers, json=payload)
        else:
            payload = {"records": [{"fields": fields}]}
            response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code in [200, 201]:
            log(f"  Sync_metadata sauvegardée pour démarche {demarche_number}")
        else:
            log_error(
                f"  Erreur save_sync_metadata: {response.status_code} — {response.text[:200]}"
            )

        return existing_grist_id

    def upsert_dossier_in_grist(self, table_id, row_dict):
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
            log_error("dossier_number ou number manquant dans les données")
            log_verbose(f"Données disponibles: {row_dict.keys()}")
            return False

        # Convertir le numéro de dossier en chaîne pour les comparaisons
        dossier_number_str = str(dossier_number)

        # Récupération des dossiers existants pour vérifier si on doit faire un update ou un insert
        log_verbose(f"Récupération des dossiers existants pour la table {table_id}...")
        existing_records = self.get_existing_dossier_numbers(table_id)
        log_verbose(f"Dossiers existants trouvés: {len(existing_records)}")

        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"

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
            update_payload = {
                "records": [{"id": record_id, "fields": formatted_row["fields"]}]
            }
            response = requests.patch(url, headers=self.headers, json=update_payload)
        else:
            # Création d'un nouvel enregistrement
            log_verbose(
                f"Dossier {dossier_number_str} non trouvé, création d'un nouvel enregistrement..."
            )
            create_payload = {"records": [formatted_row]}
            response = requests.post(url, headers=self.headers, json=create_payload)

        if response.status_code in [200, 201]:
            return True
        else:
            log_error(
                f"Erreur UPSERT pour {dossier_number_str}: {response.status_code} - {response.text}"
            )
            return False

    def list_documents(self):
        url = f"{self.base_url}/docs"
        log_verbose(f"GET {url}")
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data

    def get_document_info(self):
        if not self.doc_id:
            raise ValueError("Document ID is required")
        url = f"{self.base_url}/docs/{self.doc_id}"
        log_verbose(f"GET {url}")
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data

    def list_tables(self):
        if not self.doc_id:
            raise ValueError("Document ID is required")

        url = f"{self.base_url}/docs/{self.doc_id}/tables"
        log_verbose(f"GET {url}")
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        data = response.json()
        return data

    def create_table(self, table_id, columns):
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

        response = requests.post(url, headers=self.headers, json=data)
        if response.status_code != 200:
            log_error(f"Erreur {response.status_code}: {response.text}")
            response.raise_for_status()

        result = response.json()
        return result

    def get_table_columns(self, table_id):
        """Récupère la liste des colonnes d'une table Grist."""
        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/columns"
        response = requests.get(url, headers=self.headers)
        if response.status_code != 200:
            log_error(
                f"Erreur get_table_columns({table_id}): {response.status_code}"
            )
            return []
        return response.json().get("columns", [])

    def add_columns(self, table_id, columns):
        """Ajoute des colonnes manquantes à une table existante."""
        if not columns:
            return
        url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/columns"
        payload = {"columns": columns}
        response = requests.post(url, headers=self.headers, json=payload)
        if response.status_code in (200, 201):
            log(f"Ajout de {len(columns)} colonnes à la table {table_id}")
        else:
            log_error(
                f"Erreur add_columns({table_id}): {response.status_code}"
            )

    def create_or_clear_grist_tables(self, demarche_number, column_types):
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
                log(f"Création de la table {dossier_table_id}")
                dossier_table_result = self.create_table(
                    dossier_table_id, column_types["dossier"]
                )
                dossier_table = dossier_table_result["tables"][0]
                dossier_table_id = dossier_table.get("id")

            # Créer la table des champs si elle n'existe pas
            if not champ_table:
                log(f"Création de la table {champ_table_id}")
                champ_table_result = self.create_table(
                    champ_table_id, column_types["champs"]
                )
                champ_table = champ_table_result["tables"][0]
                champ_table_id = champ_table.get("id")

            # Créer la table des annotations si elle n'existe pas
            if not annotation_table:
                log(f"Création de la table {annotation_table_id}")
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
        self, table_id, dossiers_list, existing_records=None, column_cache=None
    ):
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
                url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/columns"
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200:
                    columns_data = response.json()
                    if "columns" in columns_data:
                        for col in columns_data["columns"]:
                            existing_columns.add(col.get("id"))
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
            dossier_number = filtered_row_dict.get(
                "dossier_number"
            ) or filtered_row_dict.get("number")
            if not dossier_number:
                log_error("dossier_number ou number manquant dans les données")
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
            update_url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
            update_payload = {"records": normalized_updates}
            update_response = requests.patch(
                update_url, headers=self.headers, json=update_payload
            )

            if update_response.status_code in [200, 201]:
                log(
                    f"Mise à jour par lot: {len(normalized_updates)} enregistrements mis à jour avec succès"
                )
                total_success += len(normalized_updates)
            else:
                log_error(
                    f"Erreur lors de la mise à jour par lot: {update_response.status_code} - {update_response.text}"
                )

                # Fallback: essayer individuellement
                log("Tentative de mise à jour individuelle...")
                update_success = 0
                for individual_record in normalized_updates:
                    individual_payload = {"records": [individual_record]}
                    individual_response = requests.patch(
                        update_url, headers=self.headers, json=individual_payload
                    )

                    if individual_response.status_code in [200, 201]:
                        update_success += 1
                    else:
                        total_errors += 1
                        log_error(f"Échec individuel pour {individual_record['id']}")

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

            create_url = f"{self.base_url}/docs/{self.doc_id}/tables/{table_id}/records"
            create_payload = {"records": normalized_creations}
            create_response = requests.post(
                create_url, headers=self.headers, json=create_payload
            )
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
                        dossier_num = normalized_creations[i]["fields"].get(
                            "dossier_number"
                        ) or normalized_creations[i]["fields"].get("number")
                        if dossier_num and existing_records is not None:
                            existing_records[str(dossier_num)] = created.get("id")
            else:
                log_error(
                    f"Erreur lors de la création par lot: {create_response.status_code} - {create_response.text}"
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
