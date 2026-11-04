import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ajouter le répertoire racine au path pour les imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../.."))

from database.database_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    @patch("database.database_manager.psycopg2.connect")
    def test_get_connection_success(self, mock_connect):
        """Test connexion réussie à la base de données"""
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn

        result = DatabaseManager.get_connection("test_url")

        self.assertEqual(result, mock_conn)
        mock_connect.assert_called_once_with("test_url")

    @patch("database.database_manager.psycopg2.connect")
    def test_get_connection_failure(self, mock_connect):
        """Test échec de connexion à la base de données"""
        mock_connect.side_effect = Exception("Connection failed")

        result = DatabaseManager.get_connection("test_url")

        self.assertIsNone(result)
