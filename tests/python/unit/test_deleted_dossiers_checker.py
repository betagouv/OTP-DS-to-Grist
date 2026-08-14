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

    def _mock_get(self, status=200, columns=None):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = {"columns": columns or []}
        return response

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_all_columns_present_no_post(self):
        """les 3 colonnes existent -> True, pas de POST"""
        get_response = self._mock_get(
            columns=[{"id": COLUMN_ID}, {"id": DATE_COLUMN_ID}, {"id": REASON_COLUMN_ID}]
        )
        with (
            patch(
                "deleted_dossiers_checker.requests.get",
                return_value=get_response,
            ),
            patch("deleted_dossiers_checker.requests.post") as mock_post,
        ):
            result = _ensure_deletion_columns(
                self.client, "dossiers", self.log, self.log_error
            )
        assert result is True
        mock_post.assert_not_called()

    def test_missing_columns_created(self):
        """colonnes absentes -> POST des 3 colonnes avec label et type"""
        get_response = self._mock_get()
        post_response = self._mock_post()
        with (
            patch(
                "deleted_dossiers_checker.requests.get",
                return_value=get_response,
            ),
            patch(
                "deleted_dossiers_checker.requests.post",
                return_value=post_response,
            ) as mock_post,
        ):
            result = _ensure_deletion_columns(
                self.client, "dossiers", self.log, self.log_error
            )
        assert result is True
        payload = mock_post.call_args.kwargs["json"]
        columns = payload["columns"]
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
        get_response = self._mock_get(status=500)
        post_response = self._mock_post()
        with (
            patch(
                "deleted_dossiers_checker.requests.get",
                return_value=get_response,
            ),
            patch(
                "deleted_dossiers_checker.requests.post",
                return_value=post_response,
            ) as mock_post,
        ):
            result = _ensure_deletion_columns(
                self.client, "dossiers", self.log, self.log_error
            )
        assert result is True
        assert len(mock_post.call_args.kwargs["json"]["columns"]) == 3

    def test_post_error_returns_false(self):
        """POST en échec -> False"""
        get_response = self._mock_get()
        post_response = self._mock_post(status=500)
        with (
            patch(
                "deleted_dossiers_checker.requests.get",
                return_value=get_response,
            ),
            patch(
                "deleted_dossiers_checker.requests.post",
                return_value=post_response,
            ),
        ):
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
