from unittest.mock import MagicMock, patch

from deleted_dossiers_checker import (
    COLUMN_ID,
    DATE_COLUMN_ID,
    REASON_COLUMN_ID,
    _ensure_deletion_columns,
    _mark_deleted_in_grist,
)


class TestEnsureDeletionColumns:
    """Tests unitaires pour _ensure_deletion_columns"""

    def setup_method(self):
        self.client = MagicMock()
        self.log = MagicMock()
        self.log_error = MagicMock()

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_all_columns_present_no_post(self):
        """les 3 colonnes existent -> True, pas de POST"""
        self.client.get_columns.return_value = {
            COLUMN_ID: "Bool",
            DATE_COLUMN_ID: "DateTime",
            REASON_COLUMN_ID: "Text",
        }
        result = _ensure_deletion_columns(
            self.client, "dossiers", self.log, self.log_error
        )
        assert result is True
        self.client.add_columns.assert_not_called()

    def test_missing_columns_created(self):
        """colonnes absentes -> POST des 3 colonnes avec label et type"""
        self.client.get_columns.return_value = {}
        self.client.add_columns.return_value = self._mock_post()
        result = _ensure_deletion_columns(
            self.client, "dossiers", self.log, self.log_error
        )
        assert result is True
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "dossiers"
        columns = self.client.add_columns.call_args.args[1]
        assert {c["id"] for c in columns} == {
            COLUMN_ID,
            DATE_COLUMN_ID,
            REASON_COLUMN_ID,
        }
        by_id = {c["id"]: c for c in columns}
        assert by_id[COLUMN_ID]["fields"]["label"] == "Dossiers supprimés DN"
        assert by_id[COLUMN_ID]["fields"]["type"] == "Bool"
        assert by_id[DATE_COLUMN_ID]["fields"]["type"] == "DateTime"
        assert by_id[REASON_COLUMN_ID]["fields"]["type"] == "Text"

    def test_get_error_still_posts(self):
        """GET en échec -> POST quand même des 3 colonnes"""
        self.client.get_columns.return_value = {}
        self.client.add_columns.return_value = self._mock_post()
        result = _ensure_deletion_columns(
            self.client, "dossiers", self.log, self.log_error
        )
        assert result is True
        assert len(self.client.add_columns.call_args.args[1]) == 3

    def test_post_error_returns_false(self):
        """POST en échec -> False"""
        self.client.get_columns.return_value = {}
        self.client.add_columns.return_value = self._mock_post(status=500)
        result = _ensure_deletion_columns(
            self.client, "dossiers", self.log, self.log_error
        )
        assert result is False


class TestMarkDeletedInGrist:
    """Tests unitaires pour _mark_deleted_in_grist"""

    def setup_method(self):
        self.client = MagicMock()
        self.log = MagicMock()
        self.log_error = MagicMock()

    def _mock_patch(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_patches_matching_records(self):
        """PATCH des records correspondants avec date et raison"""
        patch_response = self._mock_patch()
        grist_dict = {"123": 45}
        deleted_dossiers = [
            {"number": 123, "dateSupression": "2024-01-01", "reason": "supprimé"}
        ]
        with patch(
            "deleted_dossiers_checker.requests.patch",
            return_value=patch_response,
        ) as mock_patch:
            result = _mark_deleted_in_grist(
                self.client,
                "dossiers",
                grist_dict,
                deleted_dossiers,
                self.log,
                self.log_error,
            )
        assert result == 1
        payload = mock_patch.call_args.kwargs["json"]
        assert payload == {
            "records": [
                {
                    "id": 45,
                    "fields": {
                        COLUMN_ID: True,
                        DATE_COLUMN_ID: "2024-01-01",
                        REASON_COLUMN_ID: "supprimé",
                    },
                }
            ]
        }

    def test_skips_unknown_numbers(self):
        """numéro inconnu dans grist_dict -> 0, pas de PATCH"""
        grist_dict = {}
        deleted_dossiers = [{"number": 123}]
        with patch("deleted_dossiers_checker.requests.patch") as mock_patch:
            result = _mark_deleted_in_grist(
                self.client,
                "dossiers",
                grist_dict,
                deleted_dossiers,
                self.log,
                self.log_error,
            )
        assert result == 0
        mock_patch.assert_not_called()

    def test_patch_error_returns_zero(self):
        """PATCH en échec -> 0"""
        patch_response = self._mock_patch(status=500)
        grist_dict = {"123": 45}
        deleted_dossiers = [{"number": 123}]
        with patch(
            "deleted_dossiers_checker.requests.patch",
            return_value=patch_response,
        ):
            result = _mark_deleted_in_grist(
                self.client,
                "dossiers",
                grist_dict,
                deleted_dossiers,
                self.log,
                self.log_error,
            )
        assert result == 0
