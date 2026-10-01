import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from grist.client import (
    GRIST_FALLBACK_429_DELAY,
    GRIST_MAX_429_RETRIES,
    GRIST_MAX_RANDOM_DELAY_SECONDS,
    GristClient,
)
from utils.rate_limited_session import RateLimitedSession


def _mock_response(status_code=200, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    return response


class TestExtractEmailFromScim:
    """Tests unitaires pour GristClient._extract_email_from_scim"""

    def setup_method(self):
        self.client = GristClient("https://grist.example.com", "test_key")

    def test_primary_email(self):
        """Retourne l'email marqué primary"""
        data = {
            "emails": [
                {"value": "second@example.com", "primary": False},
                {"value": "primary@example.com", "primary": True},
            ]
        }
        assert self.client._extract_email_from_scim(data) == "primary@example.com"

    def test_no_primary_returns_first(self):
        """Sans primary, retourne le premier email"""
        data = {"emails": [{"value": "first@example.com"}]}
        assert self.client._extract_email_from_scim(data) == "first@example.com"

    def test_empty_emails(self):
        """emails vide -> None"""
        assert self.client._extract_email_from_scim({"emails": []}) is None

    def test_missing_emails(self):
        """emails absent -> None"""
        assert self.client._extract_email_from_scim({}) is None

    def test_user_name_ignored(self):
        """userName seul (sans emails) est ignoré -> None"""
        data = {"userName": "john.doe@example.com"}
        assert self.client._extract_email_from_scim(data) is None


class TestGetGristUserEmail:
    """Tests unitaires pour GristClient.get_grist_user_email"""

    def setup_method(self):
        self.client = GristClient("https://grist.example.com", "test_key")

    def test_success_primary_email(self):
        """200 avec primary -> retourne l'email"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "emails": [
                {"value": "primary@example.com", "primary": True},
            ]
        }
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            assert self.client.get_grist_user_email() == "primary@example.com"

    def test_success_no_primary(self):
        """200 sans primary -> retourne le premier email"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"emails": [{"value": "first@example.com"}]}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            assert self.client.get_grist_user_email() == "first@example.com"

    def test_http_error_returns_none(self):
        """401 -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            assert self.client.get_grist_user_email() is None

    def test_timeout_returns_none(self):
        """Timeout -> None"""
        session = MagicMock()
        session.get.side_effect = Exception("timeout")
        with patch.object(GristClient, "_get_session", return_value=session):
            assert self.client.get_grist_user_email() is None

    def test_success_no_emails(self):
        """200 sans emails[] -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"userName": "john.doe@example.com"}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            assert self.client.get_grist_user_email() is None


class TestGetExistingDossierNumbers:
    """Tests unitaires pour GristClient.get_existing_dossier_numbers"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success_builds_dossier_dict(self):
        """200 -> dict {str(dossier_number|number): record_id}"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [
                {"id": 11, "fields": {"dossier_number": "1001", "name": "A"}},
                {"id": 22, "fields": {"number": "2002"}},
                {"id": 33, "fields": {}},
            ]
        }
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_existing_dossier_numbers("dossiers")
        assert result == {"1001": 11, "2002": 22}

    def test_non_200_returns_empty(self):
        """non-200 -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_existing_dossier_numbers("dossiers")
        assert result == {}

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.get_existing_dossier_numbers("dossiers")


class TestGetExistingDossierDates:
    """Tests unitaires pour GristClient.get_existing_dossier_dates"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success_builds_dates_dict(self):
        """200 -> dict avec grist_id et dates"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [
                {
                    "id": 11,
                    "fields": {
                        "dossier_number": "1001",
                        "date_derniere_modification": "2024-01-01",
                    },
                },
                {"id": 22, "fields": {"number": "2002"}},
            ]
        }
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_existing_dossier_dates("dossiers")
        assert result["1001"]["grist_id"] == 11
        assert result["1001"]["date_derniere_modification"] == "2024-01-01"
        assert result["2002"]["grist_id"] == 22

    def test_non_200_returns_empty(self):
        """non-200 -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_existing_dossier_dates("dossiers")
        assert result == {}

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.get_existing_dossier_dates("dossiers")


