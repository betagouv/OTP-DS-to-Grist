import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from grist import base_url
from grist.base_url import GristBaseUrlNotAllowedError
from grist.client import (
    GRIST_FALLBACK_429_DELAY,
    GRIST_MAX_429_RETRIES,
    GRIST_MAX_BODY_BYTES,
    GRIST_MAX_RANDOM_DELAY_SECONDS,
    GristClient,
    _split_records_by_size,
)
from utils.rate_limited_session import RateLimitedSession


def _weight(payload: dict) -> int:
    """Taille du corps HTTP que `requests` produirait pour ce payload."""
    return len(json.dumps(payload).encode("utf-8"))


def _records_bulk(count: int, size: int = 30_000) -> list[dict]:
    """`count` enregistrements à créer, chacun d'environ `size` octets."""
    return [
        {"fields": {"dossier_number": i, "texte": "a" * size}} for i in range(count)
    ]


def _response(status: int, records=None, text: str = "") -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = text
    response.json.return_value = {"records": records or []}
    return response


def _post_creates_ids(*args, **kwargs) -> MagicMock:
    """POST simulé : renvoie un id par enregistrement, dans l'ordre envoyé."""
    records = kwargs["json"]["records"]
    return _response(201, [{"id": r["fields"]["dossier_number"]} for r in records])


def _patch_returns_ids(*args, **kwargs) -> MagicMock:
    """PATCH simulé : renvoie un id par enregistrement, dans l'ordre envoyé."""
    return _response(200, [{"id": r["id"]} for r in kwargs["json"]["records"]])


def _refuses_on_second_call(first: callable, refused: dict) -> callable:
    """Effet de bord : le premier envoi passe, le suivant est refusé."""

    def side_effect(*args, **kwargs):
        if side_effect.calls == 0:
            side_effect.calls += 1
            return first(*args, **kwargs)
        return _response(refused["status"], text=refused["text"])

    side_effect.calls = 0
    return side_effect


def _mock_response(status_code=200, headers=None):
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {}
    return response


class TestInitBaseUrlWhitelist:
    """Tests unitaires pour le contrôle de la liste blanche dans GristClient.__init__"""

    def test_allowed_base_url(self):
        client = GristClient("https://grist.example.com", "test_key")
        assert client.base_url == "https://grist.example.com"

    def test_trailing_slash_stripped_after_validation(self):
        client = GristClient("https://grist.example.com/api/", "test_key")
        assert client.base_url == "https://grist.example.com/api"

    def test_local_url_with_port_and_path_allowed(self):
        client = GristClient("http://localhost:8484/o/docs/api", "test_key")
        assert client.base_url == "http://localhost:8484/o/docs/api"

    def test_base_url_outside_whitelist_refused(self, monkeypatch):
        monkeypatch.setattr(base_url, "BASE_URL_WHITELIST", ("grist.example.com",))

        with pytest.raises(GristBaseUrlNotAllowedError) as excinfo:
            GristClient("https://grist.evil.example", "test_key")

        assert "grist.evil.example" in str(excinfo.value)

    def test_refusal_message_does_not_reveal_whitelist(self, monkeypatch):
        monkeypatch.setattr(
            base_url,
            "BASE_URL_WHITELIST",
            ("grist.example.com", "grist.interdit.example"),
        )

        with pytest.raises(GristBaseUrlNotAllowedError) as excinfo:
            GristClient("https://grist.evil.example", "test_key")

        message = str(excinfo.value)
        assert "grist.interdit.example" not in message
        assert "grist.example.com" not in message

    def test_empty_base_url_refused(self):
        with pytest.raises(GristBaseUrlNotAllowedError):
            GristClient("", "test_key")

    def test_refused_before_any_http_session(self, monkeypatch):
        monkeypatch.setattr(base_url, "BASE_URL_WHITELIST", ("grist.example.com",))
        mock_build = MagicMock()

        with (
            patch("grist.client.build_rate_limited_session", mock_build),
            pytest.raises(GristBaseUrlNotAllowedError),
        ):
            GristClient("https://grist.evil.example", "test_key")

        mock_build.assert_not_called()


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
        session.get.assert_called_once_with(
            "https://grist.example.com/docs/doc123",
            headers=self.client.headers,
            timeout=10,
        )

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
            result = self.client.add_columns("t", [{"id": "col1", "type": "Text"}])
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


