from unittest.mock import MagicMock, patch

from grist_processor_working_all import ColumnCache


class TestColumnCacheGetColumns:
    """Tests unitaires pour ColumnCache.get_columns"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.base_url = "https://grist.example.com"
        self.client.doc_id = "doc123"
        self.client.headers = {"Authorization": "Bearer test_key"}
        self.cache = ColumnCache(self.client)

    def test_first_call_fetches_and_caches(self):
        """1er appel -> requête API + mise en cache"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "columns": [
                {"id": "name", "type": "Text"},
                {"id": "dossier_number", "type": "Int"},
            ]
        }
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ) as mock_get:
            result = self.cache.get_columns("dossiers")
        assert result == {"name", "dossier_number"}
        mock_get.assert_called_once()

    def test_second_call_uses_cache(self):
        """2e appel -> cache, pas de nouvelle requête"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "columns": [{"id": "name", "type": "Text"}]
        }
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ) as mock_get:
            self.cache.get_columns("dossiers")
            self.cache.get_columns("dossiers")
        mock_get.assert_called_once()

    def test_force_refresh_refetches(self):
        """force_refresh=True -> nouvelle requête même si déjà en cache"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "columns": [{"id": "name", "type": "Text"}]
        }
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ) as mock_get:
            self.cache.get_columns("dossiers")
            self.cache.get_columns("dossiers", force_refresh=True)
        assert mock_get.call_count == 2

    def test_error_returns_empty_set(self):
        """réponse non-200 -> set vide"""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "boom"
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ):
            result = self.cache.get_columns("dossiers")
        assert result == set()

    def test_missing_columns_key_returns_empty_set(self):
        """200 sans clé 'columns' -> set vide"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ):
            result = self.cache.get_columns("dossiers")
        assert result == set()

    def test_skips_columns_without_id(self):
        """colonnes sans id -> ignorées"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "columns": [{"id": "name"}, {"type": "Text"}, {}]
        }
        with patch(
            "grist_processor_working_all.requests.get",
            return_value=mock_response,
        ):
            result = self.cache.get_columns("dossiers")
        assert result == {"name"}