class TestGetSyncMetadata:
    """Tests unitaires pour GristClient.get_sync_metadata"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_returns_matching_metadata(self):
        """200 avec démarche correspondante -> dict"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [
                {
                    "id": 1,
                    "fields": {
                        "demarche_number": "123",
                        "last_sync_at": "2024-01-01",
                        "force_full_sync": True,
                        "filters_hash": "json_key",
                    },
                },
            ]
        }
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_sync_metadata(123)
        assert result["grist_id"] == 1
        assert result["last_sync_at"] == "2024-01-01"
        assert result["force_full_sync"] is True
        assert result["filters_hash"] == "json_key"

    def test_returns_none_if_no_match(self):
        """200 sans démarche correspondante -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [{"id": 1, "fields": {"demarche_number": "999"}}]
        }
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_sync_metadata(123)
        assert result is None

    def test_non_200_returns_none(self):
        """non-200 -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_sync_metadata(123)
        assert result is None


class TestSaveSyncMetadata:
    """Tests unitaires pour GristClient.save_sync_metadata"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_updates_existing_record(self):
        """ligne existante -> PATCH avec id"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "records": [{"id": 7, "fields": {"demarche_number": "123"}}]
        }
        patch_response = MagicMock()
        patch_response.status_code = 200
        session = MagicMock()
        session.get.return_value = get_response
        session.patch.return_value = patch_response
        with patch.object(GristClient, "_get_session", return_value=session):
            self.client.save_sync_metadata(
                123, {"last_sync_at": "2024-01-01"}, existing_grist_id=7
            )
        session.patch.assert_called_once()
        session.post.assert_not_called()
        payload = session.patch.call_args.kwargs["json"]
        assert payload["records"][0]["id"] == 7
        assert payload["records"][0]["fields"]["demarche_number"] == 123

    def test_creates_new_record(self):
        """aucune ligne -> POST"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"records": []}
        post_response = MagicMock()
        post_response.status_code = 201
        session = MagicMock()
        session.get.return_value = get_response
        session.post.return_value = post_response
        with patch.object(GristClient, "_get_session", return_value=session):
            self.client.save_sync_metadata(123, {"last_sync_at": "2024-01-01"})
        session.post.assert_called_once()
        session.patch.assert_not_called()
        payload = session.post.call_args.kwargs["json"]
        assert payload["records"][0]["fields"]["demarche_number"] == 123


class TestUpsertDossierInGrist:
    """Tests unitaires pour GristClient.upsert_dossier_in_grist"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_updates_existing(self):
        """dossier existant -> PATCH"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {
            "records": [{"id": 5, "fields": {"dossier_number": "1001"}}]
        }
        patch_response = MagicMock()
        patch_response.status_code = 200
        session = MagicMock()
        session.get.return_value = get_response
        session.patch.return_value = patch_response
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_dossier_in_grist(
                "dossiers", {"dossier_number": "1001", "name": "X"}
            )
        assert ok is True
        session.patch.assert_called_once()
        session.post.assert_not_called()
        payload = session.patch.call_args.kwargs["json"]
        assert payload["records"][0]["id"] == 5

    def test_inserts_new(self):
        """dossier nouveau -> POST"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"records": []}
        post_response = MagicMock()
        post_response.status_code = 201
        session = MagicMock()
        session.get.return_value = get_response
        session.post.return_value = post_response
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_dossier_in_grist(
                "dossiers", {"dossier_number": "2002", "name": "Y"}
            )
        assert ok is True
        session.post.assert_called_once()
        session.patch.assert_not_called()
        payload = session.post.call_args.kwargs["json"]
        assert payload["records"][0]["fields"]["dossier_number"] == "2002"

    def test_missing_dossier_number_returns_false(self):
        """sans dossier_number -> False, aucun appel réseau"""
        session = MagicMock()
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_dossier_in_grist("dossiers", {"name": "Z"})
        assert ok is False
        session.get.assert_not_called()

    def test_error_status_returns_false(self):
        """statut d'erreur -> False"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"records": []}
        post_response = MagicMock()
        post_response.status_code = 500
        post_response.text = "err"
        session = MagicMock()
        session.get.return_value = get_response
        session.post.return_value = post_response
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_dossier_in_grist(
                "dossiers", {"dossier_number": "3003"}
            )
        assert ok is False


class TestListDocuments:
    """Tests unitaires pour GristClient.list_documents"""

    def setup_method(self):
        self.client = GristClient("https://grist.example.com", "test_key")

    def test_success(self):
        """200 -> renvoie les données"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"docs": [{"id": "a"}]}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.list_documents()
        assert result == {"docs": [{"id": "a"}]}

    def test_error_raises(self):
        """non-200 -> raise_for_status"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            with pytest.raises(Exception):
                self.client.list_documents()


class TestGetDocumentInfo:
    """Tests unitaires pour GristClient.get_document_info"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success(self):
        """200 -> renvoie les données"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "doc123"}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_document_info()
        assert result == {"id": "doc123"}

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.get_document_info()

    def test_error_raises(self):
        """non-200 -> raise_for_status"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            with pytest.raises(Exception):
                self.client.get_document_info()


