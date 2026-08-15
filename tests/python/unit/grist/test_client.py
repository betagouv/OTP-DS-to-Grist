import pytest
from unittest.mock import MagicMock, patch

from grist.client import GristClient


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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            assert self.client.get_grist_user_email() == "primary@example.com"

    def test_success_no_primary(self):
        """200 sans primary -> retourne le premier email"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"emails": [{"value": "first@example.com"}]}
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            assert self.client.get_grist_user_email() == "first@example.com"

    def test_http_error_returns_none(self):
        """401 -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 401
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            assert self.client.get_grist_user_email() is None

    def test_timeout_returns_none(self):
        """Timeout -> None"""
        with patch(
            "grist.client.requests.get",
            side_effect=Exception("timeout"),
        ):
            assert self.client.get_grist_user_email() is None

    def test_success_no_emails(self):
        """200 sans emails[] -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"userName": "john.doe@example.com"}
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.get_existing_dossier_numbers("dossiers")
        assert result == {"1001": 11, "2002": 22}

    def test_non_200_returns_empty(self):
        """non-200 -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.get_existing_dossier_dates("dossiers")
        assert result["1001"]["grist_id"] == 11
        assert result["1001"]["date_derniere_modification"] == "2024-01-01"
        assert result["2002"]["grist_id"] == 22

    def test_non_200_returns_empty(self):
        """non-200 -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
                    },
                },
            ]
        }
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.get_sync_metadata(123)
        assert result["grist_id"] == 1
        assert result["last_sync_at"] == "2024-01-01"
        assert result["force_full_sync"] is True

    def test_returns_none_if_no_match(self):
        """200 sans démarche correspondante -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "records": [{"id": 1, "fields": {"demarche_number": "999"}}]
        }
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.get_sync_metadata(123)
        assert result is None

    def test_non_200_returns_none(self):
        """non-200 -> None"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with (
            patch(
                "grist.client.requests.get",
                return_value=get_response,
            ),
            patch(
                "grist.client.requests.patch",
                return_value=patch_response,
            ) as mock_patch,
            patch("grist.client.requests.post") as mock_post,
        ):
            self.client.save_sync_metadata(
                123, {"last_sync_at": "2024-01-01"}, existing_grist_id=7
            )
        mock_patch.assert_called_once()
        mock_post.assert_not_called()
        payload = mock_patch.call_args.kwargs["json"]
        assert payload["records"][0]["id"] == 7
        assert payload["records"][0]["fields"]["demarche_number"] == 123

    def test_creates_new_record(self):
        """aucune ligne -> POST"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"records": []}
        post_response = MagicMock()
        post_response.status_code = 201
        with (
            patch(
                "grist.client.requests.get",
                return_value=get_response,
            ),
            patch(
                "grist.client.requests.post",
                return_value=post_response,
            ) as mock_post,
            patch("grist.client.requests.patch") as mock_patch,
        ):
            self.client.save_sync_metadata(123, {"last_sync_at": "2024-01-01"})
        mock_post.assert_called_once()
        mock_patch.assert_not_called()
        payload = mock_post.call_args.kwargs["json"]
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
        with (
            patch(
                "grist.client.requests.get",
                return_value=get_response,
            ),
            patch(
                "grist.client.requests.patch",
                return_value=patch_response,
            ) as mock_patch,
            patch("grist.client.requests.post") as mock_post,
        ):
            ok = self.client.upsert_dossier_in_grist(
                "dossiers", {"dossier_number": "1001", "name": "X"}
            )
        assert ok is True
        mock_patch.assert_called_once()
        mock_post.assert_not_called()
        payload = mock_patch.call_args.kwargs["json"]
        assert payload["records"][0]["id"] == 5

    def test_inserts_new(self):
        """dossier nouveau -> POST"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"records": []}
        post_response = MagicMock()
        post_response.status_code = 201
        with (
            patch(
                "grist.client.requests.get",
                return_value=get_response,
            ),
            patch(
                "grist.client.requests.post",
                return_value=post_response,
            ) as mock_post,
            patch("grist.client.requests.patch") as mock_patch,
        ):
            ok = self.client.upsert_dossier_in_grist(
                "dossiers", {"dossier_number": "2002", "name": "Y"}
            )
        assert ok is True
        mock_post.assert_called_once()
        mock_patch.assert_not_called()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["records"][0]["fields"]["dossier_number"] == "2002"

    def test_missing_dossier_number_returns_false(self):
        """sans dossier_number -> False, aucun appel réseau"""
        with patch("grist.client.requests.get") as mock_get:
            ok = self.client.upsert_dossier_in_grist("dossiers", {"name": "Z"})
        assert ok is False
        mock_get.assert_not_called()

    def test_error_status_returns_false(self):
        """statut d'erreur -> False"""
        get_response = MagicMock()
        get_response.status_code = 200
        get_response.json.return_value = {"records": []}
        post_response = MagicMock()
        post_response.status_code = 500
        post_response.text = "err"
        with (
            patch(
                "grist.client.requests.get",
                return_value=get_response,
            ),
            patch(
                "grist.client.requests.post",
                return_value=post_response,
            ),
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.list_documents()
        assert result == {"docs": [{"id": "a"}]}

    def test_error_raises(self):
        """non-200 -> raise_for_status"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = self.client.create_table("t", [{"id": "col1", "type": "Text"}])
        assert result["tables"][0]["id"] == "t"
        payload = mock_post.call_args.kwargs["json"]
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.get_columns("dossiers")
        assert result == {"name": "Text", "nb": "Int", "memo": "Text"}

    def test_skips_columns_without_id(self):
        """colonnes sans id -> ignorées"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "columns": [{"id": "name", "type": "Text"}, {"type": "Text"}, {}]
        }
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.get_columns("dossiers")
        assert result == {"name": "Text"}

    def test_missing_columns_key_returns_empty(self):
        """200 sans clé 'columns' -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
            result = self.client.get_columns("dossiers")
        assert result == {}

    def test_non_200_returns_empty(self):
        """non-200 -> {}"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ) as mock_get:
            result = self.client.get_records("dossiers")
        assert result is mock_response
        mock_get.assert_called_once()
        assert (
            mock_get.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/dossiers/records"
        )
        assert mock_get.call_args.kwargs["headers"] == self.client.headers

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        with patch(
            "grist.client.requests.get",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = self.client.add_columns(
                "t", [{"id": "col1", "type": "Text"}]
            )
        assert result is mock_response
        mock_post.assert_called_once()
        assert (
            mock_post.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/t/columns"
        )
        assert mock_post.call_args.kwargs["headers"] == self.client.headers
        assert mock_post.call_args.kwargs["json"] == {
            "columns": [{"id": "col1", "type": "Text"}]
        }

    def test_supports_fields_format(self):
        """accepte le format étendu {"id", "fields"}"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        with patch(
            "grist.client.requests.post",
            return_value=mock_response,
        ):
            self.client.add_columns(
                "t", [{"id": "col1", "fields": {"label": "X", "type": "Bool"}}]
            )

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        with patch(
            "grist.client.requests.post",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.post",
            return_value=mock_response,
        ) as mock_post:
            result = self.client.post_records("t", records)
        assert result is mock_response
        mock_post.assert_called_once()
        assert (
            mock_post.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/t/records"
        )
        assert mock_post.call_args.kwargs["headers"] == self.client.headers
        assert mock_post.call_args.kwargs["json"] == {"records": records}

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        with patch(
            "grist.client.requests.post",
            return_value=mock_response,
        ):
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
        with patch(
            "grist.client.requests.patch",
            return_value=mock_response,
        ) as mock_patch:
            result = self.client.patch_records("t", records)
        assert result is mock_response
        mock_patch.assert_called_once()
        assert (
            mock_patch.call_args.args[0]
            == "https://grist.example.com/docs/doc123/tables/t/records"
        )
        assert mock_patch.call_args.kwargs["headers"] == self.client.headers
        assert mock_patch.call_args.kwargs["json"] == {"records": records}

    def test_non_200_returns_response(self):
        """non-200 -> aucune exception, la réponse est renvoyée"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        with patch(
            "grist.client.requests.patch",
            return_value=mock_response,
        ):
            result = self.client.patch_records("t", [{"id": 42, "fields": {}}])
        assert result is mock_response
        assert result.status_code == 500

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.patch_records("t", [{"id": 42, "fields": {}}])


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
        with (
            patch(
                "grist.client.requests.get",
                return_value=columns_response,
            ) as mock_get,
            patch(
                "grist.client.requests.patch",
                return_value=update_response,
            ) as mock_patch,
            patch(
                "grist.client.requests.post",
                return_value=create_response,
            ) as mock_post,
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [
                    {"dossier_number": "1001", "name": "update-me"},
                    {"dossier_number": "2002", "name": "create-me"},
                ],
                existing_records={"1001": 5},
            )
        assert ok is True
        mock_get.assert_called_once()
        mock_patch.assert_called_once()
        mock_post.assert_called_once()

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
        with (
            patch(
                "grist.client.requests.get",
                return_value=columns_response,
            ),
            patch(
                "grist.client.requests.patch",
                side_effect=[update_response, individual_response],
            ),
        ):
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
        with (
            patch(
                "grist.client.requests.get",
                return_value=columns_response,
            ),
            patch(
                "grist.client.requests.patch",
                return_value=update_response,
            ) as mock_patch,
            patch("grist.client.requests.post"),
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x", "unknown_field": "y"}],
                existing_records={"1001": 5},
            )
        assert ok is True
        fields = mock_patch.call_args.kwargs["json"]["records"][0]["fields"]
        assert set(fields.keys()) == {"name", "dossier_number"}

    def test_no_filtering_when_columns_fetch_fails(self):
        """sans cache, erreur API colonnes -> aucun filtrage des champs"""
        columns_response = MagicMock()
        columns_response.status_code = 500
        columns_response.text = "boom"
        update_response = MagicMock()
        update_response.status_code = 200
        with (
            patch(
                "grist.client.requests.get",
                return_value=columns_response,
            ),
            patch(
                "grist.client.requests.patch",
                return_value=update_response,
            ) as mock_patch,
            patch("grist.client.requests.post"),
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x", "unknown_field": "y"}],
                existing_records={"1001": 5},
            )
        assert ok is True
        fields = mock_patch.call_args.kwargs["json"]["records"][0]["fields"]
        assert set(fields.keys()) == {"name", "dossier_number", "unknown_field"}

    def test_uses_column_cache_when_provided(self):
        """column_cache fourni -> filtrage via le cache, pas de GET colonnes"""
        column_cache = MagicMock()
        column_cache.get_columns.return_value = {"name", "dossier_number"}
        update_response = MagicMock()
        update_response.status_code = 200
        with (
            patch("grist.client.requests.get") as mock_get,
            patch(
                "grist.client.requests.patch",
                return_value=update_response,
            ) as mock_patch,
            patch("grist.client.requests.post"),
        ):
            ok = self.client.upsert_multiple_dossiers_in_grist(
                "dossiers",
                [{"dossier_number": "1001", "name": "x", "unknown_field": "y"}],
                existing_records={"1001": 5},
                column_cache=column_cache,
            )
        assert ok is True
        mock_get.assert_not_called()
        column_cache.get_columns.assert_called_once_with("dossiers")
        mock_patch.assert_called_once()
        fields = mock_patch.call_args.kwargs["json"]["records"][0]["fields"]
        assert set(fields.keys()) == {"name", "dossier_number"}

    def test_raises_without_doc_id(self):
        """sans doc_id -> ValueError"""
        client = GristClient("https://grist.example.com", "test_key")
        with pytest.raises(ValueError):
            client.upsert_multiple_dossiers_in_grist("dossiers", [])
