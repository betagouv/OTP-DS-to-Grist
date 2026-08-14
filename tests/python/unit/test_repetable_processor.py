from unittest.mock import MagicMock, patch

from repetable_processor import (
    ensure_repetable_columns_exist,
    auto_fix_missing_columns_optimized,
    process_repetables_for_grist,
)


class TestEnsureRepetableColumnsExist:
    """Tests unitaires pour ensure_repetable_columns_exist"""

    def setup_method(self):
        self.client = MagicMock()

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

    def test_empty_data_no_http(self):
        """aucune donnée -> True sans appel HTTP"""
        with patch("repetable_processor.requests.get") as mock_get:
            result = ensure_repetable_columns_exist(self.client, "blocs", [])
        assert result is True
        mock_get.assert_not_called()

    def test_all_columns_present_no_post(self):
        """colonnes nécessaires présentes -> True, pas de POST"""
        get_response = self._mock_get(columns=[{"id": "age"}])
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch("repetable_processor.requests.post") as mock_post,
        ):
            result = ensure_repetable_columns_exist(
                self.client, "blocs", [{"age": 5}]
            )
        assert result is True
        mock_post.assert_not_called()

    def test_missing_columns_created_with_inferred_type(self):
        """colonnes manquantes -> POST avec type inféré"""
        get_response = self._mock_get()
        post_response = self._mock_post()
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch(
                "repetable_processor.requests.post",
                return_value=post_response,
            ) as mock_post,
        ):
            result = ensure_repetable_columns_exist(
                self.client, "blocs", [{"age": 5}]
            )
        assert result is True
        payload = mock_post.call_args.kwargs["json"]
        assert payload == {"columns": [{"id": "age", "type": "Int"}]}

    def test_get_error_returns_false(self):
        """GET en échec -> False, pas de POST"""
        get_response = self._mock_get(status=500)
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch("repetable_processor.requests.post") as mock_post,
        ):
            result = ensure_repetable_columns_exist(
                self.client, "blocs", [{"age": 5}]
            )
        assert result is False
        mock_post.assert_not_called()

    def test_post_error_returns_false(self):
        """POST en échec -> False"""
        get_response = self._mock_get()
        post_response = self._mock_post(status=500)
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch(
                "repetable_processor.requests.post",
                return_value=post_response,
            ),
        ):
            result = ensure_repetable_columns_exist(
                self.client, "blocs", [{"age": 5}]
            )
        assert result is False


class TestAutoFixMissingColumnsOptimized:
    """Tests unitaires pour auto_fix_missing_columns_optimized"""

    def setup_method(self):
        self.client = MagicMock()

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

    def test_get_error_returns_false_none(self):
        """GET en échec -> (False, None), pas de POST"""
        get_response = self._mock_get(status=500)
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch("repetable_processor.requests.post") as mock_post,
        ):
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", {"records": []}
            )
        assert (success, response) == (False, None)
        mock_post.assert_not_called()

    def test_adds_missing_columns_then_records(self):
        """colonnes manquantes -> POST colonnes puis POST records"""
        get_response = self._mock_get()
        columns_post_response = self._mock_post()
        records_post_response = self._mock_post(status=201)
        payload = {"records": [{"fields": {"nom": "x", "age": 5}}]}
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch(
                "repetable_processor.requests.post",
                side_effect=[columns_post_response, records_post_response],
            ) as mock_post,
        ):
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", payload
            )
        assert success is True
        assert response is records_post_response
        assert mock_post.call_count == 2
        columns_payload = mock_post.call_args_list[0].kwargs["json"]
        types_by_id = {c["id"]: c["type"] for c in columns_payload["columns"]}
        assert types_by_id == {"nom": "Text", "age": "Int"}
        assert mock_post.call_args_list[1].kwargs["json"] == payload

    def test_no_missing_columns_only_records(self):
        """aucune colonne manquante -> pas de POST colonnes"""
        get_response = self._mock_get(columns=[{"id": "nom"}, {"id": "age"}])
        records_post_response = self._mock_post(status=201)
        payload = {"records": [{"fields": {"nom": "x", "age": 5}}]}
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch(
                "repetable_processor.requests.post",
                return_value=records_post_response,
            ) as mock_post,
        ):
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", payload
            )
        assert (success, response) == (True, records_post_response)
        assert mock_post.call_count == 1
        assert "columns" not in mock_post.call_args.kwargs["json"]

    def test_records_post_error_returns_false(self):
        """POST records en échec -> (False, response)"""
        get_response = self._mock_get()
        columns_post_response = self._mock_post()
        records_post_response = self._mock_post(status=400)
        payload = {"records": [{"fields": {"nom": "x"}}]}
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch(
                "repetable_processor.requests.post",
                side_effect=[columns_post_response, records_post_response],
            ),
        ):
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", payload
            )
        assert (success, response) == (False, records_post_response)

    def test_columns_post_error_no_records(self):
        """POST colonnes en échec -> (False, response), pas de POST records"""
        get_response = self._mock_get()
        columns_post_response = self._mock_post(status=400)
        with (
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch(
                "repetable_processor.requests.post",
                return_value=columns_post_response,
            ) as mock_post,
        ):
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", {"records": [{"fields": {"nom": "x"}}]}
            )
        assert (success, response) == (False, columns_post_response)
        assert mock_post.call_count == 1


class TestProcessRepetablesForGrist:
    """Tests unitaires pour la partie récupération/ajout de colonnes de process_repetables_for_grist"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"

    def _mock_get(self, status=200, columns=None):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = {"columns": columns or []}
        response.text = "boom"
        return response

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def _call(self, get_response):
        dossier_data = {"number": 123, "champs": []}
        column_types = [{"id": "champ_1", "type": "Text"}, {"id": "champ_2", "type": "Text"}]
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch("repetable_processor.requests.post") as mock_post,
        ):
            result = process_repetables_for_grist(
                self.client, dossier_data, "blocs", column_types
            )
        return result, mock_post

    def test_get_error_no_post_columns(self):
        """GET en échec -> aucune colonne ajoutée, aucun POST, pas de données insérées"""
        result, mock_post = self._call(self._mock_get(status=500))
        assert result == (0, 0)
        mock_post.assert_not_called()

    def test_missing_columns_posted_with_geo(self):
        """colonnes manquantes -> POST avec les colonnes manquantes et les colonnes géo"""
        get_response = self._mock_get(columns=[{"id": "champ_1"}])
        post_response = self._mock_post()
        dossier_data = {"number": 123, "champs": []}
        column_types = [{"id": "champ_1", "type": "Text"}, {"id": "champ_2", "type": "Text"}]
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
            patch(
                "repetable_processor.requests.get",
                return_value=get_response,
            ),
            patch(
                "repetable_processor.requests.post",
                return_value=post_response,
            ) as mock_post,
        ):
            result = process_repetables_for_grist(
                self.client, dossier_data, "blocs", column_types
            )
        assert result == (0, 0)
        assert mock_post.call_count == 1
        payload = mock_post.call_args.kwargs["json"]
        column_ids = {c["id"] for c in payload["columns"]}
        assert "champ_2" in column_ids
        assert "geo_id" in column_ids
        assert "geo_surface" in column_ids