class TestListTables:
    """Tests unitaires pour GristClient.list_tables"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success(self):
        """200 -> renvoie les données"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tables": [{"id": "dossiers"}]}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.list_tables()
        assert result == {"tables": [{"id": "dossiers"}]}

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.list_tables()

    def test_error_raises(self):
        """non-200 -> raise_for_status"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            with pytest.raises(Exception):
                self.client.list_tables()


class TestCreateTable:
    """Tests unitaires pour GristClient.create_table"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_column_missing_id_raises(self):
        """colonne sans id -> ValueError"""
        with pytest.raises(ValueError):
            self.client.create_table("t", [{"type": "Text"}])

    def test_column_missing_type_raises(self):
        """colonne sans type -> ValueError"""
        with pytest.raises(ValueError):
            self.client.create_table("t", [{"id": "col1"}])

    def test_success_posts(self):
        """colonnes valides -> POST et renvoie le résultat"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tables": [{"id": "t", "columns": []}]}
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.create_table("t", [{"id": "col1", "type": "Text"}])
        assert result["tables"][0]["id"] == "t"
        payload = session.post.call_args.kwargs["json"]
        assert payload["tables"][0]["id"] == "t"


class TestGetColumns:
    """Tests unitaires pour GristClient.get_columns"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success_builds_types_dict(self):
        """200 -> {id: type} avec type par défaut Text"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "columns": [
                {"id": "name", "type": "Text"},
                {"id": "nb", "type": "Int"},
                {"id": "memo"},
            ]
        }
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_columns("dossiers")
        assert result == {"name": "Text", "nb": "Int", "memo": "Text"}

    def test_skips_columns_without_id(self):
        """colonnes sans id -> ignorées"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "columns": [{"id": "name", "type": "Text"}, {"type": "Text"}, {}]
        }
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_columns("dossiers")
        assert result == {"name": "Text"}

    def test_missing_columns_key_returns_empty(self):
        """200 sans clé 'columns' -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_columns("dossiers")
        assert result == {}

    def test_non_200_returns_empty(self):
        """non-200 -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_columns("dossiers")
        assert result == {}

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.get_columns("dossiers")


class TestGetRecords:
    """Tests unitaires pour GristClient.get_records"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success_gets_records(self):
        """GET /records avec le bon URL et headers, renvoie la réponse brute"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_records("dossiers")
        assert result is mock_response
        session.get.assert_called_once()
        assert (
            session.get.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/dossiers/records"
        )
        assert session.get.call_args.kwargs["headers"] == self.client.headers

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.get_records("dossiers")
        assert result is mock_response
        assert result.status_code == 500

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.get_records("dossiers")


