"""
Tests unitaires pour la tâche de rafraîchissement des labels

Ces tests couvrent :
- La lecture de l'état actuel dans Grist et son comportement en erreur
- L'envoi des mises à jour par lots
- L'orchestration complète de sync_labels_for_demarche
"""

from unittest.mock import MagicMock, patch

import pytest

from sync.tasks.labels import (
    BATCH_SIZE,
    _fetch_existing_labels,
    _patch_records,
    sync_labels_for_demarche,
)


def create_mock_client():
    """Crée un mock de GristClient avec les attributs utilisés par la tâche"""
    client = MagicMock()
    client.base_url = "https://grist.test/api"
    client.doc_id = "doc123"
    client.headers = {"Authorization": "Bearer test"}
    return client


def create_mock_response(status_code=200, json_data=None, text=""):
    """Crée un mock de réponse HTTP"""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_data if json_data is not None else {}
    response.text = text
    return response


def create_mock_client_with_records(response):
    """Crée un mock de GristClient dont get_records renvoie response"""
    client = create_mock_client()
    client.get_records.return_value = response
    return client


class TestFetchExistingLabels:
    """Tests unitaires pour la fonction _fetch_existing_labels"""

    def test_fetch_existing_labels_nominal(self):
        """Test d'indexation des dossiers par numéro"""
        client = create_mock_client_with_records(
            create_mock_response(
                json_data={
                    "records": [
                        {
                            "id": 10,
                            "fields": {
                                "dossier_number": 123,
                                "label_names": "Urgent",
                                "labels_json": "[]",
                            },
                        }
                    ]
                }
            )
        )

        result = _fetch_existing_labels(client, "Table_1")

        assert "123" in result
        assert result["123"]["grist_id"] == 10
        assert result["123"]["label_names"] == "Urgent"
        client.get_records.assert_called_once_with("Table_1")

    def test_fetch_existing_labels_ignores_records_without_number(self):
        """Test que les lignes sans numéro de dossier sont ignorées"""
        client = create_mock_client_with_records(
            create_mock_response(json_data={"records": [{"id": 10, "fields": {}}]})
        )

        assert _fetch_existing_labels(client, "Table_1") == {}

    def test_fetch_existing_labels_normalizes_none(self):
        """Test que des colonnes vides sont normalisées en chaînes"""
        client = create_mock_client_with_records(
            create_mock_response(
                json_data={
                    "records": [
                        {
                            "id": 10,
                            "fields": {
                                "dossier_number": 123,
                                "label_names": None,
                                "labels_json": None,
                            },
                        }
                    ]
                }
            )
        )

        result = _fetch_existing_labels(client, "Table_1")

        assert result["123"]["label_names"] == ""
        assert result["123"]["labels_json"] == ""

    def test_fetch_existing_labels_raises_on_error(self):
        """Test qu'un échec de lecture lève une exception"""
        client = create_mock_client_with_records(
            create_mock_response(status_code=500, text="error")
        )

        with pytest.raises(RuntimeError):
            _fetch_existing_labels(client, "Table_1")


class TestPatchRecords:
    """Tests unitaires pour la fonction _patch_records"""

    def test_patch_records_empty(self):
        """Test qu'aucune requête n'est envoyée sans enregistrement"""
        client = create_mock_client()

        updated = _patch_records(client, "Table_1", [], MagicMock(), MagicMock())

        assert updated == 0
        client.patch_records.assert_not_called()

    def test_patch_records_splits_into_batches(self):
        """Test que les enregistrements sont découpés en lots aux bonnes bornes"""
        client = create_mock_client()
        client.patch_records.return_value = create_mock_response()
        records = [{"id": i, "fields": {}} for i in range(BATCH_SIZE + 1)]

        updated = _patch_records(client, "Table_1", records, MagicMock(), MagicMock())

        assert updated == BATCH_SIZE + 1
        assert client.patch_records.call_count == 2
        assert client.patch_records.call_args_list[0].args[0] == "Table_1"
        assert client.patch_records.call_args_list[0].args[1] == records[:BATCH_SIZE]
        assert client.patch_records.call_args_list[1].args[1] == records[BATCH_SIZE:]

    def test_patch_records_logs_error_on_failure(self):
        """Test qu'un lot en échec est logué et non compté"""
        client = create_mock_client()
        client.patch_records.return_value = create_mock_response(
            status_code=400, text="error"
        )
        log_error = MagicMock()

        updated = _patch_records(
            client,
            "Table_1",
            [{"id": 1, "fields": {}}],
            MagicMock(),
            log_error,
        )

        assert updated == 0
        log_error.assert_called_once()