class TestSplitRecordsBySize:
    """Tests unitaires pour le découpage des enregistrements sous la limite Grist"""

    def test_empty_list_stays_one_packet(self):
        assert _split_records_by_size([]) == [[]]

    def test_body_under_limit_stays_one_packet(self):
        records = _records_bulk(10)
        assert _split_records_by_size(records) == [records]

    def test_body_above_limit_is_split_without_loss(self):
        records = _records_bulk(60)
        packets = _split_records_by_size(records)
        assert len(packets) > 1
        assert all(_weight({"records": p}) <= GRIST_MAX_BODY_BYTES for p in packets)
        assert [record for p in packets for record in p] == records

    def test_record_over_limit_stays_on_its_own(self):
        records = _records_bulk(3) + [{"fields": {"texte": "a" * (2 << 20)}}]
        packets = _split_records_by_size(records)
        assert packets[-1] == [records[-1]]
        assert [record for p in packets for record in p] == records

    def test_lower_limit_splits_more(self):
        records = _records_bulk(10, size=1000)
        packets = _split_records_by_size(records, max_bytes=3000)
        assert len(packets) > 1
        assert all(_weight({"records": p}) <= 3000 for p in packets)


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

    def test_small_payload_goes_in_one_request(self):
        """corps sous la limite -> une seule requête, inchangée"""
        records = _records_bulk(10)
        session = MagicMock()
        session.post.side_effect = _post_creates_ids
        with patch.object(GristClient, "_get_session", return_value=session):
            self.client.post_records("t", records)
        session.post.assert_called_once()
        assert session.post.call_args.kwargs["json"] == {"records": records}

    def test_large_payload_goes_in_several_requests(self):
        """corps au-dessus de la limite -> une requête par morceau"""
        records = _records_bulk(60)
        session = MagicMock()
        session.post.side_effect = _post_creates_ids
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.post_records("t", records)
        assert session.post.call_count > 1
        for call in session.post.call_args_list:
            assert _weight(call.kwargs["json"]) <= GRIST_MAX_BODY_BYTES
        assert result.status_code == 200

    def test_aggregated_response_keeps_id_order(self):
        """tous les morceaux passés -> ids concaténés dans l'ordre d'envoi"""
        records = _records_bulk(60)
        session = MagicMock()
        session.post.side_effect = _post_creates_ids
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.post_records("t", records)
        assert result.json() == {
            "records": [
                {"id": record["fields"]["dossier_number"]} for record in records
            ]
        }

    def test_refused_packet_stops_the_send(self):
        """un morceau refusé -> sa réponse est renvoyée, la suite n'est pas envoyée"""
        records = _records_bulk(60)
        refused = {"status": 413, "text": "Request body too large"}
        session = MagicMock()
        session.post.side_effect = _refuses_on_second_call(_post_creates_ids, refused)
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.post_records("t", records)
        assert result.status_code == 413
        assert result.text == "Request body too large"
        assert session.post.call_count == 2

    def test_oversized_dossier_is_sent_and_warned(self):
        """dossier seul au-dessus de la limite -> envoyé, mais journalisé"""
        records = [{"fields": {"dossier_number": 7, "texte": "a" * (2 << 20)}}]
        session = MagicMock()
        session.post.side_effect = _post_creates_ids
        with (
            patch.object(GristClient, "_get_session", return_value=session),
            patch("grist.client.log_error") as mock_log_error,
        ):
            self.client.post_records("t", records)
        session.post.assert_called_once()
        assert "Dossier 7 trop volumineux" in mock_log_error.call_args[0][0]

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

    def test_large_payload_goes_in_several_requests(self):
        """corps au-dessus de la limite -> une requête par morceau, réponse agrégée"""
        records = [{"id": i, "fields": {"texte": "a" * 30_000}} for i in range(60)]
        session = MagicMock()
        session.patch.side_effect = _patch_returns_ids
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.patch_records("t", records)
        assert session.patch.call_count > 1
        for call in session.patch.call_args_list:
            assert _weight(call.kwargs["json"]) <= GRIST_MAX_BODY_BYTES
        assert result.status_code == 200
        assert result.json() == {
            "records": [{"id": record["id"]} for record in records]
        }

    def test_refused_packet_stops_the_send(self):
        """un morceau refusé -> sa réponse est renvoyée, la suite n'est pas envoyée"""
        records = [{"id": i, "fields": {"texte": "a" * 30_000}} for i in range(60)]
        refused = {"status": 413, "text": "Request body too large"}
        session = MagicMock()
        session.patch.side_effect = _refuses_on_second_call(_patch_returns_ids, refused)
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.patch_records("t", records)
        assert result.status_code == 413
        assert session.patch.call_count == 2

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