class TestAddColumns:
    """Tests unitaires pour GristClient.add_columns"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success_posts_columns(self):
        """POST /columns avec le bon payload, renvoie la réponse brute"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.add_columns(
                "t", [{"id": "col1", "type": "Text"}]
            )
        assert result is mock_response
        session.post.assert_called_once()
        assert (
            session.post.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/t/columns"
        )
        assert session.post.call_args.kwargs["headers"] == self.client.headers
        assert session.post.call_args.kwargs["json"] == {
            "columns": [{"id": "col1", "type": "Text"}]
        }

    def test_supports_fields_format(self):
        """accepte le format étendu {"id", "fields"}"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            self.client.add_columns(
                "t", [{"id": "col1", "fields": {"label": "X", "type": "Bool"}}]
            )

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.add_columns("t", [{"id": "col1", "type": "Text"}])
        assert result is mock_response
        assert result.status_code == 500

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.add_columns("t", [{"id": "col1", "type": "Text"}])


class TestPostRecords:
    """Tests unitaires pour GristClient.post_records"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success_posts_records(self):
        """POST /records avec le bon payload, renvoie la réponse brute"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        records = [{"fields": {"nom": "x"}}, {"fields": {"nom": "y"}}]
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.post_records("t", records)
        assert result is mock_response
        session.post.assert_called_once()
        assert (
            session.post.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/t/records"
        )
        assert session.post.call_args.kwargs["headers"] == self.client.headers
        assert session.post.call_args.kwargs["json"] == {"records": records}

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.post_records("t", [{"fields": {"nom": "x"}}])
        assert result is mock_response
        assert result.status_code == 500

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.post_records("t", [{"fields": {"nom": "x"}}])


class TestPatchRecords:
    """Tests unitaires pour GristClient.patch_records"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_success_patches_records(self):
        """PATCH /records avec le bon payload, renvoie la réponse brute"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        records = [{"id": 42, "fields": {"nom": "x"}}]
        session = MagicMock()
        session.patch.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.patch_records("t", records)
        assert result is mock_response
        session.patch.assert_called_once()
        assert (
            session.patch.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/t/records"
        )
        assert session.patch.call_args.kwargs["headers"] == self.client.headers
        assert session.patch.call_args.kwargs["json"] == {"records": records}

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        session = MagicMock()
        session.patch.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.patch_records("t", [{"id": 42, "fields": {}}])
        assert result is mock_response
        assert result.status_code == 500

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.patch_records("t", [{"id": 42, "fields": {}}])


class TestDeleteRecords:
    """Tests unitaires pour GristClient.delete_records"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_posts_raw_ids_without_envelope(self):
        """POST /records/delete avec la liste brute des ids, renvoie la réponse brute"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.delete_records("t", [1, 2])
        assert result is mock_response
        session.post.assert_called_once()
        assert (
            session.post.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/t/records/delete"
        )
        assert session.post.call_args.kwargs["headers"] == self.client.headers
        assert session.post.call_args.kwargs["json"] == [1, 2]

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.delete_records("t", [1])
        assert result is mock_response
        assert result.status_code == 500

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.delete_records("t", [1])


class TestCreateOrClearGristTables:
    """Tests unitaires pour GristClient.create_or_clear_grist_tables"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_creates_missing_tables(self):
        """aucune table existante -> crée les 3 tables"""
        with (
            patch.object(self.client, "list_tables", return_value={"tables": []}),
            patch.object(
                self.client,
                "create_table",
                side_effect=lambda table_id, columns: {"tables": [{"id": table_id}]},
            ) as mock_create,
        ):
            result = self.client.create_or_clear_grist_tables(
                5,
                {
                    "dossier": [{"id": "a", "type": "Text"}],
                    "champs": [],
                    "annotations": [],
                },
            )
        assert result["dossier_table_id"] == "Demarche_5_dossiers"
        assert result["champ_table_id"] == "Demarche_5_champs"
        assert result["annotation_table_id"] == "Demarche_5_annotations"
        assert mock_create.call_count == 3

    def test_uses_existing_tables(self):
        """tables existantes -> aucune création"""
        existing = {
            "tables": [
                {"id": "Demarche_5_dossiers"},
                {"id": "Demarche_5_champs"},
                {"id": "Demarche_5_annotations"},
            ]
        }
        with (
            patch.object(self.client, "list_tables", return_value=existing),
            patch.object(self.client, "create_table") as mock_create,
        ):
            result = self.client.create_or_clear_grist_tables(
                5, {"dossier": [], "champs": [], "annotations": []}
            )
        mock_create.assert_not_called()
        assert result["dossier_table_id"] == "Demarche_5_dossiers"
        assert result["champ_table_id"] == "Demarche_5_champs"
        assert result["annotation_table_id"] == "Demarche_5_annotations"