class TestSyncLabelsForDemarche:
    """Tests unitaires pour la fonction sync_labels_for_demarche"""

    def test_sync_labels_empty_grist(self):
        """Test qu'une table vide retourne un résultat à zéro sans appel DN"""
        client = create_mock_client_with_records(
            create_mock_response(json_data={"records": []})
        )

        result = sync_labels_for_demarche(
            client, "Table_1", 12345, MagicMock(), MagicMock()
        )

        assert result == {"checked": 0, "updated": 0, "missing_in_grist": 0}

    @patch("sync.tasks.labels.get_demarche_dossiers_labels_only")
    def test_sync_labels_updates_changed_only(self, mock_dn):
        """Test que seuls les dossiers dont les labels ont changé sont patchés"""
        client = create_mock_client_with_records(
            create_mock_response(
                json_data={
                    "records": [
                        {
                            "id": 10,
                            "fields": {
                                "dossier_number": 111,
                                "label_names": "Urgent",
                                "labels_json": '[{"id": "l1", "name": "Urgent", '
                                '"color": "red"}]',
                            },
                        },
                        {
                            "id": 11,
                            "fields": {
                                "dossier_number": 222,
                                "label_names": "",
                                "labels_json": "",
                            },
                        },
                    ]
                }
            )
        )
        client.patch_records.return_value = create_mock_response()
        mock_dn.return_value = [
            {
                "number": 111,
                "labels": [{"id": "l1", "name": "Urgent", "color": "red"}],
            },
            {
                "number": 222,
                "labels": [{"id": "l2", "name": "Nouveau", "color": "blue"}],
            },
        ]

        result = sync_labels_for_demarche(
            client, "Table_1", 12345, MagicMock(), MagicMock()
        )

        assert result["checked"] == 2
        assert result["updated"] == 1
        assert result["missing_in_grist"] == 0

        assert client.patch_records.call_args.args[0] == "Table_1"
        sent_records = client.patch_records.call_args.args[1]
        assert len(sent_records) == 1
        assert sent_records[0]["id"] == 11

    @patch("sync.tasks.labels.get_demarche_dossiers_labels_only")
    def test_sync_labels_counts_missing_in_grist(self, mock_dn):
        """Test qu'un dossier absent de Grist est compté et non patché"""
        client = create_mock_client_with_records(
            create_mock_response(
                json_data={
                    "records": [
                        {
                            "id": 10,
                            "fields": {
                                "dossier_number": 111,
                                "label_names": "",
                                "labels_json": "",
                            },
                        }
                    ]
                }
            )
        )
        mock_dn.return_value = [
            {"number": 111, "labels": []},
            {"number": 999, "labels": [{"id": "l1", "name": "X", "color": "red"}]},
        ]

        result = sync_labels_for_demarche(
            client, "Table_1", 12345, MagicMock(), MagicMock()
        )

        assert result["checked"] == 2
        assert result["updated"] == 0
        assert result["missing_in_grist"] == 1
        client.patch_records.assert_not_called()

    @patch("sync.tasks.labels.get_demarche_dossiers_labels_only")
    def test_sync_labels_propagates_read_error(self, mock_dn):
        """Test qu'une erreur de lecture Grist remonte à l'appelant"""
        client = create_mock_client_with_records(
            create_mock_response(status_code=500, text="error")
        )

        with pytest.raises(RuntimeError):
            sync_labels_for_demarche(
                client, "Table_1", 12345, MagicMock(), MagicMock()
            )

        mock_dn.assert_not_called()