class TestApplyUserActions:
    """Tests unitaires pour GristClient.apply_user_actions"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )
        self.actions = [["BulkRemoveRecord", "_grist_Views_section_field", [1, 2]]]

    def test_posts_actions_without_envelope(self):
        """POST /apply avec la liste brute des actions, renvoie la réponse brute"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.apply_user_actions(self.actions)
        assert result is mock_response
        session.post.assert_called_once()
        assert (
            session.post.call_args.args[0]
            == "https://grist.example.com/docs/doc123/apply"
        )
        assert session.post.call_args.kwargs["headers"] == self.client.headers
        assert session.post.call_args.kwargs["json"] == self.actions

    def test_does_not_use_the_records_delete_route(self):
        """la route /records/delete n'existe pas sur toutes les surfaces d'API"""
        session = MagicMock()
        with patch.object(GristClient, "_get_session", return_value=session):
            self.client.apply_user_actions(self.actions)
        assert "records/delete" not in session.post.call_args.args[0]

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "boom"
        session = MagicMock()
        session.post.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.apply_user_actions(self.actions)
        assert result is mock_response
        assert result.status_code == 400

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.apply_user_actions(self.actions)


class TestRunSql:
    """Tests unitaires pour GristClient.run_sql"""

    def setup_method(self):
        self.client = GristClient(
            "https://grist.example.com", "test_key", doc_id="doc123"
        )

    def test_sends_query_as_q_param(self):
        """200 -> la requête part dans le paramètre `q` de GET /sql"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"records": [{"id": 1, "fields": {"a": 1}}]}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            result = self.client.run_sql("SELECT 1 AS a")
        assert result == [{"a": 1}]
        assert (
            session.get.call_args.args[0] == "https://grist.example.com/docs/doc123/sql"
        )
        assert session.get.call_args.kwargs["headers"] == self.client.headers
        assert session.get.call_args.kwargs["params"] == {"q": "SELECT 1 AS a"}

    def test_no_rows_returns_empty_list(self):
        """200 sans ligne -> liste vide"""
        session = MagicMock()
        session.get.return_value = _response(200)
        with patch.object(GristClient, "_get_session", return_value=session):
            assert self.client.run_sql("SELECT 1") == []

    def test_rows_without_fields_become_empty_dicts(self):
        """une ligne sans champ ne fait pas échouer la lecture"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"records": [{"id": 7}]}
        session = MagicMock()
        session.get.return_value = mock_response
        with patch.object(GristClient, "_get_session", return_value=session):
            assert self.client.run_sql("SELECT 1") == [{}]

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
                self.client.run_sql("SELECT 1")

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.run_sql("SELECT 1")


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

    def test_update_failure_names_table_and_dossier(self):
        """échec du lot puis du repli -> la table et le dossier sont nommés"""
        columns_response = MagicMock()
        columns_response.status_code = 200
        columns_response.json.return_value = {
            "columns": [{"id": "name"}, {"id": "dossier_number"}]
        }
        failure = _response(500, text="boom")
        session = MagicMock()
        session.get.return_value = columns_response
        session.patch.return_value = failure
        with (
            patch.object(GristClient, "_get_session", return_value=session),
            patch("grist.client.log_error") as mock_log_error,
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x"}],
                existing_records={"1001": 5},
            )
        assert ok is False
        logs = " ".join(str(call.args[0]) for call in mock_log_error.call_args_list)
        assert "mise à jour par lot de la table dossiers" in logs
        assert "Échec individuel pour le dossier 1001 (ligne Grist 5)" in logs

    def test_create_failure_names_table(self):
        """échec de la création par lot -> la table et le nombre de dossiers"""
        columns_response = MagicMock()
        columns_response.status_code = 200
        columns_response.json.return_value = {
            "columns": [{"id": "name"}, {"id": "dossier_number"}]
        }
        session = MagicMock()
        session.get.return_value = columns_response
        session.post.return_value = _response(413, text="x")
        with (
            patch.object(GristClient, "_get_session", return_value=session),
            patch("grist.client.log_error") as mock_log_error,
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "champs",
                [
                    {"dossier_number": 1, "name": "x"},
                    {"dossier_number": 2, "name": "y"},
                ],
                existing_records={},
            )
        assert ok is False
        logs = " ".join(str(call.args[0]) for call in mock_log_error.call_args_list)
        assert "création par lot de la table champs (2 dossiers)" in logs

    def test_record_without_dossier_number_is_logged_with_its_fields(self):
        """enregistrement sans numéro de dossier -> ignoré, mais identifié"""
        columns_response = MagicMock()
        columns_response.status_code = 200
        columns_response.json.return_value = {"columns": [{"id": "name"}]}
        session = MagicMock()
        session.get.return_value = columns_response
        with (
            patch.object(GristClient, "_get_session", return_value=session),
            patch("grist.client.log_error") as mock_log_error,
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "champs", [{"name": "orphelin"}], existing_records={}
            )
        assert ok is False
        session.patch.assert_not_called()
        session.post.assert_not_called()
        logs = " ".join(str(call.args[0]) for call in mock_log_error.call_args_list)
        assert "dossier_number manquant" in logs
        assert "table champs" in logs
        assert "'name'" in logs

    def test_empty_cache_is_used_without_refetching_records(self):
        """cache vide (table vide) -> pas de relecture des enregistrements"""
        session = self._session_with_columns()
        with patch.object(GristClient, "_get_session", return_value=session):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": 1001, "name": "x"}],
                existing_records={},
            )
        assert ok is True
        urls = [call.args[0] for call in session.get.call_args_list]
        assert not any(url.endswith("/records") for url in urls)

    def test_created_ids_are_added_to_caller_cache(self):
        """cache partagé entre deux pages -> dossier créé puis mis à jour, pas recréé"""
        session = self._session_with_columns()
        cache: dict[str, int] = {}
        with patch.object(GristClient, "_get_session", return_value=session):
            self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": 1001, "name": "x"}],
                existing_records=cache,
            )
            self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": 1001, "name": "y"}],
                existing_records=cache,
            )
        assert cache == {"1001": 1001}
        session.post.assert_called_once()
        session.patch.assert_called_once()
        patched = session.patch.call_args.kwargs["json"]["records"][0]
        assert patched["id"] == 1001

    def test_missing_cache_fetches_existing_records(self):
        """sans cache (None) -> les enregistrements existants sont relus"""
        session = self._session_with_columns()
        with (
            patch.object(GristClient, "_get_session", return_value=session),
            patch.object(
                GristClient, "get_existing_dossier_numbers", return_value={"1001": 5}
            ) as mock_existing,
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers", [{"dossier_number": 1001, "name": "x"}]
            )
        assert ok is True
        mock_existing.assert_called_once_with("dossiers")
        assert session.patch.call_args.kwargs["json"]["records"][0]["id"] == 5
        session.post.assert_not_called()

    def _session_with_columns(self) -> MagicMock:
        """Session simulée : colonnes connues, création renvoyant un id par dossier."""
        columns_response = MagicMock()
        columns_response.status_code = 200
        columns_response.json.return_value = {
            "columns": [{"id": "name"}, {"id": "dossier_number"}]
        }
        session = MagicMock()
        session.get.return_value = columns_response
        session.post.side_effect = _post_creates_ids
        session.patch.side_effect = _patch_returns_ids
        return session


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