class TestTableExists:
    """Tests unitaires pour GristClient.table_exists"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_found_case_insensitive(self):
        """table trouvée (insensible à la casse) -> retourne la table"""
        with patch.object(
            self.client,
            "list_tables",
            return_value={"tables": [{"id": "Dossiers"}, {"id": "Champs"}]},
        ):
            result = self.client.table_exists("dossiers")
        assert result == {"id": "Dossiers"}

    def test_not_found(self):
        """table absente -> None"""
        with patch.object(
            self.client, "list_tables", return_value={"tables": [{"id": "Champs"}]}
        ):
            result = self.client.table_exists("dossiers")
        assert result is None

    def test_unexpected_structure(self):
        """structure inattendue -> None"""
        with patch.object(self.client, "list_tables", return_value="unexpected"):
            result = self.client.table_exists("dossiers")
        assert result is None


class TestUpsertMultipleDossiersInGrist:
    """Tests unitaires pour GristClient.upsert_multiple_dossiers_in_grist"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_creates_and_updates(self):
        """mix création/mise à jour -> PATCH et POST, retourne True"""
        columns_response = MagicMock()
        columns_response.status_code = 200
        columns_response.json.return_value = {
            "columns": [{"id": "name"}, {"id": "dossier_number"}]
        }
        update_response = MagicMock()
        update_response.status_code = 200
        create_response = MagicMock()
        create_response.status_code = 201
        create_response.json.return_value = {"records": [{"id": 100}]}
        session = MagicMock()
        session.get.return_value = columns_response
        session.patch.return_value = update_response
        session.post.return_value = create_response
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [
                    {"dossier_number": "1001", "name": "update-me"},
                    {"dossier_number": "2002", "name": "create-me"},
                ],
                existing_records={"1001": 5},
            )
        assert ok is True
        session.get.assert_called_once()
        session.patch.assert_called_once()
        session.post.assert_called_once()

    def test_returns_false_on_update_failure(self):
        """échec de la mise à jour par lot -> fallback individuel, retourne False"""
        columns_response = MagicMock()
        columns_response.status_code = 200
        columns_response.json.return_value = {
            "columns": [{"id": "name"}, {"id": "dossier_number"}]
        }
        update_response = MagicMock()
        update_response.status_code = 500
        update_response.text = "err"
        individual_response = MagicMock()
        individual_response.status_code = 500
        individual_response.text = "err"
        session = MagicMock()
        session.get.return_value = columns_response
        session.patch.side_effect = [update_response, individual_response]
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x"}],
                existing_records={"1001": 5},
            )
        assert ok is False

    def test_filters_unknown_fields_without_cache(self):
        """sans cache -> les colonnes de l'API filtrent les champs inconnus"""
        columns_response = MagicMock()
        columns_response.status_code = 200
        columns_response.json.return_value = {
            "columns": [{"id": "name"}, {"id": "dossier_number"}]
        }
        update_response = MagicMock()
        update_response.status_code = 200
        session = MagicMock()
        session.get.return_value = columns_response
        session.patch.return_value = update_response
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x", "unknown_field": "y"}],
                existing_records={"1001": 5},
            )
        assert ok is True
        fields = session.patch.call_args.kwargs["json"]["records"][0]["fields"]
        assert set(fields.keys()) == {"name", "dossier_number"}

    def test_no_filtering_when_columns_fetch_fails(self):
        """sans cache, erreur API colonnes -> aucun filtrage des champs"""
        columns_response = MagicMock()
        columns_response.status_code = 500
        columns_response.text = "boom"
        update_response = MagicMock()
        update_response.status_code = 200
        session = MagicMock()
        session.get.return_value = columns_response
        session.patch.return_value = update_response
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x", "unknown_field": "y"}],
                existing_records={"1001": 5},
            )
        assert ok is True
        fields = session.patch.call_args.kwargs["json"]["records"][0]["fields"]
        assert set(fields.keys()) == {"name", "dossier_number", "unknown_field"}

    def test_uses_column_cache_when_provided(self):
        """column_cache fourni -> filtrage via le cache, pas de GET colonnes"""
        column_cache = MagicMock()
        column_cache.get_columns.return_value = {"name", "dossier_number"}
        update_response = MagicMock()
        update_response.status_code = 200
        session = MagicMock()
        session.patch.return_value = update_response
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x", "unknown_field": "y"}],
                existing_records={"1001": 5},
                column_cache=column_cache,
            )
        assert ok is True
        session.get.assert_not_called()
        column_cache.get_columns.assert_called_once_with("dossiers")
        session.patch.assert_called_once()
        fields = session.patch.call_args.kwargs["json"]["records"][0]["fields"]
        assert set(fields.keys()) == {"name", "dossier_number"}

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.upsert_multiple_dossiers_in_grist("dossiers", [])


