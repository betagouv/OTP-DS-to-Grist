from unittest.mock import MagicMock

from grist.column_cache import ColumnCache


class TestColumnCacheGetColumns:
    """Tests unitaires pour ColumnCache.get_columns"""

    def setup_method(self):
        self.client = MagicMock()
        self.client.get_columns.return_value = {
            "name": "Text",
            "dossier_number": "Int",
        }
        self.cache = ColumnCache(self.client)

    def test_first_call_delegates_and_caches(self):
        """1er appel -> délègue au client + mise en cache"""
        result = self.cache.get_columns("dossiers")
        assert result == {"name", "dossier_number"}
        self.client.get_columns.assert_called_once_with("dossiers")

    def test_second_call_uses_cache(self):
        """2e appel -> cache, pas de nouvel appel au client"""
        self.cache.get_columns("dossiers")
        self.cache.get_columns("dossiers")
        self.client.get_columns.assert_called_once()

    def test_force_refresh_refetches(self):
        """force_refresh=True -> nouvel appel même si déjà en cache"""
        self.cache.get_columns("dossiers")
        self.cache.get_columns("dossiers", force_refresh=True)
        assert self.client.get_columns.call_count == 2

    def test_error_returns_empty_set(self):
        """le client renvoie {} (erreur) -> set vide"""
        self.client.get_columns.return_value = {}
        result = self.cache.get_columns("dossiers")
        assert result == set()
