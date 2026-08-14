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

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_empty_data_no_http(self):
        """aucune donnée -> True sans appel HTTP"""
        result = ensure_repetable_columns_exist(self.client, "blocs", [])
        assert result is True
        self.client.get_columns.assert_not_called()

    def test_all_columns_present_no_post(self):
        """colonnes nécessaires présentes -> True, pas de POST"""
        self.client.get_columns.return_value = {"age": "Int"}
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is True
        self.client.add_columns.assert_not_called()

    def test_missing_columns_created_with_inferred_type(self):
        """colonnes manquantes -> POST avec type inféré"""
        self.client.get_columns.return_value = {"autre_col": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is True
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "blocs"
        assert self.client.add_columns.call_args.args[1] == [
            {"id": "age", "type": "Int"}
        ]

    def test_get_error_returns_false(self):
        """GET en échec -> False, pas de POST"""
        self.client.get_columns.return_value = {}
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is False
        self.client.add_columns.assert_not_called()

    def test_post_error_returns_false(self):
        """POST en échec -> False"""
        self.client.get_columns.return_value = {"autre_col": "Text"}
        self.client.add_columns.return_value = self._mock_post(status=500)
        result = ensure_repetable_columns_exist(
            self.client, "blocs", [{"age": 5}]
        )
        assert result is False


class TestAutoFixMissingColumnsOptimized:
    """Tests unitaires pour auto_fix_missing_columns_optimized"""

    def setup_method(self):
        self.client = MagicMock()

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def test_get_error_returns_false_none(self):
        """GET en échec -> (False, None), pas de POST"""
        self.client.get_columns.return_value = {}
        success, response = auto_fix_missing_columns_optimized(
            self.client, "dossiers", {"records": []}
        )
        assert (success, response) == (False, None)
        self.client.add_columns.assert_not_called()

    def test_adds_missing_columns_then_records(self):
        """colonnes manquantes -> POST colonnes puis POST records"""
        self.client.get_columns.return_value = {"deja_la": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        records_post_response = self._mock_post(status=201)
        payload = {"records": [{"fields": {"nom": "x", "age": 5}}]}
        with patch(
            "repetable_processor.requests.post",
            return_value=records_post_response,
        ) as mock_post:
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", payload
            )
        assert success is True
        assert response is records_post_response
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "dossiers"
        columns = self.client.add_columns.call_args.args[1]
        types_by_id = {c["id"]: c["type"] for c in columns}
        assert types_by_id == {"nom": "Text", "age": "Int"}
        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["json"] == payload

    def test_no_missing_columns_only_records(self):
        """aucune colonne manquante -> pas de POST colonnes"""
        self.client.get_columns.return_value = {"nom": "Text", "age": "Int"}
        records_post_response = self._mock_post(status=201)
        payload = {"records": [{"fields": {"nom": "x", "age": 5}}]}
        with patch(
            "repetable_processor.requests.post",
            return_value=records_post_response,
        ) as mock_post:
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", payload
            )
        assert (success, response) == (True, records_post_response)
        self.client.add_columns.assert_not_called()
        assert mock_post.call_count == 1
        assert "columns" not in mock_post.call_args.kwargs["json"]

    def test_records_post_error_returns_false(self):
        """POST records en échec -> (False, response)"""
        self.client.get_columns.return_value = {"deja_la": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        records_post_response = self._mock_post(status=400)
        payload = {"records": [{"fields": {"nom": "x"}}]}
        with patch(
            "repetable_processor.requests.post",
            return_value=records_post_response,
        ):
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", payload
            )
        assert (success, response) == (False, records_post_response)
        self.client.add_columns.assert_called_once()

    def test_columns_post_error_no_records(self):
        """POST colonnes en échec -> (False, response), pas de POST records"""
        self.client.get_columns.return_value = {"deja_la": "Text"}
        columns_post_response = self._mock_post(status=400)
        self.client.add_columns.return_value = columns_post_response
        with patch("repetable_processor.requests.post") as mock_post:
            success, response = auto_fix_missing_columns_optimized(
                self.client, "dossiers", {"records": [{"fields": {"nom": "x"}}]}
            )
        assert (success, response) == (False, columns_post_response)
        self.client.add_columns.assert_called_once()
        mock_post.assert_not_called()


class TestProcessRepetablesForGrist:
    """Tests unitaires pour la partie récupération/ajout de colonnes de process_repetables_for_grist"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc1"

    def _mock_post(self, status=200):
        response = MagicMock()
        response.status_code = status
        response.text = "err"
        return response

    def _call(self):
        dossier_data = {"number": 123, "champs": []}
        column_types = [{"id": "champ_1", "type": "Text"}, {"id": "champ_2", "type": "Text"}]
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
            patch("repetable_processor.requests.post") as mock_post,
        ):
            result = process_repetables_for_grist(
                self.client, dossier_data, "blocs", column_types
            )
        return result, mock_post

    def test_get_error_no_post_columns(self):
        """GET en échec -> aucune colonne ajoutée, aucun POST, pas de données insérées"""
        self.client.get_columns.return_value = {}
        result, mock_post = self._call()
        assert result == (0, 0)
        self.client.add_columns.assert_not_called()
        mock_post.assert_not_called()

    def test_missing_columns_posted_with_geo(self):
        """colonnes manquantes -> POST avec les colonnes manquantes et les colonnes géo"""
        self.client.get_columns.return_value = {"champ_1": "Text"}
        self.client.add_columns.return_value = self._mock_post()
        dossier_data = {"number": 123, "champs": []}
        column_types = [{"id": "champ_1", "type": "Text"}, {"id": "champ_2", "type": "Text"}]
        with (
            patch(
                "repetable_processor.get_existing_repetable_rows_improved_no_filter",
                return_value={},
            ),
            patch("repetable_processor.requests.post") as mock_post,
        ):
            result = process_repetables_for_grist(
                self.client, dossier_data, "blocs", column_types
            )
        assert result == (0, 0)
        self.client.add_columns.assert_called_once()
        assert self.client.add_columns.call_args.args[0] == "blocs"
        columns = self.client.add_columns.call_args.args[1]
        column_ids = {c["id"] for c in columns}
        assert "champ_2" in column_ids
        assert "geo_id" in column_ids
        assert "geo_surface" in column_ids
        mock_post.assert_not_called()