class TestGristClientSession:
    """Tests unitaires pour GristClient._get_session (retry 429 + 5xx)"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_session_is_rate_limited_and_parametrized(self):
        """_get_session -> RateLimitedSession paramétré par les constantes GRIST_*"""
        session = self.client._get_session()
        assert isinstance(session, RateLimitedSession)
        assert session.max_retries == GRIST_MAX_429_RETRIES
        assert session.fallback_delay == GRIST_FALLBACK_429_DELAY
        assert session.max_random_delay == GRIST_MAX_RANDOM_DELAY_SECONDS

    def test_session_has_5xx_adapter_mounted(self):
        """adapter 5xx monté sur https:// et http:// avec la config prévue"""
        session = self.client._get_session()
        https_adapter = session.get_adapter("https://grist.example.com")
        assert https_adapter.max_retries.total == 3
        assert https_adapter.max_retries.backoff_factor == 1
        assert https_adapter.max_retries.status_forcelist == [500, 502, 503, 504]
        assert https_adapter.max_retries.allowed_methods is None
        assert https_adapter.max_retries.raise_on_status is False
        http_adapter = session.get_adapter("http://grist.example.com")
        assert http_adapter is https_adapter

    def test_session_is_reused_and_distinct_per_client(self):
        """même client -> session réutilisée ; client différent -> session distincte"""
        first = self.client._get_session()
        assert self.client._get_session() is first

        other = GristClient("https://grist.example.com", "other_key", doc_id="doc123")
        assert other._get_session() is not first

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_429_retries_then_succeeds(self, mock_sleep, mock_log, mock_request):
        """429 sans en-tête -> retry après délai de repli puis succès"""
        mock_request.side_effect = [
            _mock_response(429),
            _mock_response(200),
        ]

        with patch("random.uniform", return_value=0):
            response = self.client.get_records("dossiers")

        assert response.status_code == 200
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once_with(GRIST_FALLBACK_429_DELAY)

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_429_exhausted_returns_429(self, mock_sleep, mock_log, mock_request):
        """429 répétés -> épuisement des essais puis la réponse 429 remonte"""
        mock_request.side_effect = [
            _mock_response(429) for _ in range(GRIST_MAX_429_RETRIES)
        ]

        with patch("random.uniform", return_value=0):
            response = self.client.get_records("dossiers")

        assert response.status_code == 429
        assert mock_request.call_count == GRIST_MAX_429_RETRIES
        assert mock_sleep.call_count == GRIST_MAX_429_RETRIES - 1
        assert mock_log.call_count == GRIST_MAX_429_RETRIES - 1

    @patch.object(requests.Session, "request")
    @patch("utils.rate_limited_session.log")
    @patch("time.sleep")
    def test_5xx_not_retried(self, mock_sleep, mock_log, mock_request):
        """5xx -> renvoyé sans attente (géré par l'adapter urllib3)"""
        mock_request.return_value = _mock_response(500)

        response = self.client.get_records("dossiers")

        assert response.status_code == 500
        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()
        mock_log.assert_not_called()